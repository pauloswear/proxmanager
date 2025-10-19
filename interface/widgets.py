# widgets.py - Versão otimizada

from typing import Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QSize, QThreadPool, QTimer
)
# A importação relativa do ProxmoxController garante o acesso à API
from api import ProxmoxController 
# Assumindo que ViewerWorker está em utils.utilities
from utils.utilities import ViewerWorker 


class VMWidget(QWidget):
    """ Widget personalizado para exibir o status e ações de uma VM. """
    action_performed = pyqtSignal()
    
    def __init__(self, vm_data: Dict[str, Any], controller: ProxmoxController):
        super().__init__()
        self.controller = controller
        # Usamos o pool de threads global para abrir o Viewer (SPICE/VNC)
        self.threadpool = QThreadPool.globalInstance() 
        
        self.vm_data = vm_data
        self.vmid = vm_data.get('vmid', -1)
        self.name = vm_data.get('name', 'VM Desconhecida')
        self.status = vm_data.get('status', 'unknown')
        
        # LABELS DE MÉTRICAS
        self.status_label = QLabel() 
        self.cpu_usage_label = QLabel()
        self.mem_usage_label = QLabel()
        self.ip_label = QLabel()
        
        self.setup_ui()
        self.update_data(vm_data) 


    def update_data(self, new_vm_data: Dict[str, Any]):
        """
        Atualiza os dados internos do widget usando os dados PRÉ-BUSCADOS
        pela thread de background da MainWindow. (Seguro para Thread Principal).
        """
        # 1. Atualiza o dicionário de dados (MANTIDO)
        self.vm_data = new_vm_data
        self.vmid = new_vm_data.get('vmid', self.vmid)
        self.name = new_vm_data.get('name', self.name)
        self.status = new_vm_data.get('status', self.status) # Novo status
        
        # 2. Atualiza os componentes da UI
        self.update_metrics_display()
        self.update_status_display()
        self.update_ip_display()
        self.update_action_buttons()


    def setup_ui(self):
        self.setStyleSheet("""
            VMWidget { 
                background-color: #2D2D2D; 
                border-radius: 6px; 
                margin: 1px; 
                border: 1px solid #444444; 
            }
            VMWidget:hover { 
                background-color: #3A3A3A; 
                border: 1px solid #4A90E2;
            }
        """)
        self.setFixedHeight(75)  # Aumentado para acomodar IP
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 3, 10, 3)  # Margem esquerda ajustada para 15px

        # 1. Indicador de Status (Gráfico)
        status_indicator = QLabel()
        status_indicator.setFixedSize(QSize(10, 10)) 
        self.status_indicator = status_indicator 
        main_layout.addWidget(status_indicator, alignment=Qt.AlignTop)

        # 2. Informações da VM 
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)  # Reduzido de 1 para 0 
        
        self.name_id_label = QLabel(f"<b>{self.name}</b> <span style='color: #888888; font-size: 7pt;'>(ID: {self.vmid})</span>")
        self.name_id_label.setStyleSheet("color: white; font-size: 11pt;")  # Reduzido de 14pt para 11pt
        info_layout.addWidget(self.name_id_label)
        
        info_layout.addWidget(self.status_label) 
        info_layout.addWidget(self.cpu_usage_label)
        info_layout.addWidget(self.mem_usage_label)
        info_layout.addWidget(self.ip_label)
        
        main_layout.addWidget(info_widget, 4)

        # 3. Botões de Ação
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8) 
        
        self.connect_btn = QPushButton()
        self.connect_btn.clicked.connect(self.on_connect_start_clicked)
        action_layout.addWidget(self.connect_btn, 2) 
        
        self.ssh_btn = QPushButton("SSH")
        self.ssh_btn.clicked.connect(self.on_ssh_clicked)
        action_layout.addWidget(self.ssh_btn, 1)
        
        self.novnc_btn = QPushButton("noVNC")
        self.novnc_btn.clicked.connect(self.on_novnc_clicked)
        action_layout.addWidget(self.novnc_btn, 1)
        
        self.spice_btn = QPushButton("SPICE")
        self.spice_btn.clicked.connect(self.on_spice_clicked)
        action_layout.addWidget(self.spice_btn, 1)
        
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
            QPushButton { height: 24px; border-radius: 3px; font-size: 8pt; font-weight: bold; background-color: #383838; }
            QPushButton:hover { background-color: #454545; border: 1px solid #777777; }
            QPushButton:pressed { background-color: #202020; padding-top: 3px; padding-left: 3px; }
        """
        self.ssh_btn.setStyleSheet(button_style_base.replace("#383838", "#404040") + "color: #28A745; border: 1px solid #28A745;")
        self.novnc_btn.setStyleSheet(button_style_base.replace("#383838", "#404040") + "color: #FF6B35; border: 1px solid #FF6B35;")
        self.spice_btn.setStyleSheet(button_style_base.replace("#383838", "#404040") + "color: #00A3CC; border: 1px solid #00A3CC;")
        self.vnc_btn.setStyleSheet(button_style_base.replace("#383838", "#404040") + "color: #CCCCCC; border: 1px solid #777777;")
        self.stop_btn.setStyleSheet(button_style_base.replace("#383838", "#503030") + "color: #DC3545; border: 1px solid #DC3545;")
        self.reboot_btn.setStyleSheet(button_style_base.replace("#383838", "#505030") + "color: #FFC107; border: 1px solid #FFC107;")


    # --- Métodos de Atualização de UI (Sem chamadas de API) ---

    def update_metrics_display(self):
        """ Usa APENAS self.vm_data que já está atualizado. """
        
        data_source = self.vm_data
        vm_type = data_source.get('type', 'qemu')
        
        # --- Uso de CPU ---
        cpu_usage_percent = data_source.get('cpu', 0.0) * 100
        cpu_cores_total = data_source.get('maxcpu', 1)
        cpu_text = f"CPU: {cpu_usage_percent:.1f}% de {cpu_cores_total} Cores"
        self.cpu_usage_label.setStyleSheet("color: #00A3CC; font-size: 8pt;")
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

        self.mem_usage_label.setStyleSheet("color: #FFC107; font-size: 8pt;")
        self.mem_usage_label.setText(mem_text)

    def update_status_display(self):
        """ Atualiza os indicadores de status. """
        status = self.status
        
        if status == 'running':
            color = "#28A745"
        elif status == 'stopped':
            color = "#DC3545"
        elif status == 'suspended':
            color = "#FFC107"
        else:
            color = "#6C757D"
        
        status_text = f"Status: <b>{status.upper()}</b>"

        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 8pt;")
        self.status_indicator.setStyleSheet(f"QLabel {{ background-color: {color}; border-radius: 5px; }}")

    def update_ip_display(self):
        """ Atualiza a exibição dos endereços IP. """
        ip_addresses = self.vm_data.get('ip_addresses', [])
        # Debug log commented out
        
        if ip_addresses:
            # Filtra apenas IPv4 para uma exibição mais limpa
            ipv4_addresses = [ip for ip in ip_addresses if '.' in ip and not ip.startswith('127.')]
            # IPv4 filtering applied
            
            if ipv4_addresses:
                # Exibe apenas o primeiro IP IPv4 válido
                ip_text = f"IP: {ipv4_addresses[0]}"
                if len(ipv4_addresses) > 1:
                    ip_text += f" (+{len(ipv4_addresses)-1})"
            elif ip_addresses:
                # Se não há IPv4, exibe o primeiro IP disponível
                ip_text = f"IP: {ip_addresses[0]}"
            else:
                ip_text = "IP: N/A"
        else:
            ip_text = "IP: N/A" if self.status == 'running' else "IP: Stopped"
        

        self.ip_label.setText(ip_text)
        self.ip_label.setStyleSheet("color: #90EE90; font-size: 8pt;")

    def update_action_buttons(self):
        """ Atualiza a aparência e o estado dos botões de ação. """
        is_running = self.status == 'running'
        
        # Botão principal (Connect/Start)
        if is_running:
            self.connect_btn.setText("RDP")
            color = "#007ACC"  # Azul mais escuro para RDP
            hover_color = "#0099FF"
            pressed_color = "#005999"
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
        
        # Botões de controle (Shutdown, Reboot, SSH, noVNC, SPICE, VNC)
        self.stop_btn.setEnabled(is_running)
        self.reboot_btn.setEnabled(is_running)
        self.ssh_btn.setEnabled(is_running)
        self.novnc_btn.setEnabled(is_running)
        self.spice_btn.setEnabled(is_running)
        self.vnc_btn.setEnabled(is_running)
        
        self.stop_btn.setVisible(is_running)
        self.reboot_btn.setVisible(is_running)
        self.ssh_btn.setVisible(is_running)
        self.novnc_btn.setVisible(is_running)
        self.spice_btn.setVisible(is_running)
        # Manter VNC escondido se não for usado ativamente
        self.vnc_btn.setHidden(True) 

    # --- Métodos de Clique (Ações) ---

    def on_ssh_clicked(self):
        # Versão simplificada: conecta diretamente com usuário padrão
        worker = ViewerWorker(self.controller, self.vmid, protocol='ssh')
        self.threadpool.start(worker)

    def on_novnc_clicked(self):
        worker = ViewerWorker(self.controller, self.vmid, protocol='novnc')
        self.threadpool.start(worker)

    def on_spice_clicked(self):
        worker = ViewerWorker(self.controller, self.vmid, protocol='spice')
        self.threadpool.start(worker)

    def on_vnc_clicked(self):
        worker = ViewerWorker(self.controller, self.vmid, protocol='vnc')
        self.threadpool.start(worker)

    def on_connect_start_clicked(self):
        if self.status == 'running':
            # Abre o cliente RDP em uma nova thread
            worker = ViewerWorker(self.controller, self.vmid, protocol='rdp')
            self.threadpool.start(worker)
            
        else:
            # Ação de controle síncrona
            if self.controller.api_client.start_vm(self.vmid):
                # Dispara um sinal para forçar a MainWindow a atualizar o dashboard
                self.action_performed.emit() 

    def on_stop_clicked(self):
        if self.controller.api_client.stop_vm(self.vmid):
            self.action_performed.emit()

    def on_reboot_clicked(self):
        if self.controller.api_client.reboot_vm(self.vmid):
            self.action_performed.emit()