import sys
import os
import atexit
import tempfile
import subprocess
import socket
import threading
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QIcon, QColor, QPalette
from PyQt5.QtCore import QSettings, Qt
from interface import LoginWindow

# Configurações globais da Aplicação
APP_ORGANIZATION = "PyQtProxmoxApp"
APP_NAME = "ProxManager"
ICON_PATH = "./resources/favicon.ico"
SOCKET_PORT = 49152  # Porta para verificar instância única

# Variável global para manter referência do socket
app_socket = None

def create_socket_lock():
    """Cria um socket para verificar se a aplicação já está rodando"""
    global app_socket
    try:
        # Tenta criar e fazer bind em uma porta específica
        app_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        app_socket.bind(('localhost', SOCKET_PORT))
        app_socket.listen(1)
        
        # Registra função para fechar socket ao sair
        atexit.register(close_socket_lock)
        return True
        
    except socket.error:
        # Porta já está em uso, aplicação já está rodando
        return False
    except Exception as e:
        print(f"Erro ao criar socket lock: {e}")
        return False

def close_socket_lock():
    """Fecha o socket lock"""
    global app_socket
    try:
        if app_socket:
            app_socket.close()
            app_socket = None
    except Exception as e:
        print(f"Erro ao fechar socket lock: {e}")

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
    
    # Verificar se já há uma instância rodando usando socket
    if not create_socket_lock():
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