# widgets.py

from typing import Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QSize, QThreadPool
)
from api import ProxmoxController # Assume que o Controller está acessível
from utils.utilities import ViewerWorker


class VMWidget(QWidget):
    """ Widget personalizado para exibir o status e ações de uma VM. """
    action_performed = pyqtSignal()
    
    def __init__(self, vm_data: Dict[str, Any], controller: ProxmoxController):
        super().__init__()
        self.vm_data = vm_data
        self.controller = controller
        # Usa a instância global do pool de threads
        self.threadpool = QThreadPool.globalInstance() 
        self.vmid = vm_data['vmid']
        self.status = vm_data['status']
        self.name = vm_data['name']
        
        # ⭐️ NOVOS LABELS DE MÉTRICAS (Definidos aqui, preenchidos em setup_ui)
        self.cpu_usage_label = QLabel()
        self.mem_usage_label = QLabel()
        
        self.setup_ui()
        self.update_metrics_display() # ⭐️ CHAMADA PARA EXIBIR MÉTRICAS INICIAIS
        self.update_buttons()

    def setup_ui(self):
        self.setStyleSheet("""
            VMWidget { background-color: #2D2D2D; border-radius: 6px; margin: 4px 0px; border: 1px solid #444444; }
            VMWidget:hover { background-color: #3A3A3A; }
        """)
        # Aumentar um pouco a altura para acomodar os novos labels
        self.setFixedHeight(85) 
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 5, 15, 5)

        # 1. Indicador de Status
        status_indicator = QLabel()
        status_indicator.setFixedSize(QSize(10, 10)) 
        status_color = "#28A745" if self.status == 'running' else "#DC3545"
        status_indicator.setStyleSheet(f"QLabel {{ background-color: {status_color}; border-radius: 5px; }}")
        main_layout.addWidget(status_indicator, alignment=Qt.AlignTop) # Alinhado ao topo para compensar a altura

        # 2. Informações da VM (Nome, Status, CPU e RAM)
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(1) 
        
        # Linha 1: Nome e ID
        name_label = QLabel(f"<b>{self.name}</b> <span style='color: #888888; font-size: 8pt;'>(ID: {self.vmid})</span>")
        name_label.setStyleSheet("color: white; font-size: 14pt;")
        info_layout.addWidget(name_label)
        
        # Linha 2: Status
        status_label = QLabel(f"Status: <b>{self.status.upper()}</b>")
        status_label.setStyleSheet(f"color: {status_color}; font-size: 9pt;")
        info_layout.addWidget(status_label)
        
        # ⭐️ Linha 3: Uso de CPU
        self.cpu_usage_label.setStyleSheet("color: #00A3CC; font-size: 9pt;")
        info_layout.addWidget(self.cpu_usage_label)
        
        # ⭐️ Linha 4: Uso de Memória (RAM)
        self.mem_usage_label.setStyleSheet("color: #FFC107; font-size: 9pt;")
        info_layout.addWidget(self.mem_usage_label)
        
        main_layout.addWidget(info_widget, 4)

        # 3. Botões de Ação
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8) 
        self.connect_btn = QPushButton()
        self.connect_btn.clicked.connect(self.on_connect_start_clicked)
        action_layout.addWidget(self.connect_btn, 2) 
        self.vnc_btn = QPushButton("VNC")
        self.vnc_btn.clicked.connect(self.on_vnc_clicked)
        action_layout.addWidget(self.vnc_btn, 1)
        self.reboot_btn = QPushButton("Restart")
        self.reboot_btn.clicked.connect(self.on_reboot_clicked)
        action_layout.addWidget(self.reboot_btn, 1)
        self.stop_btn = QPushButton("Shutdown")
        self.stop_btn.clicked.connect(self.on_stop_clicked)
        action_layout.addWidget(self.stop_btn, 1)
        main_layout.addLayout(action_layout, 6) 

        button_style_base = """
            QPushButton { height: 30px; border-radius: 4px; font-size: 9pt; font-weight: bold; background-color: #383838; }
            QPushButton:hover { background-color: #454545; border: 1px solid #777777; }
            QPushButton:pressed { background-color: #202020; padding-top: 3px; padding-left: 3px; }
        """
        self.vnc_btn.setStyleSheet(button_style_base.replace("#383838", "#404040") + "color: #CCCCCC; border: 1px solid #777777;")
        self.stop_btn.setStyleSheet(button_style_base.replace("#383838", "#503030") + "color: #DC3545; border: 1px solid #DC3545;")
        self.reboot_btn.setStyleSheet(button_style_base.replace("#383838", "#505030") + "color: #FFC107; border: 1px solid #FFC107;")


    # ⭐️ NOVO MÉTODO PARA ATUALIZAR AS MÉTRICAS DE CPU/RAM 

