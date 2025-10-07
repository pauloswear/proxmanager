# widgets.py

from typing import Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QSize, QThreadPool
)
from api import ProxmoxController
# Assumindo que ViewerWorker está definido em utils.utilities
from utils.utilities import ViewerWorker 


class VMWidget(QWidget):
    """ Widget personalizado para exibir o status e ações de uma VM. """
    action_performed = pyqtSignal()
    
    def __init__(self, vm_data: Dict[str, Any], controller: ProxmoxController):
        super().__init__()
        self.controller = controller
        # Usa a instância global do pool de threads
        self.threadpool = QThreadPool.globalInstance() 
        
        # ⭐️ Dados iniciais - Serão atualizados pelo update_data
        self.vm_data = vm_data
        self.vmid = vm_data['vmid']
        self.name = vm_data['name']
        
        # LABELS DE MÉTRICAS
        self.status_label = QLabel() # ⭐️ Adicionado self para status_label
        self.cpu_usage_label = QLabel()
        self.mem_usage_label = QLabel()
        
        self.setup_ui()
        
        # ⭐️ Chama update_data para popular a UI com os dados iniciais
        self.update_data(vm_data) 

    # ⭐️ NOVO MÉTODO OBRIGATÓRIO PARA ATUALIZAÇÃO ASSÍNCRONA
    def update_data(self, new_vm_data: Dict[str, Any]):
        """
        Atualiza os dados internos do widget e redesenha a exibição
        com base no novo status recebido da MainWindow (thread principal).
        """
        # 1. Atualiza o dicionário de dados
        self.vm_data = new_vm_data
        self.status = new_vm_data.get('status', 'unknown')
        self.vmid = new_vm_data.get('vmid', self.vmid)
        self.name = new_vm_data.get('name', self.name)

        # 2. Atualiza os componentes da UI
        self.update_metrics_display()
        self.update_status_display()
        self.update_action_buttons()


    def setup_ui(self):
        self.setStyleSheet("""
            VMWidget { background-color: #2D2D2D; border-radius: 6px; margin: 4px 0px; border: 1px solid #444444; }
            VMWidget:hover { background-color: #3A3A3A; }
        """)
        self.setFixedHeight(85) 
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 5, 15, 5)

        # 1. Indicador de Status (Gráfico)
        status_indicator = QLabel()
        status_indicator.setFixedSize(QSize(10, 10)) 
        self.status_indicator = status_indicator # ⭐️ Guarda a referência
        main_layout.addWidget(status_indicator, alignment=Qt.AlignTop)

        # 2. Informações da VM (Nome, Status, CPU e RAM)
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(1) 
        
        # Linha 1: Nome e ID
        # ⭐️ Usando o nome e ID atuais (self.name, self.vmid)
        self.name_id_label = QLabel(f"<b>{self.name}</b> <span style='color: #888888; font-size: 8pt;'>(ID: {self.vmid})</span>")
        self.name_id_label.setStyleSheet("color: white; font-size: 14pt;")
        info_layout.addWidget(self.name_id_label)
        
        # Linha 2: Status (status_label já existe, só precisa ser self.status_label)
        # O self.status_label foi definido no __init__ e será populado em update_status_display
        info_layout.addWidget(self.status_label) 
        
        # Linha 3: Uso de CPU
        self.cpu_usage_label.setStyleSheet("color: #00A3CC; font-size: 9pt;")
        info_layout.addWidget(self.cpu_usage_label)
        
        # Linha 4: Uso de Memória (RAM)
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


    # --- Métodos de Atualização de UI (usam apenas self.vm_data) ---

    def update_metrics_display(self):
        """ Atualiza os rótulos de CPU e RAM usando self.vm_data atualizado. """
        
        data_source = self.vm_data
        vm_type = data_source.get('type', 'qemu')
        
        # --- Uso de CPU ---
        cpu_usage_percent = data_source.get('cpu', 0.0) * 100
        cpu_cores_total = data_source.get('maxcpu', 1)
        cpu_text = f"CPU: {cpu_usage_percent:.1f}% de {cpu_cores_total} Cores"
        self.cpu_usage_label.setText(cpu_text)
        
        # --- Uso de Memória (RAM) ---
        mem_used_bytes = data_source.get('mem', 0) 
        mem_total_bytes = data_source.get('maxmem', 0)
        
        if mem_total_bytes > 0:
            mem_used_mb = mem_used_bytes / (1024**2)
            mem_total_gb = mem_total_bytes / (1024**3)
            mem_text = f"RAM: {mem_used_mb:.1f} MB de {mem_total_gb:.1f} GB ({vm_type.upper()})"
        else:
            mem_text = "RAM: N/A"

        self.mem_usage_label.setText(mem_text)

    def update_status_display(self):
        """ Atualiza os indicadores de status. """
        status = self.status
        
        if status == 'running':
            color = "#28A745"
            status_text = f"Status: <b>{status.upper()}</b>"
        elif status == 'stopped':
            color = "#DC3545"
            status_text = f"Status: <b>{status.upper()}</b>"
        elif status == 'suspended':
            color = "#FFC107"
            status_text = f"Status: <b>{status.upper()}</b>"
        else:
            color = "#6C757D"
            status_text = f"Status: <b>{status.upper()}</b>" # Inclui 'unknown'

        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 9pt;")
        
        # Atualiza o indicador gráfico
        self.status_indicator.setStyleSheet(f"QLabel {{ background-color: {color}; border-radius: 5px; }}")


    def update_action_buttons(self):
        """ Atualiza a aparência e o estado dos botões de ação. """
        is_running = self.status == 'running'
        
        # Botão principal (Connect/Start)
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
        
        # Botões de controle (Shutdown, Reboot, VNC)
        self.stop_btn.setEnabled(is_running)
        self.reboot_btn.setEnabled(is_running)
        self.vnc_btn.setEnabled(is_running)
        
        self.stop_btn.setVisible(is_running)
        self.reboot_btn.setVisible(is_running)
        self.vnc_btn.setHidden(True) # Mantido como hidden

    # --- Métodos de Clique (Permanecem os mesmos) ---

    def on_vnc_clicked(self):
        worker = ViewerWorker(self.controller, self.vmid, protocol='vnc')
        self.threadpool.start(worker)

    def on_connect_start_clicked(self):
        if self.status == 'running':
            worker = ViewerWorker(self.controller, self.vmid, protocol='spice')
            self.threadpool.start(worker)
            
        else:
            # Assíncrono: Ação de START deve emitir o sinal para forçar a atualização
            if self.controller.api_client.start_vm(self.vmid):
                self.action_performed.emit()

    def on_stop_clicked(self):
        # Assíncrono: Ação de STOP deve emitir o sinal para forçar a atualização
        if self.controller.api_client.stop_vm(self.vmid):
            self.action_performed.emit()

    def on_reboot_clicked(self):
        # Assíncrono: Ação de REBOOT deve emitir o sinal para forçar a atualização
        if self.controller.api_client.reboot_vm(self.vmid):
            self.action_performed.emit()