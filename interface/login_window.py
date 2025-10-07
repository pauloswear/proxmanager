from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLineEdit, QMessageBox, QGridLayout, 
    QDesktopWidget, QLabel, QPushButton, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from utils.config_manager import ConfigManager
from api import ProxmoxAPIClient, ViewerConfigGenerator, ProxmoxController
from utils import set_dark_title_bar
from .main_window import MainWindow 


class LoginWindow(QMainWindow):
    """ Janela para coletar credenciais de conexão do Proxmox. """
    
    def __init__(self):
        super().__init__()
        set_dark_title_bar(self.winId())
        self.config_manager = ConfigManager()
        self.login_data = self.config_manager.load_login_data()
        self.setWindowTitle("ProxManager - Login")
        
        self.resize(450, 300)
        self.center()
        
        self.setStyleSheet("background-color: #1E1E1E; color: white;")
        
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)
        self.layout.setAlignment(Qt.AlignCenter)
        
        self.setup_ui()
        
        # Verifica se deve fazer auto-login após a UI estar pronta
        QTimer.singleShot(500, self.check_auto_login)
        
    def center(self):
        """ Centraliza a janela na tela do monitor. """
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def setup_ui(self):
        # Título
        title_label = QLabel("🔑 Proxmox VE Login")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #00A3CC; margin-bottom: 20px;")
        self.layout.addWidget(title_label)
        
        # Formulário
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setSpacing(10)

        input_style = "QLineEdit { background-color: #383838; color: white; border: 1px solid #555555; padding: 5px; border-radius: 4px; }"

        # Campo HOST IP
        form_layout.addWidget(QLabel("IP/Host:"), 0, 0)
        self.host_input = QLineEdit(text=self.login_data.get("host_ip", ""))
        self.host_input.setPlaceholderText("Ex: 192.168.1.10:8006 (optional port)")
        self.host_input.setStyleSheet(input_style)
        form_layout.addWidget(self.host_input, 0, 1)

        # Campo Usuário
        form_layout.addWidget(QLabel("User:"), 1, 0)
        self.user_input = QLineEdit(text=self.login_data.get("user", ""))
        self.user_input.setPlaceholderText("Ex: root@pam or name@pve")
        self.user_input.setStyleSheet(input_style)
        form_layout.addWidget(self.user_input, 1, 1)
        
        # Campo Senha
        form_layout.addWidget(QLabel("Password:"), 2, 0)
        self.password_input = QLineEdit(text=self.login_data.get("password", ""))
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(input_style)
        form_layout.addWidget(self.password_input, 2, 1)

        # Campo TOTP
        form_layout.addWidget(QLabel("TOTP:"), 3, 0)
        self.totp_input = QLineEdit(text=self.login_data.get("totp", "") or "")
        self.totp_input.setPlaceholderText("Opcional")
        self.totp_input.setStyleSheet(input_style)
        form_layout.addWidget(self.totp_input, 3, 1)

        # Checkbox Login Automático
        self.auto_login_check = QCheckBox("Lembrar login e conectar automaticamente")
        self.auto_login_check.setChecked(self.login_data.get('auto_login', False))
        self.auto_login_check.setStyleSheet("""
            QCheckBox {
                color: #CCCCCC;
                spacing: 5px;
                margin-top: 10px;
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
        form_layout.addWidget(self.auto_login_check, 4, 0, 1, 2)

        self.layout.addWidget(form_widget)
        
        # Botão Conectar
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.attempt_login)
        self.connect_btn.setStyleSheet("""
            QPushButton { 
                background-color: #00A3CC; color: white; height: 40px; border-radius: 5px; font-size: 11pt; font-weight: bold; margin-top: 15px;
            }
            QPushButton:hover { background-color: #00BFFF; }
            QPushButton:pressed { background-color: #007090; padding-top: 5px; }
        """)
        self.layout.addWidget(self.connect_btn)
        
        self.password_input.returnPressed.connect(self.attempt_login)
        self.host_input.returnPressed.connect(self.attempt_login)

    def check_auto_login(self):
        """
        Verifica se deve executar auto-login baseado nas configurações salvas.
        """
        # Verifica se auto-login está habilitado
        if not self.login_data.get('auto_login', False):
            return
        
        # Verifica se todos os dados necessários estão preenchidos
        host_ip = self.host_input.text().strip()
        user = self.user_input.text().strip() 
        password = self.password_input.text().strip()
        
        if host_ip and user and password:
            # Atualiza o checkbox para mostrar o estado correto
            self.auto_login_check.setChecked(True)
            
            # Mostra mensagem de conectando
            self.connect_btn.setText("Conectando...")
            self.connect_btn.setEnabled(False)
            
            # Executa o login automaticamente
            QTimer.singleShot(1000, self.attempt_login)  # Aguarda 1 segundo para o usuário ver a tela

    def attempt_login(self):
        """ 
        Tenta inicializar o ProxmoxController e abre a MainWindow.
        Garante que a exceção é capturada antes de tentar instanciar a MainWindow.
        """
        host_ip = self.host_input.text().strip()
        user = self.user_input.text().strip()
        password = self.password_input.text()
        totp = self.totp_input.text().strip() or None
        
        if not host_ip or not user or not password:
            QMessageBox.warning(self, "Erro de Login", "Por favor, preencha o Host/IP, Usuário e Senha.")
            return
        
        # Mostra mensagem de conectando
        self.connect_btn.setText("Conectando...")
        self.connect_btn.setEnabled(False)
        
        # ⭐️ O bloco try/except deve englobar TUDO o que pode falhar
        try:
            # 1. Tenta inicializar o cliente API
            # Se a conexão falhar AQUI (no construtor), ele deve levantar uma exceção.
            api_client = ProxmoxAPIClient(host=host_ip, user=user, password=password, totp=totp)
            
            # 2. Health Check: Tenta obter uma informação básica (como o status do node)
            # para validar se o token ou as permissões funcionam.
            if api_client.get_node_status() is None:
                 raise ConnectionError("Conexão bem-sucedida, mas falha ao obter status do Node (Verifique permissões ou HA).")

            # 3. Salva as credenciais no login.json (se o Health Check passou)
            login_data = {
                'host_ip': host_ip,
                'user': user, 
                'password': password,
                'totp': totp,
                'auto_login': self.auto_login_check.isChecked()
            }
            self.config_manager.save_login_data(login_data)
            
            # 4. Cria o restante do controlador
            config_generator = ViewerConfigGenerator(host_ip=host_ip)
            controller = ProxmoxController(api_client, config_generator)
            
            # 5. Abre a janela principal (só se tudo estiver ok)
            try:
                self.main_window = MainWindow(controller)
                self.main_window.show()
                # Aguarda um pouco antes de fechar a janela de login
                QTimer.singleShot(100, self.close)
            except Exception as main_window_error:
                raise Exception(f"Erro ao criar janela principal: {main_window_error}")
            
        except Exception as e:
            # ⭐️ Tratamento de erro ⭐️
            # Esta exceção captura falhas de rede, autenticação (da proxmoxer) 
            # ou a falha do Health Check (ConnectionError)
            
            # Restaura o botão em caso de erro (com verificação de segurança)
            try:
                if hasattr(self, 'connect_btn') and self.connect_btn is not None:
                    self.connect_btn.setText("Connect")
                    self.connect_btn.setEnabled(True)
            except RuntimeError:
                # Widget já foi destruído, ignora
                pass
            
            # Mostra erro de forma segura
            try:
                QMessageBox.critical(self, "Falha na Conexão", 
                                   f"Não foi possível conectar ao Proxmox.\n\nDetalhes do Erro: {str(e)}")
            except RuntimeError:
                # Se a janela foi destruída, imprime no console
                print(f"Erro de conexão: {e}")