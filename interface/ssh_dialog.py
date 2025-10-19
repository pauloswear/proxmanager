# ssh_dialog.py - Dialog para configurações SSH

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QSpinBox, QComboBox, QFormLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class SSHDialog(QDialog):
    """Dialog para configurar conexão SSH"""
    
    def __init__(self, ssh_config, parent=None):
        super().__init__(parent)
        self.ssh_config = ssh_config
        self.result_config = ssh_config.copy()
        
        self.setWindowTitle(f"Configurar SSH - VM {ssh_config['vmid']}")
        self.setFixedSize(400, 250)
        self.setup_ui()
        
        # Aplica o tema escuro
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D2D;
                color: white;
            }
            QLabel {
                color: white;
                font-size: 11pt;
            }
            QLineEdit, QSpinBox, QComboBox {
                background-color: #3D3D3D;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px;
                color: white;
                font-size: 10pt;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 2px solid #007ACC;
            }
            QPushButton {
                background-color: #007ACC;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: white;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
            QPushButton:pressed {
                background-color: #003F70;
            }
            QPushButton#cancel {
                background-color: #666666;
            }
            QPushButton#cancel:hover {
                background-color: #777777;
            }
        """)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel(f"Conectar via SSH")
        title.setFont(QFont("", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Formulário
        form_layout = QFormLayout()
        
        # IP
        self.ip_edit = QLineEdit(self.ssh_config.get('ip', ''))
        form_layout.addRow("IP:", self.ip_edit)
        
        # Porta
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(self.ssh_config.get('port', 22))
        form_layout.addRow("Porta:", self.port_spin)
        
        # Usuário
        self.user_edit = QLineEdit(self.ssh_config.get('default_user', 'root'))
        form_layout.addRow("Usuário:", self.user_edit)
        
        # Usuários sugeridos baseados no OS
        self.user_combo = QComboBox()
        os_type = self.ssh_config.get('os_type', 'linux')
        if os_type == 'windows':
            users = ['Administrator', 'admin', 'user']
        else:
            users = ['root', 'ubuntu', 'debian', 'admin', 'user']
        
        self.user_combo.addItems(users)
        self.user_combo.setCurrentText(self.ssh_config.get('default_user', 'root'))
        self.user_combo.currentTextChanged.connect(self.on_user_combo_changed)
        form_layout.addRow("Usuários sugeridos:", self.user_combo)
        
        # Info sobre o OS detectado
        os_info = self.ssh_config.get('os_info', {})
        os_name = os_info.get('name', f"OS: {os_type}")
        info_label = QLabel(f"Sistema detectado: {os_name}")
        info_label.setStyleSheet("color: #AAAAAA; font-size: 9pt;")
        form_layout.addRow("", info_label)
        
        layout.addLayout(form_layout)
        
        # Botões
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setObjectName("cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.connect_btn = QPushButton("Conectar SSH")
        self.connect_btn.clicked.connect(self.accept)
        self.connect_btn.setDefault(True)
        button_layout.addWidget(self.connect_btn)
        
        layout.addLayout(button_layout)
    
    def on_user_combo_changed(self, text):
        """Atualiza o campo de usuário quando a combo muda"""
        self.user_edit.setText(text)
    
    def get_config(self):
        """Retorna a configuração SSH atualizada"""
        self.result_config.update({
            'ip': self.ip_edit.text().strip(),
            'port': self.port_spin.value(),
            'user': self.user_edit.text().strip()
        })
        return self.result_config