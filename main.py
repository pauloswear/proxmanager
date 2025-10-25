import sys
import os
import atexit
import tempfile
import subprocess
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QIcon, QColor, QPalette
from PyQt5.QtCore import QSettings, Qt
from interface import LoginWindow

# Configurações globais da Aplicação
APP_ORGANIZATION = "PyQtProxmoxApp"
APP_NAME = "ProxManager"
ICON_PATH = "./resources/favicon.ico"
LOCKFILE_PATH = os.path.join(tempfile.gettempdir(), "proxmanager.lock")

def create_lockfile():
    """Cria o arquivo de lock com o PID do processo atual"""
    try:
        if os.path.exists(LOCKFILE_PATH):
            # Verifica se o processo ainda está rodando
            with open(LOCKFILE_PATH, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Verifica se o processo ainda existe
            if is_process_running(old_pid):
                return False  # Processo ainda rodando
            else:
                # Remove lockfile órfão
                os.remove(LOCKFILE_PATH)
        
        # Cria novo lockfile
        with open(LOCKFILE_PATH, 'w') as f:
            f.write(str(os.getpid()))
        
        # Registra função para remover lockfile ao sair
        atexit.register(remove_lockfile)
        return True
        
    except Exception as e:
        print(f"Erro ao criar lockfile: {e}")
        return False

def remove_lockfile():
    """Remove o arquivo de lock"""
    try:
        if os.path.exists(LOCKFILE_PATH):
            os.remove(LOCKFILE_PATH)
    except Exception as e:
        print(f"Erro ao remover lockfile: {e}")

def is_process_running(pid):
    """Verifica se um processo está rodando pelo PID"""
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                  capture_output=True, text=True)
            return str(pid) in result.stdout
        
        else:  # Unix/Linux
            os.kill(pid, 0)
            return True
    
    except (OSError, subprocess.SubprocessError):
        return False

def show_already_running_message():
    """Exibe mensagem informando que a aplicação já está rodando"""
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("ProxManager")
    msg.setText("ProxManager is already running!")
    msg.setInformativeText("Only one instance of the application can be executed at a time.")
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()
    
    sys.exit(1)

def apply_dark_theme(app: QApplication):
    """ Aplica o tema dark (Fusion) na aplicação. """
    app.setStyle('Fusion')
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(18, 18, 18))
    palette.setColor(QPalette.AlternateBase, QColor(30, 30, 30))
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(40, 40, 40))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.Highlight, QColor(0, 163, 204))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(palette)

def main():
    """ Ponto de entrada principal da aplicação. """
    
    # Verificar se já há uma instância rodando
    if not create_lockfile():
        show_already_running_message()
        return
    
    # 1. Configurações de aplicação para QSettings
    QApplication.setOrganizationName(APP_ORGANIZATION) 
    QApplication.setApplicationName(APP_NAME)
    
    app = QApplication(sys.argv)
    
    # 2. Configurações de visual
    apply_dark_theme(app)

    # 3. Ícone
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))
    else:
        print(f"Aviso: O arquivo de ícone '{ICON_PATH}' não foi encontrado.")
    
    # 4. Inicia pela tela de login
    login_window = LoginWindow()
    login_window.show() 
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()