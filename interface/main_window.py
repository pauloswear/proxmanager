import datetime
from typing import Dict, Any, List, Optional, Tuple
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QDesktopWidget, QPushButton, QMessageBox
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, QSettings, QThreadPool, pyqtSlot, QPoint
)
from PyQt5.QtGui import QFont
# Importações relativas
from .widgets import VMWidget
from api import ProxmoxController 
from utils.utilities import set_dark_title_bar 
from .worker import Worker, WorkerSignals 


class MainWindow(QMainWindow):
    """ Janela principal para gerenciar e visualizar as VMs e o status do Node. """
    
    vm_widgets: Dict[int, VMWidget]
    
    def __init__(self, controller: ProxmoxController):
        super().__init__()
        set_dark_title_bar(self.winId())
        self.controller = controller

        self.timer_interval = 1000 # intervalo do tempo de atualização do dash em MS
        
        self.threadpool = QThreadPool()

        node_name = self.controller.api_client.node if hasattr(self.controller.api_client, 'node') else 'N/A'
        self.setWindowTitle(f"ProxManager - Node: {node_name}")
        
        self.settings = QSettings()
        self.load_geometry() 
        
        self.setStyleSheet("background-color: #1E1E1E; color: white;") 
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        
        self.vm_widgets = {}

        self.setup_header()
        self.setup_scroll_area()
        self.setup_footer() 
        
        self.initial_load()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.run_update_in_thread)
        self.timer.start(self.timer_interval) 

    # --------------------------------------------------------------------------
    # --- Métodos de Threading
    # --------------------------------------------------------------------------

    def initial_load(self):
        """ Carrega o painel pela primeira vez de forma síncrona. """
        try:
            # Aqui é síncrono para garantir que a UI não comece vazia.
            node_data, vms_list = self.controller.update_dashboard()
            self.update_gui_with_data(node_data, vms_list)
        except Exception as e:
            QMessageBox.critical(self, "Falha na Conexão Inicial", 
                                 f"Não foi possível conectar ou carregar dados do Proxmox.\n\nDetalhes: {e}", 
                                 QMessageBox.Ok)
            
    def run_update_in_thread(self):
        """ Inicia a atualização do dashboard em uma thread separada. """
        
        if self.threadpool.activeThreadCount() > 0:
             return
        
        # Parar o Timer para evitar sobreposição de requisições
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

        # Reinicia o Timer (Ciclo de 2.5s começa agora)
        self.timer.start(self.timer_interval) 

    @pyqtSlot(tuple)
    def thread_error(self, error: Tuple[type, BaseException, str]):
        """ Lida com erros da API que ocorreram na thread e REINICIA o timer. """
        exctype, value, traceback_str = error
        
        QMessageBox.critical(self.centralWidget(), "Falha na Atualização (Thread)", 
                             f"Não foi possível atualizar o Proxmox.\n\nDetalhes do Erro: {value}", 
                             QMessageBox.Ok)
        
        self.timer.start(self.timer_interval)

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
        """ Atualiza os widgets das VMs, contagem de status e garante a ordem. """
        scroll_bar = self.scroll_area.verticalScrollBar()
        old_position = scroll_bar.value()
        
        if not vms_list:
            self.online_label.setText("🚀 Online: 0")
            self.offline_label.setText("🛑 Offline: 0")
            return

        current_vmids = {vm['vmid'] for vm in vms_list if 'vmid' in vm}
        
        # 1. Remover Widgets Obsoletos
        widgets_to_remove = []
        for vmid, widget in self.vm_widgets.items():
            if vmid not in current_vmids:
                widgets_to_remove.append(widget)
        
        for widget in widgets_to_remove:
            self.vms_layout.removeWidget(widget)
            widget.deleteLater()
            del self.vm_widgets[widget.vmid]

        # 2. Preparar Ordenação e Contagem
        online_count = 0
        offline_count = 0
        
        def sort_key(vm: Dict[str, Any]):
            status_priority = 0 if vm.get('status', 'unknown') == 'running' else 1
            return (status_priority, vm.get('name', 'z').lower())

        sorted_vms = sorted(vms_list, key=sort_key)
        
        # Limpa o layout para redesenhar na ordem correta
        while self.vms_layout.count():
            child = self.vms_layout.takeAt(0)
            if child.widget():
                pass # Apenas remove os widgets do layout, a destruição é feita acima

        # 3. Iterar, Contar e Redesenhar (ou Criar)
        for vm in sorted_vms:
            vmid = vm.get('vmid')
            if vmid is None: continue 

            if vm.get('status') == 'running':
                online_count += 1
            else:
                offline_count += 1
                
            if vmid in self.vm_widgets:
                widget = self.vm_widgets[vmid]
                widget.update_data(vm) 
                self.vms_layout.addWidget(widget) 
                
            else:
                vm_widget = VMWidget(vm, self.controller)
                vm_widget.action_performed.connect(self.run_update_in_thread) 
                self.vms_layout.addWidget(vm_widget)
                self.vm_widgets[vmid] = vm_widget
                
        # 4. Atualizar Status
        self.online_label.setText(f"🚀 Online: {online_count}")
        self.offline_label.setText(f"🛑 Offline: {offline_count}")
        
        self.scroll_content.adjustSize()
        QTimer.singleShot(0, lambda: scroll_bar.setValue(old_position))


    # --------------------------------------------------------------------------
    # --- Setup Methods
    # --------------------------------------------------------------------------

    def setup_header(self):
        title_label = QLabel("🚀 Gerenciamento de Servidores Virtuais")
        title_label.setFont(QFont("Arial", 18, QFont.Bold)) 
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #00A3CC; margin-bottom: 10px; padding: 5px;") 
        self.main_layout.addWidget(title_label)

    def setup_scroll_area(self):
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.vms_layout = QVBoxLayout(self.scroll_content)
        self.vms_layout.setAlignment(Qt.AlignTop)
        self.vms_layout.setSpacing(5) 
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #333333; border-radius: 6px; }")
        self.main_layout.addWidget(self.scroll_area)


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
        
        # --- GRUPO 3: Botões de Ação e Debug (Esquerda)
        
        self.node_restart_btn = QPushButton("♻️ RESTART NODE")
        self.node_restart_btn.setStyleSheet("""
            QPushButton { height: 25px; border-radius: 4px; font-size: 8pt; font-weight: bold; background-color: #505030; color: #FFC107; }
            QPushButton:hover { background-color: #606040; }
        """)
        self.node_restart_btn.setFixedSize(120, 25)
        self.node_restart_btn.clicked.connect(self.on_node_restart_clicked) 
        controls_copyright_layout.addWidget(self.node_restart_btn)

        self.node_shutdown_btn = QPushButton("🛑 SHUTDOWN NODE")
        self.node_shutdown_btn.setStyleSheet("""
            QPushButton { height: 25px; border-radius: 4px; font-size: 8pt; font-weight: bold; background-color: #503030; color: #DC3545; margin-left: 10px; }
            QPushButton:hover { background-color: #604040; }
        """)
        self.node_shutdown_btn.setFixedSize(130, 25)
        self.node_shutdown_btn.clicked.connect(self.on_node_shutdown_clicked) 
        controls_copyright_layout.addWidget(self.node_shutdown_btn)
        
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
        size = self.settings.value("size", QSize(800, 600))
        position = self.settings.value("pos")
        
        if size:
            self.resize(size)

        if position:
            self.move(position)
        else:
            self.resize(800, 600)
            self.center()
            
    def closeEvent(self, event):
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        event.accept()

    def center(self): 
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

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