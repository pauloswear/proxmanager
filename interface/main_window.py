import datetime
from typing import Dict, Any, List
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QDesktopWidget, QPushButton, QMessageBox
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, QSettings, QThreadPool, pyqtSlot
)
from PyQt5.QtGui import QFont
from .widgets import VMWidget
from api import ProxmoxController 
from utils.utilities import set_dark_title_bar
# ⭐️ Certifique-se que o worker.py está disponível
from .worker import Worker, WorkerSignals 


class MainWindow(QMainWindow):
    """ Janela principal para gerenciar e visualizar as VMs e o status do Node. """
    
    vm_widgets: Dict[int, VMWidget]
    
    def __init__(self, controller: ProxmoxController):
        super().__init__()
        set_dark_title_bar(self.winId())
        self.controller = controller
        
        self.threadpool = QThreadPool()
        print(f"Multithreading com {self.threadpool.maxThreadCount()} threads.")

        node_name = self.controller.api_client.node if hasattr(self.controller.api_client, 'node') else 'N/A'
        self.setWindowTitle(f"ProxManager - Node: {node_name}")
        
        # Geometria e QSettings
        self.settings = QSettings()
        # ⭐️ ESTAVA FALTANDO AQUI: O método load_geometry precisa estar na classe.
        self.load_geometry() 
        
        self.setStyleSheet("background-color: #1E1E1E; color: white;") 
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        
        self.vm_widgets = {}

        self.setup_header()
        self.setup_scroll_area()
        # ⭐️ ESTAVA FALTANDO AQUI: O método setup_footer precisa estar na classe.
        self.setup_footer() 
        
        self.initial_load()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.run_update_in_thread)
        self.timer.start(1000) 

    # --- Métodos de Threading ---

    def initial_load(self):
        """ Carrega o painel pela primeira vez de forma síncrona. """
        node_data, vms_list = self.controller.update_dashboard()
        self.update_gui_with_data(node_data, vms_list)


    def run_update_in_thread(self):
        """ Inicia a atualização do dashboard em uma thread separada. """
        
        if self.threadpool.activeThreadCount() > 0:
             return
             
        worker = Worker(self.controller.update_dashboard) 
        
        worker.signals.result.connect(self.handle_update_result)
        worker.signals.error.connect(self.thread_error)
        
        self.threadpool.start(worker)


    @pyqtSlot(object)
    def handle_update_result(self, result):
        """ Recebe o resultado da thread e chama a atualização da GUI. """
        if result and isinstance(result, tuple) and len(result) == 2:
            node_data, vms_list = result
            self.update_gui_with_data(node_data, vms_list)
        else:
            # Isso pode ocorrer se houver um erro de API antes de retornar os dados
            print("Erro: A thread não retornou os dados esperados. (API falhou antes da coleta completa)")

    @pyqtSlot(tuple)
    def thread_error(self, error):
        """ Lida com erros da API que ocorreram na thread. """
        exctype, value, traceback_str = error
        
        # Exibe o erro de forma mais amigável
        QMessageBox.critical(self, "Falha na Atualização (Thread)", 
                             f"Não foi possível atualizar o Proxmox.\n\nDetalhes do Erro: {value}", 
                             QMessageBox.Ok)
        print(f"ERRO CRÍTICO na Thread de Atualização: {exctype.__name__}: {value}")


    # --- Setup Methods ---

    def setup_header(self):
        """ Configura o título da janela principal. """
        title_label = QLabel("🚀 Gerenciamento de Servidores Virtuais")
        title_label.setFont(QFont("Arial", 18, QFont.Bold)) 
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #00A3CC; margin-bottom: 10px; padding: 5px;") 
        self.main_layout.addWidget(title_label)

    def setup_scroll_area(self):
        """ Configura a área de rolagem para listar os widgets das VMs. """
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
        """ Configura o rodapé em duas linhas. """
        
        footer_container = QWidget()
        footer_v_layout = QVBoxLayout(footer_container)
        footer_v_layout.setContentsMargins(10, 5, 10, 5) 
        footer_v_layout.setSpacing(5) 

        footer_style = "font-weight: bold; font-size: 9pt; margin-right: 15px;"

        # --- LINHA 1: Status e Métricas ---
        status_metrics_widget = QWidget()
        status_metrics_layout = QHBoxLayout(status_metrics_widget)
        status_metrics_layout.setContentsMargins(0, 0, 0, 0)
        
        self.online_label = QLabel()
        self.online_label.setStyleSheet("color: #28A745; " + footer_style)
        self.offline_label = QLabel()
        self.offline_label.setStyleSheet("color: #DC3545; " + footer_style)
        
        self.online_label.setFixedWidth(80) 
        self.offline_label.setFixedWidth(80)

        status_metrics_layout.addWidget(self.online_label)
        status_metrics_layout.addWidget(self.offline_label)
        
        status_metrics_layout.addSpacing(10)
        separator_status_label = QLabel("|")
        separator_status_label.setStyleSheet("color: #444444; font-size: 10pt;")
        status_metrics_layout.addWidget(separator_status_label)
        status_metrics_layout.addSpacing(15)

        self.cpu_label = QLabel("CPU: N/A")
        self.cpu_label.setStyleSheet("color: #00A3CC; " + footer_style)
        self.mem_label = QLabel("RAM: N/A")
        self.mem_label.setStyleSheet("color: #FFC107; " + footer_style)
        self.load_label = QLabel("Load Avg: N/A") 
        self.load_label.setStyleSheet("color: #DC3545; " + footer_style)
        self.uptime_label = QLabel("Uptime: N/A") 
        self.uptime_label.setStyleSheet("color: #999999; " + footer_style)

        self.uptime_label.setMaximumWidth(120) 
        
        status_metrics_layout.addWidget(self.cpu_label)
        status_metrics_layout.addWidget(self.mem_label)
        status_metrics_layout.addWidget(self.load_label)
        status_metrics_layout.addWidget(self.uptime_label)

        status_metrics_layout.addStretch(1) 
        footer_v_layout.addWidget(status_metrics_widget)

        # --- SEPARADOR HORIZONTAL (Traço) ---
        separator_line = QLabel()
        separator_line.setFixedHeight(1)
        separator_line.setStyleSheet("background-color: #333333; margin-top: 5px; margin-bottom: 5px;")
        footer_v_layout.addWidget(separator_line)
        
        
        # --- LINHA 2: CONTROLES E COPYRIGHT ---
        controls_copyright_widget = QWidget()
        controls_copyright_layout = QHBoxLayout(controls_copyright_widget)
        controls_copyright_layout.setContentsMargins(0, 0, 0, 0)
        
        # Botão de Restart (ESQUERDA)
        self.node_restart_btn = QPushButton("♻️ RESTART NODE")
        self.node_restart_btn.setStyleSheet("""
            QPushButton { height: 25px; border-radius: 4px; font-size: 8pt; font-weight: bold; background-color: #505030; color: #FFC107; }
            QPushButton:hover { background-color: #606040; }
        """)
        self.node_restart_btn.setFixedSize(120, 25)
        # ⭐️ CONECTA AO NOVO MÉTODO
        self.node_restart_btn.clicked.connect(self.on_node_restart_clicked) 
        controls_copyright_layout.addWidget(self.node_restart_btn)

        # Botão de Shutdown (ESQUERDA)
        self.node_shutdown_btn = QPushButton("🛑 SHUTDOWN NODE")
        self.node_shutdown_btn.setStyleSheet("""
            QPushButton { height: 25px; border-radius: 4px; font-size: 8pt; font-weight: bold; background-color: #503030; color: #DC3545; margin-left: 10px; }
            QPushButton:hover { background-color: #604040; }
        """)
        self.node_shutdown_btn.setFixedSize(130, 25)
        # ⭐️ CONECTA AO NOVO MÉTODO
        self.node_shutdown_btn.clicked.connect(self.on_node_shutdown_clicked) 
        controls_copyright_layout.addWidget(self.node_shutdown_btn)
        
        
        controls_copyright_layout.addStretch(1) 

        current_year = datetime.datetime.now().year
        copyright_text = f"<span>© {current_year} - <a href='https://github.com/pauloswear' style='color: #00A3CC; text-decoration: none;'>Paulo Henrique</a></span>"
        
        copyright_label = QLabel(copyright_text)
        copyright_label.setStyleSheet("color: #888888; font-size: 8pt;")
        copyright_label.setOpenExternalLinks(True)
        
        controls_copyright_layout.addWidget(copyright_label)
        
        footer_v_layout.addWidget(controls_copyright_widget)

        self.main_layout.addWidget(footer_container)


    # --- Utility Methods (Reintegrados) ---

    def load_geometry(self):
        """ Carrega o tamanho e posição salvos ou define os padrões. """
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
        """ Salva o tamanho e posição da janela antes de fechar. """
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        event.accept()

    def center(self): 
        """ Centraliza a janela na tela do monitor. """
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    # --- Métodos de Controle do Node (Reintegrados) ---

    def on_node_restart_clicked(self):
        """ Executa a ação de Restart do Node (com confirmação). """
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
        """ Executa a ação de Shutdown do Node (com confirmação). """
        reply = QMessageBox.question(self, 'Confirmação de Shutdown',
            "Tem certeza que deseja DESLIGAR o Node?\nIsso afetará todas as VMs!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success = self.controller.api_client.shutdown_node()
            if success:
                QMessageBox.information(self, "Shutdown Iniciado", "Comando de shutdown enviado. O Node será desligado.", QMessageBox.Ok)
            else:
                QMessageBox.critical(self, "Erro de API", "ERRO ao tentar desligar o Node.", QMessageBox.Ok)


    # --- Dashboard Methods ---

    def update_gui_with_data(self, node_data: Dict[str, Any] | None, vms_list: List[Dict[str, Any]] | None):
        """ Função central para atualizar a GUI após a thread ter coletado os dados. """
        self.update_node_metrics(node_data)
        self.update_vms_widgets(vms_list)


    def update_node_metrics(self, status_data: Dict[str, Any] | None):
        """ Atualiza as métricas do Node usando dados fornecidos. """
        
        if not status_data:
            self.cpu_label.setText("CPU: ERROR")
            self.mem_label.setText("RAM: ERROR")
            self.load_label.setText("Load Avg: ERROR")
            self.uptime_label.setText("Uptime: ERROR")
            return
            
        # --- Uso de CPU ---
        cpu_usage = status_data.get('cpu', 0.0) * 100
        
        # --- Load Average ---
        load_avg_list = status_data.get('loadavg', [0, 0, 0])
        try:
            load_value = float(load_avg_list[0]) 
            load_avg_str = f"{load_value:.2f}"
        except (ValueError, TypeError, IndexError):
            load_avg_str = "N/A"
        
        # --- Uso de Memória (RAM) ---
        mem_total = status_data.get('memory', {}).get('total', 0)
        mem_used = status_data.get('memory', {}).get('used', 0)
        
        if mem_total > 0:
            mem_percent = (mem_used / mem_total) * 100
            mem_used_gb = mem_used / (1024**3)
            mem_total_gb = mem_total / (1024**3)
            mem_text = f"RAM: {mem_percent:.1f}% ({mem_used_gb:.1f}/{mem_total_gb:.1f} GB)"
        else:
            mem_text = "RAM: N/A"

        # --- Uptime ---
        uptime_seconds = status_data.get('uptime', 0)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        uptime_text = f"Uptime: {days}d {hours}h {minutes}m"
            
        # Atualiza os Rótulos
        self.cpu_label.setText(f"CPU: {cpu_usage:.1f}%")
        self.mem_label.setText(mem_text)
        self.load_label.setText(f"Load Avg: {load_avg_str}")
        self.uptime_label.setText(uptime_text)


    def update_vms_widgets(self, vms_list: List[Dict[str, Any]] | None):
        """ Atualiza os widgets das VMs (adiciona novos, remove obsoletos, atualiza existentes). """
        scroll_bar = self.scroll_area.verticalScrollBar()
        old_position = scroll_bar.value()
        
        if not vms_list:
            self.online_label.setText("🚀 Online: 0")
            self.offline_label.setText("🛑 Offline: 0")
            if not self.vm_widgets:
                # Se não houver VMs e a lista falhar, exibe a mensagem de erro no layout
                self.vms_layout.addWidget(QLabel("Não foi possível carregar as VMs. Tente novamente."))
            return

        current_vmids = {vm['vmid'] for vm in vms_list}
        
        # --- 1. Remover Widgets Obsoletos ---
        widgets_to_remove = []
        for vmid, widget in self.vm_widgets.items():
            if vmid not in current_vmids:
                widgets_to_remove.append(widget)
        
        for widget in widgets_to_remove:
            self.vms_layout.removeWidget(widget)
            widget.deleteLater()
            del self.vm_widgets[widget.vmid]

        # --- 2. Atualizar Existentes e Adicionar Novos ---
        online_count = 0
        offline_count = 0
        
        # Lógica de Ordenação: Running primeiro, depois por nome
        def sort_key(vm: Dict[str, Any]):
            status_priority = 0 if vm['status'] == 'running' else 1
            return (status_priority, vm['name'].lower())

        sorted_vms = sorted(vms_list, key=sort_key)
        
        # Limpar o layout e redesenhar para garantir a ordem correta
        # Nota: Uma otimização seria apenas reordenar, mas redesenhar é mais simples.
        while self.vms_layout.count():
             child = self.vms_layout.takeAt(0)
             if child.widget():
                 self.vms_layout.removeWidget(child.widget())

        for vm in sorted_vms:
            vmid = vm['vmid']
            
            if vm['status'] == 'running':
                online_count += 1
            else:
                offline_count += 1
                
            if vmid in self.vm_widgets:
                # Atualiza Widget Existente
                widget = self.vm_widgets[vmid]
                widget.update_data(vm)
                self.vms_layout.addWidget(widget) # Adiciona ao layout na ordem correta
                
            else:
                # Adiciona Novo Widget
                vm_widget = VMWidget(vm, self.controller)
                vm_widget.action_performed.connect(self.run_update_in_thread) 
                self.vms_layout.addWidget(vm_widget)
                self.vm_widgets[vmid] = vm_widget

        # --- 3. Atualizar Layout e Rótulos ---
        self.online_label.setText(f"🚀 Online: {online_count}")
        self.offline_label.setText(f"🛑 Offline: {offline_count}")
        
        self.scroll_content.adjustSize()
        QTimer.singleShot(0, lambda: scroll_bar.setValue(old_position))