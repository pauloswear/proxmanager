import datetime
from typing import Dict, Any, List, Optional, Tuple
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QDesktopWidget, QPushButton, QMessageBox, 
    QLineEdit, QComboBox, QFrame, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, QThreadPool, pyqtSlot, QPoint
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
        self.timer_interval = configs.get('timer_interval', 300)
        
        self.threadpool = QThreadPool()

        node_name = self.controller.api_client.node if hasattr(self.controller.api_client, 'node') else 'N/A'
        self.setWindowTitle(f"ProxManager - Node: {node_name}")
        
        self.load_geometry() 
        
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

        self.setup_header()
        self.setup_tree_view()
        self.setup_footer() 
        
        self.initial_load()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.run_update_in_thread)
        self.timer.start(self.timer_interval) 

    # --------------------------------------------------------------------------
    # --- Métodos de Threading
    # --------------------------------------------------------------------------

    def initial_load(self):
        """Loads the dashboard for the first time synchronously."""
        try:
            # Aqui é síncrono para garantir que a UI não comece vazia.
            node_data, vms_list = self.controller.update_dashboard()
            self.update_gui_with_data(node_data, vms_list)
        except Exception as e:
            QMessageBox.critical(self, "Falha na Conexão Inicial", 
                                 f"Não foi possível conectar ou carregar dados do Proxmox.\n\nDetalhes: {e}", 
                                 QMessageBox.Ok)
            
    def run_update_in_thread(self):
        """Starts dashboard update in a separate thread."""
        
        if self.threadpool.activeThreadCount() > 0:
             return
        
        # Stop Timer to avoid request overlap
        self.timer.stop()
             
        worker = Worker(self.controller.update_dashboard) 
        
        worker.signals.result.connect(self.handle_update_result)
        worker.signals.error.connect(self.thread_error)
        
        self.threadpool.start(worker)

    @pyqtSlot(object)
    def handle_update_result(self, result: Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]):
        """ Recebe o resultado da thread, atualiza a GUI e REINICIA o timer. """
        
        if result and isinstance(result, tuple) and len(result) == 2:
            node_data, vms_list = result
            self.update_gui_with_data(node_data, vms_list)

        # Restart Timer (cycle starts now)
        self.timer.start(self.timer_interval) 

    @pyqtSlot(tuple)
    def thread_error(self, error: Tuple[type, BaseException, str]):
        """ Lida com erros da API que ocorreram na thread e REINICIA o timer. """
        exctype, value, traceback_str = error
        
        QMessageBox.critical(self.centralWidget(), "Falha na Atualização (Thread)", 
                             f"Não foi possível atualizar o Proxmox.\n\nDetalhes do Erro: {value}", 
                             QMessageBox.Ok)
        
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
        
        if not status_data:
            self.cpu_label.setText("CPU: ERROR")
            self.mem_label.setText("RAM: ERROR")
            self.load_label.setText("Load Avg: ERROR")
            self.uptime_label.setText("Uptime: ERROR")
            return
            
        cpu_usage = status_data.get('cpu', 0.0) * 100
        
        load_avg_list = status_data.get('loadavg', [0, 0, 0])
        try:
            load_value = float(load_avg_list[0]) 
            load_avg_str = f"{load_value:.2f}"
        except (ValueError, TypeError, IndexError):
            load_avg_str = "N/A"
        
        mem_total = status_data.get('memory', {}).get('total', 0)
        mem_used = status_data.get('memory', {}).get('used', 0)
        
        if mem_total > 0:
            mem_percent = (mem_used / mem_total) * 100
            mem_used_gb = mem_used / (1024**3)
            mem_total_gb = mem_total / (1024**3)
            mem_text = f"RAM: {mem_percent:.1f}% ({mem_used_gb:.1f}/{mem_total_gb:.1f} GB)"
        else:
            mem_text = "RAM: N/A"

        uptime_seconds = status_data.get('uptime', 0)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        uptime_text = f"Uptime: {days}d {hours}h {minutes}m"
            
        self.cpu_label.setText(f"CPU: {cpu_usage:.1f}%")
        self.mem_label.setText(mem_text)
        self.load_label.setText(f"Load Avg: {load_avg_str}")
        self.uptime_label.setText(uptime_text)


    def update_vms_widgets(self, vms_list: Optional[List[Dict[str, Any]]]):
        """Updates VM tree with status count and applies filters"""
        if not vms_list:
            self.online_label.setText("🚀 Online: 0")
            self.offline_label.setText("🛑 Offline: 0")
            self.unfiltered_vms_list = []
            self.apply_filters()
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
        
        # Update status labels
        self.online_label.setText(f"🚀 Online: {online_count}")
        self.offline_label.setText(f"🛑 Offline: {offline_count}")
        
        # Apply filters (this will update the tree)
        self.apply_filters()


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
        filter_container = QFrame()
        filter_container.setStyleSheet("""
            QFrame {
                background-color: #2D2D2D;
                border-radius: 6px;
                margin: 5px;
                padding: 5px;
            }
        """)
        filter_layout = QHBoxLayout(filter_container)
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
        
        self.main_layout.addWidget(filter_container)

    def setup_footer(self):
        """ Configura o rodapé em duas linhas com melhor disposição. """
        
        footer_container = QWidget()
        footer_v_layout = QVBoxLayout(footer_container)
        # Margens e espaçamento do container principal
        footer_v_layout.setContentsMargins(10, 5, 10, 5) 
        footer_v_layout.setSpacing(5) 

        footer_style = "font-weight: bold; font-size: 9pt;" 

        # ----------------------------------------------------------------------
        # --- LINHA 1: Status e Métricas (Distribuídas Horizontalmente) ---
        # ----------------------------------------------------------------------
        
        status_metrics_widget = QWidget()
        status_metrics_layout = QHBoxLayout(status_metrics_widget)
        status_metrics_layout.setContentsMargins(0, 0, 0, 0)
        status_metrics_layout.setSpacing(20) # Aumenta o espaçamento entre grupos

        # --- GRUPO 1: Contadores (Online/Offline) - Extrema Esquerda
        
        self.online_label = QLabel()
        self.online_label.setStyleSheet("color: #28A745; " + footer_style)
        self.offline_label = QLabel()
        self.offline_label.setStyleSheet("color: #DC3545; " + footer_style)
        
        # Removendo largura fixa para permitir que o texto defina a largura, mas mantendo a disposição à esquerda
        status_metrics_layout.addWidget(self.online_label)
        status_metrics_layout.addWidget(self.offline_label)
        
        # Adiciona um separador claro
        separator_status_label = QLabel(" | ")
        separator_status_label.setStyleSheet("color: #444444; font-size: 10pt;")
        status_metrics_layout.addWidget(separator_status_label)
        
        # --- GRUPO 2: Métricas do Node (CPU, RAM, Load Avg, Uptime) - Centro

        self.cpu_label = QLabel("CPU: N/A")
        self.cpu_label.setStyleSheet("color: #00A3CC; " + footer_style)
        self.mem_label = QLabel("RAM: N/A")
        self.mem_label.setStyleSheet("color: #FFC107; " + footer_style)
        self.load_label = QLabel("Load Avg: N/A") 
        self.load_label.setStyleSheet("color: #DC3545; " + footer_style)
        self.uptime_label = QLabel("Uptime: N/A") 
        self.uptime_label.setStyleSheet("color: #999999; " + footer_style)

        # Usamos setMinimumWidth para garantir que cada métrica tenha espaço suficiente,
        # especialmente RAM, que tem mais texto (GB/GB).
        self.cpu_label.setMinimumWidth(80) 
        self.mem_label.setMinimumWidth(200) # Ajustado para acomodar o formato (X.X/Y.Y GB)
        self.load_label.setMinimumWidth(100)
        self.uptime_label.setMinimumWidth(120)

        status_metrics_layout.addWidget(self.cpu_label)
        status_metrics_layout.addWidget(self.mem_label)
        status_metrics_layout.addWidget(self.load_label)
        status_metrics_layout.addWidget(self.uptime_label)
        
        # Adiciona stretch para empurrar o copyright para a direita
        status_metrics_layout.addStretch(1) 
        
        footer_v_layout.addWidget(status_metrics_widget)

        # --- SEPARADOR HORIZONTAL (Traço) ---
        separator_line = QLabel()
        separator_line.setFixedHeight(1)
        separator_line.setStyleSheet("background-color: #333333; margin-top: 5px; margin-bottom: 5px;")
        footer_v_layout.addWidget(separator_line)
        
        
        # ----------------------------------------------------------------------
        # --- LINHA 2: CONTROLES, DEBUG e COPYRIGHT ---
        # ----------------------------------------------------------------------
        
        controls_copyright_widget = QWidget()
        controls_copyright_layout = QHBoxLayout(controls_copyright_widget)
        controls_copyright_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- GRUPO 3: Copyright (Direita) 
        controls_copyright_layout.addStretch(1) # Stretch para empurrar o copyright para a direita

        # --- GRUPO 4: Copyright (Extrema Direita)
        current_year = datetime.datetime.now().year
        copyright_text = f"<span>© {current_year} - <a href='https://github.com/pauloswear' style='color: #00A3CC; text-decoration: none;'>Paulo Henrique</a></span>"
        
        copyright_label = QLabel(copyright_text)
        copyright_label.setStyleSheet("color: #888888; font-size: 8pt;")
        copyright_label.setOpenExternalLinks(True)
        
        controls_copyright_layout.addWidget(copyright_label)
        
        footer_v_layout.addWidget(controls_copyright_widget)

        self.main_layout.addWidget(footer_container)

    # --------------------------------------------------------------------------
    # --- Utility Methods
    # --------------------------------------------------------------------------

    def load_geometry(self):
        configs = self.config_manager.load_configs()
        window_config = configs.get('window', {})
        
        width = window_config.get('width', 800)
        height = window_config.get('height', 600)
        self.resize(width, height)
        
        if window_config.get('maximized', False):
            self.showMaximized()
        else:
            self.center()
            
    def closeEvent(self, event):
        # Save window configuration
        configs = self.config_manager.load_configs()
        configs['window'] = {
            'width': self.size().width(),
            'height': self.size().height(),
            'maximized': self.isMaximized()
        }
        self.config_manager.save_configs(configs)
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
        
        # Add spacer
        sidebar_layout.addStretch()
        
        # Settings button
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setStyleSheet(self._get_sidebar_icon_style())
        self.settings_btn.clicked.connect(self.show_settings)
        self.settings_btn.setToolTip("Configurações")
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
                                   QDialogButtonBox, QFormLayout)
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Configurações")
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
            self.config_manager.save_configs(configs)
            
            QMessageBox.information(self, "Configurações", "Configurações SPICE salvas com sucesso!", QMessageBox.Ok)