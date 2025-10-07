import datetime
from typing import Dict, Any
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QDesktopWidget, QPushButton
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, QSettings
)
from PyQt5.QtGui import QFont
from .widgets import VMWidget
from api import ProxmoxController 
from utils.utilities import set_dark_title_bar


class MainWindow(QMainWindow):
    """ Janela principal para gerenciar e visualizar as VMs e o status do Node. """
    
    def __init__(self, controller: ProxmoxController):
        super().__init__()
        set_dark_title_bar(self.winId())
        self.controller = controller
        # Exibe o nome do Node, assumindo que ele está armazenado no api_client
        node_name = self.controller.api_client.node if hasattr(self.controller.api_client, 'node') else 'N/A'
        self.setWindowTitle(f"ProxManager - Node: {node_name}")
        
        # Geometria e QSettings
        self.settings = QSettings()
        self.load_geometry()
        
        self.setStyleSheet("background-color: #1E1E1E; color: white;") 
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        
        self.setup_header()
        self.setup_scroll_area()
        self.setup_footer() 
        
        # Faz a primeira carga completa
        self.refresh_dashboard()
        
        # Timer de 3s para atualização automática
        self.timer = QTimer(self)
        # O timer chama o método unificado de atualização
        self.timer.timeout.connect(self.refresh_dashboard) 
        self.timer.start(2500) 

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
        """ Configura o rodapé em duas linhas: 
            1. Status de VMs e Métricas do Node (Com stretch à direita).
            2. Controles do Node (Restart/Shutdown - Esquerda) e Copyright (Direita).
        """
        
        # 1. Widget principal do Rodapé (usará QVBoxLayout para empilhar)
        footer_container = QWidget()
        footer_v_layout = QVBoxLayout(footer_container)
        # Margens e espaçamento
        footer_v_layout.setContentsMargins(10, 5, 10, 5) 
        footer_v_layout.setSpacing(5) 

        footer_style = "font-weight: bold; font-size: 9pt; margin-right: 15px;"

        # --- LINHA 1: Status e Métricas (usando QHBoxLayout) ---
        status_metrics_widget = QWidget()
        status_metrics_layout = QHBoxLayout(status_metrics_widget)
        status_metrics_layout.setContentsMargins(0, 0, 0, 0)
        
        # Rótulos para o status da VM (Online/Offline)
        self.online_label = QLabel()
        self.online_label.setStyleSheet("color: #28A745; " + footer_style)
        self.offline_label = QLabel()
        self.offline_label.setStyleSheet("color: #DC3545; " + footer_style)
        
        status_metrics_layout.addWidget(self.online_label)
        status_metrics_layout.addWidget(self.offline_label)
        
        # Separador para Status/Métricas
        status_metrics_layout.addSpacing(10)
        separator_status_label = QLabel("|")
        separator_status_label.setStyleSheet("color: #444444; font-size: 10pt;")
        status_metrics_layout.addWidget(separator_status_label)
        status_metrics_layout.addSpacing(15)

        # Rótulos para as Métricas do Node
        self.cpu_label = QLabel("CPU: N/A")
        self.cpu_label.setStyleSheet("color: #00A3CC; " + footer_style)
        self.mem_label = QLabel("RAM: N/A")
        self.mem_label.setStyleSheet("color: #FFC107; " + footer_style)
        self.load_label = QLabel("Load Avg: N/A") 
        self.load_label.setStyleSheet("color: #DC3545; " + footer_style)
        self.uptime_label = QLabel("Uptime: N/A") 
        self.uptime_label.setStyleSheet("color: #999999; " + footer_style)
        
        status_metrics_layout.addWidget(self.cpu_label)
        status_metrics_layout.addWidget(self.mem_label)
        status_metrics_layout.addWidget(self.load_label)
        status_metrics_layout.addWidget(self.uptime_label)

        status_metrics_layout.addStretch(1) # Empurra tudo para a esquerda
        footer_v_layout.addWidget(status_metrics_widget)

        # --- SEPARADOR HORIZONTAL (Traço) ---
        separator_line = QLabel()
        separator_line.setFixedHeight(1)
        separator_line.setStyleSheet("background-color: #333333; margin-top: 5px; margin-bottom: 5px;")
        footer_v_layout.addWidget(separator_line)
        
        
        # ⭐️ --- LINHA 2: CONTROLES E COPYRIGHT (Usando QHBoxLayout) ---
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
        self.node_restart_btn.clicked.connect(self.on_node_restart_clicked)
        controls_copyright_layout.addWidget(self.node_restart_btn)

        # Botão de Shutdown (ESQUERDA)
        self.node_shutdown_btn = QPushButton("🛑 SHUTDOWN NODE")
        self.node_shutdown_btn.setStyleSheet("""
            QPushButton { height: 25px; border-radius: 4px; font-size: 8pt; font-weight: bold; background-color: #503030; color: #DC3545; margin-left: 10px; }
            QPushButton:hover { background-color: #604040; }
        """)
        self.node_shutdown_btn.setFixedSize(130, 25)
        self.node_shutdown_btn.clicked.connect(self.on_node_shutdown_clicked)
        controls_copyright_layout.addWidget(self.node_shutdown_btn)
        
        
        # ⭐️ Espaçamento flexível para empurrar o copyright para a direita
        controls_copyright_layout.addStretch(1) 

        # Rótulo de Copyright (DIREITA)
        current_year = datetime.datetime.now().year
        # Usando QLabel com HTML para link externo e formatação
        copyright_text = f"<span>© {current_year} - <a href='https://github.com/pauloswear' style='color: #00A3CC; text-decoration: none;'>Paulo Henrique</a></span>"
        
        copyright_label = QLabel(copyright_text)
        copyright_label.setStyleSheet("color: #888888; font-size: 8pt;")
        copyright_label.setOpenExternalLinks(True)
        
        controls_copyright_layout.addWidget(copyright_label)
        
        footer_v_layout.addWidget(controls_copyright_widget)

        self.main_layout.addWidget(footer_container)


    # --- Utility Methods ---

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

    # ⭐️ --- MÉTODOS DE CONTROLE DO NODE ---

    def on_node_restart_clicked(self):
        """ Executa a ação de Restart do Node através do Controller. """
        # ⚠️ IMPORTANTE: Você deve implementar um Pop-up de CONFIRMAÇÃO aqui!
        # Ações de Restart/Shutdown de Node são perigosas.

        # Exemplo de como chamar o Controller (assumindo a função existe)
        success = self.controller.api_client.restart_node()
        
        if success:
            print("Restart do Node iniciado com sucesso.")
            # O Node ficará inacessível, então não faz sentido chamar refresh_dashboard()
            # Uma mensagem de aviso para o usuário é o ideal.
        else:
            print("ERRO ao tentar reiniciar o Node.")
            
    def on_node_shutdown_clicked(self):
        """ Executa a ação de Shutdown do Node através do Controller. """
        # ⚠️ IMPORTANTE: Você deve implementar um Pop-up de CONFIRMAÇÃO aqui!
        
        # Exemplo de como chamar o Controller (assumindo a função existe)
        success = self.controller.api_client.shutdown_node()
        
        if success:
            print("Shutdown do Node iniciado com sucesso.")
            # O Node ficará inacessível
        else:
            print("ERRO ao tentar desligar o Node.")


    # --- Dashboard Methods ---

    def refresh_dashboard(self):
        """ Método unificado chamado pelo timer para atualizar todas as métricas e a lista de VMs. """
        self.load_vms()
        self.update_node_metrics()


    def update_node_metrics(self):
        """ Busca e exibe as métricas de uso do Node. """
        # Chama o novo método do seu api_client
        status_data = self.controller.api_client.get_node_status()
        
        if not status_data:
            self.cpu_label.setText("CPU: ERROR")
            self.mem_label.setText("RAM: ERROR")
            self.load_label.setText("Load Avg: ERROR")
            self.uptime_label.setText("Uptime: ERROR")
            return
            
        # --- Uso de CPU ---
        cpu_usage = status_data.get('cpu', 0.0) * 100
        
        # --- Load Average (CORRIGIDO) ---
        load_avg_list = status_data.get('loadavg', [0, 0, 0])
        
        # ⭐️ TRATAMENTO DE ERRO AQUI: Converte para float de forma segura
        try:
            # Pega o primeiro valor (média de 1 minuto) e converte para float
            load_value = float(load_avg_list[0]) 
            load_avg_str = f"{load_value:.2f}"
        except (ValueError, TypeError, IndexError):
            # Se a conversão falhar (se for 'str' não numérica, None, ou lista vazia)
            load_avg_str = "N/A" # Define um valor seguro
        
        # --- Uso de Memória (RAM) ---
        mem_total = status_data.get('memory', {}).get('total', 0)
        mem_used = status_data.get('memory', {}).get('used', 0)
        
        if mem_total > 0:
            mem_percent = (mem_used / mem_total) * 100
            # Converte bytes para GB
            mem_used_gb = mem_used / (1024**3)
            mem_total_gb = mem_total / (1024**3)
            mem_text = f"RAM: {mem_percent:.1f}% ({mem_used_gb:.1f}/{mem_total_gb:.1f} GB)"
        else:
            mem_text = "RAM: N/A"

        # --- Uptime ---
        uptime_seconds = status_data.get('uptime', 0)
        # Converte segundos para Dd Hh Mm
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        uptime_text = f"Uptime: {days}d {hours}h {minutes}m"
            
        # Atualiza os Rótulos
        self.cpu_label.setText(f"CPU: {cpu_usage:.1f}%")
        self.mem_label.setText(mem_text)
        self.load_label.setText(f"Load Avg: {load_avg_str}")
        self.uptime_label.setText(uptime_text)


    def load_vms(self):
        """ Carrega e exibe a lista de VMs, atualizando o status de contagem (VM status). """
        
        scroll_bar = self.scroll_area.verticalScrollBar()
        old_position = scroll_bar.value()

        # Limpa o layout existente
        while self.vms_layout.count():
            child = self.vms_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        vms_list = self.controller.api_client.get_vms_list()
        
        online_count = 0
        offline_count = 0

        if not vms_list:
            self.online_label.setText("Online: 0")
            self.offline_label.setText("Offline: 0")
            self.vms_layout.addWidget(QLabel("Não foi possível conectar ou nenhuma VM encontrada. Verifique as credenciais/rede."))
            return

        # Lógica de Contagem de Status de VMs
        for vm in vms_list:
            if vm['status'] == 'running':
                online_count += 1
            else:
                offline_count += 1

        # Atualiza os rótulos do rodapé de VM
        self.online_label.setText(f"🚀 Online: {online_count}")
        self.offline_label.setText(f"🛑 Offline: {offline_count}")

        # Lógica de Ordenação
        def sort_key(vm: Dict[str, Any]):
            status_priority = 0 if vm['status'] == 'running' else 1
            return (status_priority, vm['name'].lower())

        sorted_vms = sorted(vms_list, key=sort_key)
        
        # Adiciona os widgets
        for vm in sorted_vms:
            vm_widget = VMWidget(vm, self.controller)
            # Conecta a ação da VM para atualizar toda a dashboard
            vm_widget.action_performed.connect(self.refresh_dashboard) 
            self.vms_layout.addWidget(vm_widget)
        
        self.scroll_content.adjustSize()

        # Restaura a posição do scroll
        QTimer.singleShot(0, lambda: scroll_bar.setValue(old_position))