# widgets.py (Dentro da classe VMWidget, no método update_metrics_display)

    def update_metrics_display(self):
        """ Atualiza os rótulos de CPU e RAM com a formatação solicitada (Uso MB/GB). """
        
        # O self.vm_data é o dicionário de status inicial (incompleto)
        
        # --- 1. Busca os Dados de Status ATUAIS (Corrigidos) ---
        vm_type = self.vm_data.get('type', 'qemu') # Assume qemu se não encontrar
        
        # Chamamos a API para obter o status/current. Se a VM estiver parada,
        # self.vm_data.get('mem') será 0 e o status_data pode ser None/incompleto.
        status_data = self.controller.api_client.get_vm_current_status(self.vmid, vm_type)
        
        # Usa os dados do status atual, se disponíveis, ou faz fallback para os dados iniciais
        data_source = status_data if status_data else self.vm_data
        
        # --- Uso de CPU (Mantido) ---
        cpu_usage_percent = data_source.get('cpu', 0.0) * 100
        cpu_cores_total = data_source.get('maxcpu', 1)
        cpu_text = f"CPU: {cpu_usage_percent:.1f}% de {cpu_cores_total} Cores"
        self.cpu_usage_label.setText(cpu_text)
        
        # --- Uso de Memória (RAM) - Agora com dados de 'status/current' ---
        
        # 'mem' é o campo de memória USADA em bytes (preciso para LXC/QEMU status/current)
        mem_used_bytes = data_source.get('mem', 0) 
        mem_total_bytes = data_source.get('maxmem', 0)
        
        if mem_total_bytes > 0:
            
            # Converte o USO de bytes para MEGABYTES (1024^2)
            mem_used_mb = mem_used_bytes / (1024**2)
            
            # Converte o TOTAL de bytes para GIGABYTES (1024^3)
            mem_total_gb = mem_total_bytes / (1024**3)
            
            # Adiciona o tipo de VM para contexto
            mem_text = f"RAM: {mem_used_mb:.1f} MB de {mem_total_gb:.1f} GB ({vm_type.upper()})"
        else:
            mem_text = "RAM: N/A"

        self.mem_usage_label.setText(mem_text)

    # Os métodos update_buttons, on_vnc_clicked, etc. continuam os mesmos.

    def update_buttons(self):
        is_running = self.status == 'running'
        
        if is_running:
            self.connect_btn.setText("Connect to SPICE")
            color = "#00A3CC"
            hover_color = "#00BFFF"
            pressed_color = "#007090"
        else:
            self.connect_btn.setText("START VM")
            color = "#28A745"
            hover_color = "#30C750"
            pressed_color = "#1F7A35"

        self.connect_btn.setStyleSheet(f"""
            QPushButton {{ 
                height: 30px; border-radius: 4px; font-size: 9pt; font-weight: bold; color: white; 
                background-color: {color}; border: 1px solid {color};
            }}
            QPushButton:hover {{ background-color: {hover_color}; border: 1px solid {hover_color}; }}
            QPushButton:pressed {{ background-color: {pressed_color}; border: 1px solid {pressed_color};
                padding-top: 3px; padding-left: 3px;
            }}
        """)
        self.stop_btn.setVisible(is_running)
        self.reboot_btn.setVisible(is_running)
        self.vnc_btn.setVisible(is_running)
        self.vnc_btn.setHidden(True) # TODO 



    def on_vnc_clicked(self):
        worker = ViewerWorker(self.controller, self.vmid, protocol='vnc')
        self.threadpool.start(worker)

    def on_connect_start_clicked(self):
        if self.status == 'running':
            worker = ViewerWorker(self.controller, self.vmid, protocol='spice')
            self.threadpool.start(worker)
            
        else:
            if self.controller.api_client.start_vm(self.vmid):
                self.action_performed.emit()

    def on_stop_clicked(self):
        if self.controller.api_client.stop_vm(self.vmid):
            self.action_performed.emit()

    def on_reboot_clicked(self):
        if self.controller.api_client.reboot_vm(self.vmid):
            self.action_performed.emit()