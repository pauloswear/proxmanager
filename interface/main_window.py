import datetime
from typing import Dict, Any, List, Optional, Tuple
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QDesktopWidget, QPushButton, QMessageBox, 
    QLineEdit, QComboBox, QFrame, QSizePolicy, QDialog, 
    QDialogButtonBox, QFormLayout, QGroupBox, QCheckBox
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, QThreadPool, pyqtSlot, QPoint, QPropertyAnimation, QRect, QEasingCurve
)
from PyQt5.QtGui import QFont
# Importações relativas
from .widgets import VMWidget
from .tree_widget import VMTreeWidget
from api import ProxmoxController 
from utils.utilities import set_dark_title_bar 
from utils.config_manager import ConfigManager
from .worker import Worker, WorkerSignals 


class MainWindow(QMainWindow):
    """Main window for managing and viewing VMs and Node status."""
    
    def __init__(self, controller: ProxmoxController):
        super().__init__()
        set_dark_title_bar(self.winId())
        self.controller = controller

        # Initialize config manager
        self.config_manager = ConfigManager()
        
        # Load configurations
        configs = self.config_manager.load_configs()
        self.timer_interval = 500  # Atualização rápida (500ms = 0.5s)
        
        # Track separate API requests
        self.metrics_running = False
        self.vms_running = False
        
        self.threadpool = QThreadPool()

        node_name = self.controller.api_client.node if hasattr(self.controller.api_client, 'node') else 'N/A'
        self.setWindowTitle(f"ProxManager - Node: {node_name}")
        
        self.setStyleSheet("background-color: #1E1E1E; color: white;") 
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout: sidebar + content
        main_horizontal_layout = QHBoxLayout(central_widget)
        main_horizontal_layout.setContentsMargins(0, 0, 0, 0)
        main_horizontal_layout.setSpacing(0)
        
        # Create sidebar
        self.setup_sidebar()
        main_horizontal_layout.addWidget(self.sidebar)
        
        # Create content area with vertical layout
        content_widget = QWidget()
        self.main_layout = QVBoxLayout(content_widget)
        main_horizontal_layout.addWidget(content_widget)

        # Filter variables
        self.current_search_text = ""
        self.current_status_filter = "ALL"
        self.unfiltered_vms_list = []  # Store original VM list
        
        # Search menu state
        self.search_expanded = False  # Start collapsed
        self.search_animation = None

        self.setup_header()
        self.setup_tree_view()
        self.setup_footer() 
        
        # Load geometry after all UI is setup (delayed to ensure proper rendering)
        QTimer.singleShot(50, self.load_geometry)
        
        # Don't call initial_load here - it will be called from LoginWindow
        
        # Single timer for all updates - waits for API response
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.run_update_in_thread)
        self.timer.start(self.timer_interval) 

    # --------------------------------------------------------------------------
    # --- Métodos de Threading
    # --------------------------------------------------------------------------

    def initial_load(self):
        """Loads the dashboard for the first time synchronously."""
        try:
            # Load metrics first (usually faster)
            try:
                node_data = self.controller.api_client.get_node_status()
                if node_data:
                    self.update_node_metrics(node_data)
            except Exception:
                pass  # Continue even if metrics fail
            
            # Load VMs list
            try:
                vms_list = self.get_vms_only()
                if vms_list:
                    self.update_vms_widgets(vms_list)
            except Exception:
                pass  # Continue even if VMs fail
                
        except Exception as e:
            QMessageBox.critical(self, "Falha na Conexão Inicial", 
                                 f"Não foi possível conectar ou carregar dados do Proxmox.\n\nDetalhes: {e}", 
                                 QMessageBox.Ok)
            
    def run_update_in_thread(self):
        """Starts separate updates for metrics and VMs - updates as they respond."""
        import time
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] run_update_in_thread chamado")
        
        # Start metrics update if not already running
        if not self.metrics_running:
            self.metrics_running = True
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] Iniciando worker de métricas...")
            metrics_worker = Worker(self.controller.api_client.get_node_status)
            metrics_worker.signals.result.connect(self.handle_metrics_result)
            metrics_worker.signals.error.connect(self.handle_metrics_error)
            self.threadpool.start(metrics_worker)
        else:
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] Métricas ainda rodando, pulando...")
        
        # Start VMs update if not already running - USANDO PROGRESSIVE WORKER
        if not self.vms_running:
            self.vms_running = True
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] Iniciando ProgressiveVMWorker...")
            
            from .worker import ProgressiveVMWorker
            vms_worker = ProgressiveVMWorker(self.controller.api_client)
            vms_worker.signals.progress.connect(self.handle_vm_progress)
            vms_worker.signals.finished.connect(self.handle_vms_finished)
            vms_worker.signals.error.connect(self.handle_vms_error)
            self.threadpool.start(vms_worker)
        else:
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] VMs ainda rodando, pulando...")

    @pyqtSlot(object)
    def handle_update_result(self, result: Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]):
        """ Recebe o resultado da thread, atualiza a GUI e reinicia o timer. """
        
        if result and isinstance(result, tuple) and len(result) == 2:
            node_data, vms_list = result
            self.update_gui_with_data(node_data, vms_list)

        # Restart timer after response is processed
        self.timer.start(self.timer_interval)

    @pyqtSlot(object)
    def handle_metrics_result(self, result):
        """Handle metrics response - update immediately"""
        import time
        start_time = time.time()
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] handle_metrics_result recebido")
        
        if result:
            self.update_node_metrics(result)
        
        elapsed = (time.time() - start_time) * 1000
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] Métricas atualizadas em {elapsed:.2f}ms")
        self.metrics_running = False

    @pyqtSlot(tuple)
    def handle_metrics_error(self, error):
        """Handle metrics error"""
        import time
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] handle_metrics_error: {error}")
        self.metrics_running = False

    @pyqtSlot(object)
    def handle_vms_result(self, result):
        """Handle VMs response - update immediately"""
        import time
        start_time = time.time()
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] handle_vms_result recebido com {len(result) if result else 0} VMs")
        
        if result:
            self.update_vms_widgets(result)
        
        elapsed = (time.time() - start_time) * 1000
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] VMs atualizadas em {elapsed:.2f}ms")
        self.vms_running = False
    
    @pyqtSlot(object)
    def handle_vm_progress(self, vm_data):
        """Handle individual VM as it becomes ready (progressive update)"""
        import time
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] handle_vm_progress: VM {vm_data.get('vmid')} recebida")
        
        # Adiciona ou atualiza a VM na lista
        vmid = vm_data.get('vmid')
        
        # Atualiza a lista não filtrada
        found = False
        for i, vm in enumerate(self.unfiltered_vms_list):
            if vm.get('vmid') == vmid:
                self.unfiltered_vms_list[i] = vm_data
                found = True
                break
        
        if not found:
            self.unfiltered_vms_list.append(vm_data)
        
        # Atualiza a UI imediatamente para esta VM
        self.tree_widget.update_single_vm(vm_data)
        
        # Atualiza contadores
        self.update_vm_counts()
    
    @pyqtSlot()
    def handle_vms_finished(self):
        """Called when all VMs have been loaded"""
        import time
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] handle_vms_finished: Todas as VMs carregadas")
        self.vms_running = False
    
    def update_vm_counts(self):
        """Update VM counts in footer"""
        online_count = sum(1 for vm in self.unfiltered_vms_list if vm.get('status') == 'running')
        offline_count = sum(1 for vm in self.unfiltered_vms_list if vm.get('status') != 'running')
        
        if hasattr(self, 'vm_counts'):
            try:
                vm_text = f"VMs: <span style='color: #4CAF50;'>{online_count} online</span>, <span style='color: #F44336;'>{offline_count} offline</span>"
                self.vm_counts.setText(vm_text)
                
                # Update status dot
                if hasattr(self, 'status_dot'):
                    if online_count > 0:
                        dot_color = "#4CAF50"
                    elif offline_count > 0:
                        dot_color = "#F44336"
                    else:
                        dot_color = "#666666"
                    
                    self.status_dot.setStyleSheet(f"""
                        QLabel {{
                            color: {dot_color};
                            font-size: 10pt;
                        }}
                    """)
            except RuntimeError:
                pass

    @pyqtSlot(tuple)
    def handle_vms_error(self, error):
        """Handle VMs error"""
        self.vms_running = False

    def get_vms_only(self):
        """Get only VMs list with detailed status"""
        import time
        start_time = time.time()
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] get_vms_only iniciado")
        
        updated_vms_list = []
        try:
            # Get basic VMs list
            api_start = time.time()
            vms_list = self.controller.api_client.get_vms_list()
            api_elapsed = (time.time() - api_start) * 1000
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] get_vms_list() levou {api_elapsed:.2f}ms")
            
            if vms_list:
                vm_count = len(vms_list)
                print(f"[DEBUG {time.strftime('%H:%M:%S')}] Processando {vm_count} VMs...")
                
                for idx, vm in enumerate(vms_list, 1):
                    vm_start = time.time()
                    vmid = vm.get('vmid')
                    vm_type = vm.get('type')
                    
                    if vmid is None or vm_type is None:
                        continue 
                    
                    # Get detailed status for each VM
                    status_start = time.time()
                    detailed_status = self.controller.api_client.get_vm_current_status(vmid, vm_type)
                    status_elapsed = (time.time() - status_start) * 1000
                    
                    if detailed_status:
                        vm.update(detailed_status)
                    
                    # Busca ostype e vga (display type) da configuração da VM
                    config_start = time.time()
                    vm_config = self.controller.api_client.get_vm_config(vmid, vm_type)
                    config_elapsed = (time.time() - config_start) * 1000
                    
                    if vm_config:
                        if 'ostype' in vm_config:
                            vm['ostype'] = vm_config['ostype']
                        if 'vga' in vm_config:
                            vm['vga'] = vm_config['vga']
                    
                    # Busca informações de rede (IP addresses) apenas se a VM estiver rodando
                    ip_elapsed = 0
                    if vm.get('status') == 'running':
                        try:
                            ip_start = time.time()
                            ip_addresses = self.controller.api_client.get_vm_network_info(vmid, vm_type)
                            ip_elapsed = (time.time() - ip_start) * 1000
                            vm['ip_addresses'] = ip_addresses
                        except Exception as e:
                            vm['ip_addresses'] = []
                    else:
                        vm['ip_addresses'] = []
                    
                    vm_elapsed = (time.time() - vm_start) * 1000
                    print(f"[DEBUG {time.strftime('%H:%M:%S')}] VM {vmid} ({idx}/{vm_count}): status={status_elapsed:.0f}ms, config={config_elapsed:.0f}ms, ip={ip_elapsed:.0f}ms, total={vm_elapsed:.0f}ms")
                    
                    updated_vms_list.append(vm)
            
            total_elapsed = (time.time() - start_time) * 1000
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] get_vms_only concluído em {total_elapsed:.2f}ms")
            return updated_vms_list
            
        except Exception as e:
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] ERRO em get_vms_only: {e}")
            raise e

    @pyqtSlot(tuple)
    def thread_error(self, error: Tuple[type, BaseException, str]):
        """ Lida com erros da API que ocorreram na thread e reinicia o timer. """
        exctype, value, traceback_str = error
        
        QMessageBox.critical(self.centralWidget(), "Falha na Atualização (Thread)", 
                             f"Não foi possível atualizar o Proxmox.\n\nDetalhes do Erro: {value}", 
                             QMessageBox.Ok)
        
        # Restart timer even on error
        self.timer.start(self.timer_interval)

    def pause_timer(self):
        """Pauses the update timer during drag operations"""
        self.timer.stop()

    def resume_timer(self):
        """Resumes the update timer after drag operations"""
        self.timer.start(self.timer_interval)

    # --------------------------------------------------------------------------
    # --- Filter Methods
    # --------------------------------------------------------------------------
    
    def on_search_changed(self, text: str):
        """Called when search text changes"""
        self.current_search_text = text.strip().lower()
        self.apply_filters()
    
    def on_status_filter_changed(self, status: str):
        """Called when status filter changes"""
        self.current_status_filter = status
        self.apply_filters()
    
    def has_active_filters(self) -> bool:
        """Check if any filters are currently active"""
        return (
            bool(self.current_search_text) or 
            self.current_status_filter != "ALL"
        )
    
    def clear_filters(self):
        """Clears all filters"""
        self.search_field.clear()
        self.status_combo.setCurrentText("ALL")
        self.current_search_text = ""
        self.current_status_filter = "ALL"
        self.apply_filters()

    def toggle_search_menu(self):
        """Toggle search menu visibility with animation"""
        if self.search_animation and self.search_animation.state() == QPropertyAnimation.Running:
            return
        
        # Create animation for the entire filter container
        self.search_animation = QPropertyAnimation(self.filter_container, b"maximumHeight")
        self.search_animation.setDuration(300)
        self.search_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        if self.search_expanded:
            # Collapse - hide entire container
            self.search_animation.setStartValue(self.filter_container.height())
            self.search_animation.setEndValue(0)
            # Atualiza estilo do botão sidebar para indicar estado inativo
            self.search_sidebar_btn.setStyleSheet(self._get_sidebar_icon_style())
            self.search_expanded = False
        else:
            # Expand - show entire container
            self.filter_container.setMaximumHeight(16777215)  # Reset max height
            target_height = self.filter_container.sizeHint().height()
            self.search_animation.setStartValue(0)
            self.search_animation.setEndValue(target_height)
            # Atualiza estilo do botão sidebar para indicar estado ativo
            self.search_sidebar_btn.setStyleSheet(self._get_sidebar_icon_style(active=True))
            self.search_expanded = True
        
        self.search_animation.start()
    
    def apply_filters(self):
        """Applies current filters to the VM list"""
        if not self.unfiltered_vms_list:
            return
        
        filtered_vms = []
        
        for vm in self.unfiltered_vms_list:
            # Apply search filter
            vm_name = vm.get('name', '').lower()
            vm_id = str(vm.get('vmid', ''))
            
            search_match = (
                not self.current_search_text or 
                self.current_search_text in vm_name or
                self.current_search_text in vm_id
            )
            
            # Apply status filter
            vm_status = vm.get('status', 'unknown').upper()
            status_match = (
                self.current_status_filter == "ALL" or
                (self.current_status_filter == "RUNNING" and vm_status == "RUNNING") or
                (self.current_status_filter == "STOPPED" and vm_status != "RUNNING")
            )
            
            if search_match and status_match:
                filtered_vms.append(vm)
        
        # Update results count
        total_count = len(self.unfiltered_vms_list)
        filtered_count = len(filtered_vms)
        if filtered_count == total_count:
            self.results_label.setText(f"{total_count} servers")
        else:
            self.results_label.setText(f"{filtered_count} of {total_count} servers")
        
        # Update tree with filtered data
        # If filters are active, expand groups that contain results
        self.tree_widget.update_tree(filtered_vms, expand_groups_with_results=self.has_active_filters())

    # --------------------------------------------------------------------------
    # --- Dashboard Methods
    # --------------------------------------------------------------------------

    def update_gui_with_data(self, node_data: Optional[Dict[str, Any]], vms_list: Optional[List[Dict[str, Any]]]):
        """ Função central para atualizar a GUI após a thread ter coletado os dados. """
        self.update_node_metrics(node_data)
        self.update_vms_widgets(vms_list)


    def update_node_metrics(self, status_data: Optional[Dict[str, Any]]):
        """ Atualiza as métricas do Node usando dados fornecidos. """
        import time
        start_time = time.time()
        
        # Check if widgets still exist
        if not hasattr(self, 'system_metrics') or not self.system_metrics:
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] update_node_metrics: widget não existe")
            return
            
        try:
            if not status_data:
                self.system_metrics.setText("CPU: -- | RAM: --")
                print(f"[DEBUG {time.strftime('%H:%M:%S')}] update_node_metrics: sem dados")
                return
                
            cpu_usage = status_data.get('cpu', 0.0) * 100
            
            mem_total = status_data.get('memory', {}).get('total', 0)
            mem_used = status_data.get('memory', {}).get('used', 0)
            
            if mem_total > 0:
                mem_percent = (mem_used / mem_total) * 100
                mem_used_gb = mem_used / (1024**3)
                mem_total_gb = mem_total / (1024**3)
                mem_str = f"{mem_percent:.0f}% ({mem_used_gb:.1f}/{mem_total_gb:.1f}GB)"
            else:
                mem_str = "--"
                mem_percent = 0

            # Define colors based on usage
            cpu_color = "#4CAF50" if cpu_usage < 70 else "#FF9800" if cpu_usage < 90 else "#F44336"
            ram_color = "#4CAF50" if mem_percent < 70 else "#FF9800" if mem_percent < 90 else "#F44336"

            # Update the compact metrics display with colors
            metrics_html = f"<span style='color: #CCCCCC;'>CPU:</span> <span style='color: {cpu_color};'>{cpu_usage:.0f}%</span> <span style='color: #666;'>|</span> <span style='color: #CCCCCC;'>RAM:</span> <span style='color: {ram_color};'>{mem_str}</span>"
            self.system_metrics.setText(metrics_html)
            
            elapsed = (time.time() - start_time) * 1000
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] update_node_metrics concluído em {elapsed:.2f}ms")
            
        except RuntimeError:
            # Widget was deleted, ignore the update
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] update_node_metrics: RuntimeError (widget deletado)")
            pass


    def update_vms_widgets(self, vms_list: Optional[List[Dict[str, Any]]]):
        """Updates VM tree with status count and applies filters"""
        import time
        start_time = time.time()
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] update_vms_widgets iniciado com {len(vms_list) if vms_list else 0} VMs")
        
        if not vms_list:
            if hasattr(self, 'vm_counts'):
                try:
                    vm_text = "VMs: <span style='color: #4CAF50;'>0 online</span>, <span style='color: #F44336;'>0 offline</span>"
                    self.vm_counts.setText(vm_text)
                    
                    # Set status dot to gray when no VMs
                    if hasattr(self, 'status_dot'):
                        self.status_dot.setStyleSheet("""
                            QLabel {
                                color: #666666;
                                font-size: 10pt;
                            }
                        """)
                except RuntimeError:
                    pass
            self.unfiltered_vms_list = []
            self.apply_filters()
            print(f"[DEBUG {time.strftime('%H:%M:%S')}] update_vms_widgets: sem VMs")
            return

        # Store unfiltered list for filter operations
        self.unfiltered_vms_list = vms_list.copy()

        # Count online and offline VMs (from unfiltered data)
        online_count = 0
        offline_count = 0
        
        for vm in vms_list:
            if vm.get('status') == 'running':
                online_count += 1
            else:
                offline_count += 1
        
        # Update VM counts in footer with colors and status dot
        if hasattr(self, 'vm_counts'):
            try:
                vm_text = f"VMs: <span style='color: #4CAF50;'>{online_count} online</span>, <span style='color: #F44336;'>{offline_count} offline</span>"
                self.vm_counts.setText(vm_text)
                
                # Update status dot color based on VMs status
                if hasattr(self, 'status_dot'):
                    if online_count > 0:
                        dot_color = "#4CAF50"  # Green if any VMs online
                    elif offline_count > 0:
                        dot_color = "#F44336"  # Red if only offline VMs
                    else:
                        dot_color = "#666666"  # Gray if no VMs
                    
                    self.status_dot.setStyleSheet(f"""
                        QLabel {{
                            color: {dot_color};
                            font-size: 10pt;
                        }}
                    """)
            except RuntimeError:
                pass
        
        # Apply filters (this will update the tree)
        filter_start = time.time()
        self.apply_filters()
        filter_elapsed = (time.time() - filter_start) * 1000
        
        total_elapsed = (time.time() - start_time) * 1000
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] update_vms_widgets concluído: apply_filters={filter_elapsed:.2f}ms, total={total_elapsed:.2f}ms")


    # --------------------------------------------------------------------------
    # --- Setup Methods
    # --------------------------------------------------------------------------

    def setup_header(self):
        title_label = QLabel("Servers")
        title_label.setFont(QFont("Arial", 18, QFont.Bold)) 
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #00A3CC; margin-bottom: 10px; padding: 5px;") 
        self.main_layout.addWidget(title_label)

    def setup_tree_view(self):
        """Configures the tree widget for VM groups"""
        # Add filters before the tree
        self.setup_filters()
        
        self.tree_widget = VMTreeWidget(self.controller)
        self.tree_widget.vm_action_performed.connect(self.run_update_in_thread)
        
        # Connect drag signals to pause/resume timer
        self.tree_widget.drag_started.connect(self.pause_timer)
        self.tree_widget.drag_finished.connect(self.resume_timer)
        
        self.main_layout.addWidget(self.tree_widget)

    def setup_filters(self):
        """Sets up the filter controls above the tree"""
        # Container for filters
        self.filter_container = QFrame()
        self.filter_container.setStyleSheet("""
            QFrame {
                background-color: #2D2D2D;
                border-radius: 6px;
                margin: 5px;
                padding: 5px;
            }
        """)
        filter_layout = QHBoxLayout(self.filter_container)
        filter_layout.setContentsMargins(10, 8, 10, 8)
        

        
        # Search field
        search_label = QLabel("🔍 Search:")
        search_label.setStyleSheet("color: white; font-weight: bold; font-size: 10pt;")
        filter_layout.addWidget(search_label)
        
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Type VM name to search...")
        self.search_field.setStyleSheet("""
            QLineEdit {
                background-color: #383838;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                color: white;
                font-size: 10pt;
                min-width: 200px;
            }
            QLineEdit:focus {
                border: 1px solid #4A90E2;
                background-color: #404040;
            }
        """)
        self.search_field.textChanged.connect(self.on_search_changed)
        filter_layout.addWidget(self.search_field)
        
        filter_layout.addSpacing(20)
        
        # Status filter
        status_label = QLabel("📊 Status:")
        status_label.setStyleSheet("color: white; font-weight: bold; font-size: 10pt;")
        filter_layout.addWidget(status_label)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["ALL", "RUNNING", "STOPPED"])
        self.status_combo.setStyleSheet("""
            QComboBox {
                background-color: #383838;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                color: white;
                font-size: 10pt;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #CCCCCC;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #383838;
                border: 1px solid #555555;
                selection-background-color: #4A90E2;
                color: white;
            }
        """)
        self.status_combo.currentTextChanged.connect(self.on_status_filter_changed)
        filter_layout.addWidget(self.status_combo)
        
        # Clear filters button
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF6B6B;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                color: white;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #FF5252;
            }
            QPushButton:pressed {
                background-color: #E53935;
            }
        """)
        clear_btn.clicked.connect(self.clear_filters)
        filter_layout.addWidget(clear_btn)
        
        filter_layout.addStretch()
        
        # Results count
        self.results_label = QLabel()
        self.results_label.setStyleSheet("color: #888888; font-size: 9pt;")
        filter_layout.addWidget(self.results_label)
        
        self.main_layout.addWidget(self.filter_container)
        
        # Initialize search menu as collapsed
        self.filter_container.setMaximumHeight(0)

    def setup_footer(self):
        """Clean and minimal footer"""
        footer_container = QWidget()
        footer_container.setFixedHeight(28)
        footer_container.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                border-top: 1px solid #333333;
            }
        """)
        
        footer_layout = QHBoxLayout(footer_container)
        footer_layout.setContentsMargins(16, 4, 16, 4)
        footer_layout.setSpacing(0)
        
        # Left side: Status
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        
        # Status dot (will change color based on VMs status)
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 10pt;
            }
        """)
        
        # VM counts
        self.vm_counts = QLabel("VMs: 0 online, 0 offline")
        self.vm_counts.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 8pt;
                margin-left: 8px;
            }
        """)
        
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.vm_counts)
        
        footer_layout.addWidget(status_container)
        footer_layout.addStretch()
        
        # Center: System metrics (compact)
        self.system_metrics = QLabel("CPU: -- | RAM: --")
        self.system_metrics.setStyleSheet("""
            QLabel {
                color: #999999;
                font-size: 8pt;
                font-family: 'Segoe UI', 'Consolas', monospace;
            }
        """)
        
        footer_layout.addWidget(self.system_metrics)
        footer_layout.addStretch()
        
        # Right side: Copyright
        current_year = datetime.datetime.now().year
        copyright_text = f"© {current_year} <a href='https://github.com/pauloswear/proxmanager' style='color: #00A3CC; text-decoration: none;'>Paulo Henrique</a>"
        copyright_label = QLabel(copyright_text)
        copyright_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 8pt;
            }
        """)
        copyright_label.setOpenExternalLinks(True)
        
        footer_layout.addWidget(copyright_label)
        self.main_layout.addWidget(footer_container)



    # --------------------------------------------------------------------------
    # --- Utility Methods
    # --------------------------------------------------------------------------

    def load_geometry(self):
        configs = self.config_manager.load_configs()
        window_config = configs.get('window', {})
        
        # Set size from saved config or defaults
        width = window_config.get('width', 1200)
        height = window_config.get('height', 800)
        
        # Apply size and center the window
        self.resize(width, height)
        self.center()
        
        # Handle maximized state
        if window_config.get('maximized', False):
            self.showMaximized()
            
    def closeEvent(self, event):
        # Save window configuration
        try:
            configs = self.config_manager.load_configs()
            
            # Save only size and maximized state
            configs['window'] = {
                'width': self.size().width(),
                'height': self.size().height(),
                'maximized': self.isMaximized()
            }
            
            self.config_manager.save_configs(configs)
        except Exception as e:
            pass  # Silently ignore config save errors
        
        event.accept()

    def center(self): 
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def setup_sidebar(self):
        """Creates a compact sidebar with icon-only buttons"""
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(60)
        self.sidebar.setStyleSheet("""
            QWidget {
                background-color: #2D2D2D;
                border-right: 1px solid #404040;
            }
        """)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(5, 8, 5, 8)
        sidebar_layout.setSpacing(6)
        
        # Logo icon
        logo_btn = QPushButton("🚀")
        logo_btn.setStyleSheet(self._get_sidebar_icon_style(logo=True))
        logo_btn.setEnabled(False)
        logo_btn.setToolTip("ProxManager")
        sidebar_layout.addWidget(logo_btn)
        
        # Separator
        separator = QFrame()
        separator.setFrameStyle(QFrame.HLine)
        separator.setStyleSheet("color: #404040; margin: 5px 0;")
        sidebar_layout.addWidget(separator)
        
        # Dashboard button (current page)
        dashboard_btn = QPushButton("🏠")
        dashboard_btn.setStyleSheet(self._get_sidebar_icon_style(active=True))
        dashboard_btn.setEnabled(False)
        dashboard_btn.setToolTip("Dashboard")
        sidebar_layout.addWidget(dashboard_btn)
        
        # Search toggle button (starts inactive since menu is collapsed by default)
        self.search_sidebar_btn = QPushButton("🔍")
        self.search_sidebar_btn.setStyleSheet(self._get_sidebar_icon_style())
        self.search_sidebar_btn.setToolTip("Toggle Search Menu")
        self.search_sidebar_btn.clicked.connect(self.toggle_search_menu)
        sidebar_layout.addWidget(self.search_sidebar_btn)
        
        # Add spacer
        sidebar_layout.addStretch()
        
        # Settings button
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setStyleSheet(self._get_sidebar_icon_style())
        self.settings_btn.clicked.connect(self.show_settings)
        self.settings_btn.setToolTip("Configurations")
        sidebar_layout.addWidget(self.settings_btn)
        
        # Node Restart button
        self.node_restart_btn = QPushButton("♻️")
        self.node_restart_btn.setStyleSheet(self._get_sidebar_icon_style(warning=True))
        self.node_restart_btn.clicked.connect(self.on_node_restart_clicked)
        self.node_restart_btn.setToolTip("Restart Node")
        sidebar_layout.addWidget(self.node_restart_btn)
        
        # Node Shutdown button
        self.node_shutdown_btn = QPushButton("🛑")
        self.node_shutdown_btn.setStyleSheet(self._get_sidebar_icon_style(danger=True))
        self.node_shutdown_btn.clicked.connect(self.on_node_shutdown_clicked)
        self.node_shutdown_btn.setToolTip("Shutdown Node")
        sidebar_layout.addWidget(self.node_shutdown_btn)
        
        # Logout button
        self.logout_btn = QPushButton("🚪")
        self.logout_btn.setStyleSheet(self._get_sidebar_icon_style(logout=True))
        self.logout_btn.clicked.connect(self.logout)
        self.logout_btn.setToolTip("Logout")
        sidebar_layout.addWidget(self.logout_btn)

    def _get_sidebar_icon_style(self, active=False, logout=False, logo=False, warning=False, danger=False):
        """Returns the stylesheet for sidebar icon buttons"""
        if logo:
            return """
                QPushButton {
                    background-color: transparent;
                    color: #00A3CC;
                    border: none;
                    padding: 6px;
                    text-align: center;
                    border-radius: 6px;
                    font-size: 16px;
                    font-weight: bold;
                    min-width: 32px;
                    min-height: 32px;
                }
            """
        elif active:
            return """
                QPushButton {
                    background-color: #00A3CC;
                    color: white;
                    border: none;
                    padding: 6px;
                    text-align: center;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                    min-width: 32px;
                    min-height: 32px;
                }
            """
        elif logout:
            return """
                QPushButton {
                    background-color: transparent;
                    color: #DC3545;
                    border: 1px solid #DC3545;
                    padding: 6px;
                    text-align: center;
                    border-radius: 6px;
                    font-size: 14px;
                    min-width: 32px;
                    min-height: 32px;
                }
                QPushButton:hover {
                    background-color: #DC3545;
                    color: white;
                }
                QPushButton:pressed {
                    background-color: #B52D37;
                }
            """
        elif warning:
            return """
                QPushButton {
                    background-color: transparent;
                    color: #FFC107;
                    border: none;
                    padding: 6px;
                    text-align: center;
                    border-radius: 6px;
                    font-size: 14px;
                    min-width: 32px;
                    min-height: 32px;
                }
                QPushButton:hover {
                    background-color: #555555;
                }
                QPushButton:pressed {
                    background-color: #444444;
                }
            """
        elif danger:
            return """
                QPushButton {
                    background-color: transparent;
                    color: #DC3545;
                    border: none;
                    padding: 6px;
                    text-align: center;
                    border-radius: 6px;
                    font-size: 14px;
                    min-width: 32px;
                    min-height: 32px;
                }
                QPushButton:hover {
                    background-color: #555555;
                }
                QPushButton:pressed {
                    background-color: #444444;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: transparent;
                    color: #CCCCCC;
                    border: none;
                    padding: 6px;
                    text-align: center;
                    border-radius: 6px;
                    font-size: 14px;
                    min-width: 32px;
                    min-height: 32px;
                }
                QPushButton:hover {
                    background-color: #404040;
                    color: white;
                }
                QPushButton:pressed {
                    background-color: #505050;
                }
            """

    # --------------------------------------------------------------------------
    # --- Métodos de Controle do Node
    # --------------------------------------------------------------------------
    
    def on_node_restart_clicked(self):
        reply = QMessageBox.question(self, 'Confirmação de Restart',
            "Tem certeza que deseja REINICIAR o Node?\nIsso afetará todas as VMs!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            success = self.controller.api_client.restart_node()
            if success:
                QMessageBox.information(self, "Restart Iniciado", "Comando de restart enviado. O Node ficará inacessível.", QMessageBox.Ok)
            else:
                QMessageBox.critical(self, "Erro de API", "ERRO ao tentar reiniciar o Node.", QMessageBox.Ok)
            
    def on_node_shutdown_clicked(self):
        reply = QMessageBox.question(self, 'Confirmação de Shutdown',
            "Tem certeza que deseja DESLIGAR o Node?\nIsso afetará todas as VMs!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success = self.controller.api_client.shutdown_node()
            if success:
                QMessageBox.information(self, "Shutdown Iniciado", "Comando de shutdown enviado. O Node será desligado.", QMessageBox.Ok)
            else:
                QMessageBox.critical(self, "Erro de API", "ERRO ao tentar desligar o Node.", QMessageBox.Ok)

    # --------------------------------------------------------------------------
    # --- Métodos do Sidebar
    # --------------------------------------------------------------------------

    def logout(self):
        """Logout and return to login window"""
        reply = QMessageBox.question(
            self, "Logout", 
            "Tem certeza que deseja fazer logout?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Stop the timer
            if hasattr(self, 'timer') and self.timer:
                self.timer.stop()
            
            # Clear any stored credentials if auto_login is disabled
            login_data = self.config_manager.load_login_data()
            if not login_data.get('auto_login', False):
                login_data['password'] = ""
                self.config_manager.save_login_data(login_data)
            
            # Close this window and show login
            self.close()
            
            # Import and show login window
            from .login_window import LoginWindow
            self.login_window = LoginWindow()
            self.login_window.show()

    def show_settings(self):
        """Show settings dialog"""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGroupBox, QCheckBox, 
                                   QDialogButtonBox, QFormLayout, QSpinBox, QLabel)
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Configurations")
        dialog.setFixedSize(350, 200)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2D2D2D;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555555;
                border-radius: 5px;
                margin-top: 5px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #CCCCCC;
            }
            QCheckBox {
                color: #CCCCCC;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555555;
                background-color: #383838;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #00A3CC;
                background-color: #00A3CC;
                border-radius: 3px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        # Load current configurations
        configs = self.config_manager.load_configs()
        
        # SPICE GroupBox
        spice_group = QGroupBox("SPICE")
        spice_layout = QFormLayout(spice_group)
        
        # Start fullscreen checkbox
        self.fullscreen_check = QCheckBox()
        self.fullscreen_check.setChecked(configs.get('spice_fullscreen', False))
        spice_layout.addRow("Start fullscreen:", self.fullscreen_check)
        
        # Auto resize checkbox
        self.autoresize_check = QCheckBox()
        self.autoresize_check.setChecked(configs.get('spice_autoresize', False))
        spice_layout.addRow("Auto resize:", self.autoresize_check)
        
        # Kiosk mode checkbox
        self.kiosk_check = QCheckBox()
        self.kiosk_check.setChecked(configs.get('spice_kiosk', False))
        spice_layout.addRow("Kiosk mode:", self.kiosk_check)
        
        # SmartCard checkbox
        self.smartcard_check = QCheckBox()
        self.smartcard_check.setChecked(configs.get('spice_smartcard', True))
        spice_layout.addRow("SmartCard:", self.smartcard_check)
        
        # USB Redirect checkbox
        self.usbredirect_check = QCheckBox()
        self.usbredirect_check.setChecked(configs.get('spice_usbredirect', True))
        spice_layout.addRow("USB Redirect:", self.usbredirect_check)
        
        # Fluidity mode combo box
        self.fluidity_combo = QComboBox()
        self.fluidity_combo.addItems(["balanced", "performance", "quality"])
        current_fluidity = configs.get('spice_fluidity_mode', 'balanced')
        self.fluidity_combo.setCurrentText(current_fluidity)
        spice_layout.addRow("Fluidity:", self.fluidity_combo)
        

        layout.addWidget(spice_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, dialog
        )
        buttons.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #555555;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        layout.addWidget(buttons)
        
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        if dialog.exec_() == QDialog.Accepted:
            # Save SPICE settings
            configs['spice_fullscreen'] = self.fullscreen_check.isChecked()
            configs['spice_autoresize'] = self.autoresize_check.isChecked()
            configs['spice_kiosk'] = self.kiosk_check.isChecked()
            configs['spice_fluidity_mode'] = self.fluidity_combo.currentText()
            configs['spice_smartcard'] = self.smartcard_check.isChecked()
            configs['spice_usbredirect'] = self.usbredirect_check.isChecked()
            self.config_manager.save_configs(configs)
            
            QMessageBox.information(self, "Configurations", "Configs saved!", QMessageBox.Ok)