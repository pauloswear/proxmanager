import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon, QColor, QPalette
from PyQt5.QtCore import QSettings, Qt
from interface import LoginWindow

# Configurações globais da Aplicação
APP_ORGANIZATION = "PyQtProxmoxApp"
APP_NAME = "ProxManager"
ICON_PATH = "./resources/favicon.ico"

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