from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLineEdit, QMessageBox, QGridLayout, 
    QDesktopWidget, QLabel, QPushButton, QCheckBox, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from utils.config_manager import ConfigManager
from api import ProxmoxAPIClient, ViewerConfigGenerator, ProxmoxController
from utils import set_dark_title_bar
from .main_window import MainWindow 


class LoadingWorker(QThread):
    """Thread para carregar dados iniciais sem travar a UI"""
    finished = pyqtSignal(object, object)  # Emite (node_data, vms_list)
    error = pyqtSignal(str)  # Emite mensagem de erro
    
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
    
    def load_vm_data(self, vm):
        """Carrega dados de uma VM individual (executado em paralelo)"""
        vmid = vm.get('vmid')
        vm_type = vm.get('type')
        
        if vmid is None or vm_type is None:
            return None
        
        # Get detailed status
        try:
            detailed_status = self.controller.api_client.get_vm_current_status(vmid, vm_type)
            if detailed_status:
                vm.update(detailed_status)
        except:
            pass
        
        # Get config
        try:
            vm_config = self.controller.api_client.get_vm_config(vmid, vm_type)
            if vm_config:
                if 'ostype' in vm_config:
                    vm['ostype'] = vm_config['ostype']
                if 'vga' in vm_config:
                    vm['vga'] = vm_config['vga']
        except:
            pass
        
        # Get IPs
        if vm.get('status') == 'running':
            try:
                ip_addresses = self.controller.api_client.get_vm_network_info(vmid, vm_type)
                vm['ip_addresses'] = ip_addresses
            except:
                vm['ip_addresses'] = []
        else:
            vm['ip_addresses'] = []
        
        return vm
    
    def run(self):
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            # Carrega apenas os DADOS em thread (não cria widgets)
            node_data = None
            vms_list = []
            
            # Carrega métricas do node
            try:
                node_data = self.controller.api_client.get_node_status()
            except:
                pass
            
            # Carrega lista básica de VMs
            try:
                raw_vms = self.controller.api_client.get_vms_list()
                
                if raw_vms:
                    # Usa ThreadPoolExecutor para carregar dados de VMs em paralelo
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        # Submete todas as VMs para processamento paralelo
                        future_to_vm = {executor.submit(self.load_vm_data, vm): vm for vm in raw_vms}
                        
                        # Coleta resultados conforme vão ficando prontos
                        for future in as_completed(future_to_vm):
                            try:
                                vm_data = future.result()
                                if vm_data:
                                    vms_list.append(vm_data)
                            except Exception as e:
                                # Se uma VM falhar, continua com as outras
                                pass
                        
            except Exception as e:
                raise Exception(f"Erro ao carregar VMs: {e}")
            
            # Emite os dados carregados
            self.finished.emit(node_data, vms_list)
            
        except Exception as e:
            self.error.emit(str(e))


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
        
        self.loading_worker = None
        self.progress_bar = None
        
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
        self.auto_login_check = QCheckBox("Remember-me and auto connect")
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
            self.connect_btn.setText("Connecting...")
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
        self.connect_btn.setText("Connecting...")
        self.connect_btn.setEnabled(False)
        
        # ⭐️ O bloco try/except deve englobar TUDO o que pode falhar
        try:
            # 1. Tenta inicializar o cliente API
            # Se a conexão falhar AQUI (no construtor), ele deve levantar uma exceção.
            api_client = ProxmoxAPIClient(host=host_ip, user=user, password=password, totp=totp)
            
            # 2. Health Check: Tenta obter uma informação básica (como o status do node)
            # para validar se o token ou as permissões funcionam.
            if api_client.get_node_status() is None:
                raise ConnectionError("Connection successful, but failed to get node status (Check permissions or HA).")

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
            
            # 5. Salva o controller para usar depois
            self.pending_controller = controller
            
            # 6. Mostra loading e inicia thread de carregamento
            self.show_loading()
            
            # 7. Cria worker thread para carregar APENAS DADOS
            self.loading_worker = LoadingWorker(controller)
            self.loading_worker.finished.connect(self.on_loading_finished)
            self.loading_worker.error.connect(self.on_loading_error)
            self.loading_worker.start()
            
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
                QMessageBox.critical(self, "Connection Failed", 
                                   f"Unable to connect to Proxmox.\n\nError Details: {str(e)}")
            except RuntimeError:
                # Se a janela foi destruída, imprime no console
                print(f"Connection error: {e}")
    
    def show_loading(self):
        """Mostra barra de progresso durante carregamento"""
        if self.progress_bar is None:
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 0)  # Modo indeterminado
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #444;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #2D2D2D;
                }
                QProgressBar::chunk {
                    background-color: #00A3CC;
                }
            """)
            self.layout.addWidget(self.progress_bar)
        
        self.progress_bar.setVisible(True)
        self.connect_btn.setEnabled(False)
    
    def hide_loading(self):
        """Esconde barra de progresso"""
        if self.progress_bar:
            self.progress_bar.setVisible(False)
    
    def on_loading_finished(self, node_data, vms_list):
        """Chamado quando o carregamento termina com sucesso"""
        self.hide_loading()
        
        try:
            # Agora cria a MainWindow na thread principal (seguro)
            self.main_window = MainWindow(self.pending_controller)
            
            # Popula com os dados já carregados
            if node_data:
                self.main_window.update_node_metrics(node_data)
            if vms_list:
                self.main_window.update_vms_widgets(vms_list)
            
            # Mostra a janela
            self.main_window.show()
            QTimer.singleShot(100, self.close)
            
        except Exception as e:
            self.on_loading_error(str(e))
    
    def on_loading_error(self, error_msg):
        """Chamado quando ocorre erro no carregamento"""
        self.hide_loading()
        self.connect_btn.setText("Connect")
        self.connect_btn.setEnabled(True)
        QMessageBox.critical(self, "Loading Failed", 
                           f"Unable to load dashboard.\n\nError Details: {error_msg}")