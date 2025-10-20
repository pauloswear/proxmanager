# utils.py
import ctypes
import os
import json
import traceback 
from typing import Dict, Any
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from api import ProxmoxController # Assume que ProxmoxController está acessível

# --- CONSTANTES ---
CONFIG_FILE = "./resources/configs.json"
os.makedirs("./resources", exist_ok=True)  # Garante que o diretório exista 



# Para Windows 10/11 - modo escuro na barra de título
def set_dark_title_bar(hwnd):
    # Ativa o modo escuro na barra de título
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
    set_window_attribute(int(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE, 
                        ctypes.byref(ctypes.c_int(1)), 
                        ctypes.sizeof(ctypes.c_int))



# --- FUNÇÕES DE GERENCIAMENTO DE CONFIGURAÇÃO ---

def load_config() -> Dict[str, Any]:
    """ Carrega as configurações de login do arquivo JSON. """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Aviso: Arquivo configs.json inválido. Criando um novo.")
    
    # Retorna o modelo padrão
    return {
        "host_ip": "100.82.234.124", 
        "user": "root@pam",
        "password": "",
        "totp": None
    }

def save_config(host: str, user: str, password: str, totp: str | None):
    """ Salva as credenciais de login no arquivo JSON. """
    config = {
        "host_ip": host,
        "user": user,
        "password": password,
        "totp": totp
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except IOError as e:
        print(f"Erro ao salvar o arquivo de configuração: {e}")


# --- SINAIS PARA WORKERS ---
class ViewerWorkerSignals(QObject):
    """Sinais para comunicação do ViewerWorker com a thread principal"""
    finished = pyqtSignal(int, int, str)  # (vmid, pid, protocol)
    error = pyqtSignal(int, str)  # (vmid, error_message)


# --- CLASSE WORKER PARA EXECUTAR TAREFAS EM SEGUNDO PLANO ---
class ViewerWorker(QRunnable):
    """
    QRunnable para executar a conexão do viewer (SPICE/VNC/RDP/SSH) em um thread.
    Isso evita que a GUI congele durante o processo de conexão.
    Emite sinais quando o processo é criado com sucesso.
    """
    def __init__(self, controller, vmid: int, protocol: str):
        super().__init__()
        self.controller = controller
        self.vmid = vmid
        self.protocol = protocol
        self.signals = ViewerWorkerSignals()
        # Garante que o worker seja deletado após a execução
        self.setAutoDelete(True) 

    def run(self):
        """ Lógica que será executada no thread separado. """
        try:
            # A chamada que bloqueia a thread principal é movida para aqui
            pid = self.controller.start_viewer(self.vmid, protocol=self.protocol)
            
            if pid:
                # Sucesso! Emite sinal com o PID
                self.signals.finished.emit(self.vmid, pid, self.protocol)
            elif not pid and self.protocol == 'spice':
                # SPICE falhou, tenta VNC
                pid = self.controller.start_viewer(self.vmid, protocol='vnc')
                if pid:
                    self.signals.finished.emit(self.vmid, pid, 'vnc')
                else:
                    self.signals.error.emit(self.vmid, "Falha ao conectar via SPICE e VNC")
            else:
                self.signals.error.emit(self.vmid, f"Falha ao conectar via {self.protocol}")

        except Exception as e:
            # Captura exceções no thread para depuração
            error_msg = f"ERRO no ViewerWorker: {e}"
            print(error_msg)
            traceback.print_exc()
            self.signals.error.emit(self.vmid, error_msg)


class SSHWorker(QRunnable):
    """
    QRunnable para executar conexão SSH com configurações personalizadas.
    """
    def __init__(self, controller: ProxmoxController, vmid: int, ssh_config: dict):
        super().__init__()
        self.controller = controller
        self.vmid = vmid
        self.ssh_config = ssh_config
        self.setAutoDelete(True)

    def run(self):
        """ Executa a conexão SSH com as configurações personalizadas. """
        try:
            import os
            
            ssh_ip = self.ssh_config['ip']
            ssh_port = self.ssh_config['port']
            ssh_user = self.ssh_config['user']
            
            if os.name == 'nt':  # Windows
                # Força uso do OpenSSH do Windows
                openssh_path = r'C:\Windows\System32\OpenSSH\ssh.exe'
                
                if os.path.exists(openssh_path):
                    # Usa OpenSSH oficial do Windows
                    ssh_cmd = f'start "SSH - VM {self.vmid}" cmd /k "{openssh_path}" {ssh_user}@{ssh_ip} -P {ssh_port}'
                else:
                    # Tenta SSH genérico do PATH
                    ssh_cmd = f'start "SSH - VM {self.vmid}" cmd /k ssh {ssh_user}@{ssh_ip} -P {ssh_port}'

                os.system(ssh_cmd)
                
            else:  # Linux/Unix
                # Usa terminal nativo
                import subprocess
                terminal_cmds = [
                    ['gnome-terminal', '--', 'ssh', f'{ssh_user}@{ssh_ip}', '-p', str(ssh_port)],
                    ['konsole', '-e', 'ssh', f'{ssh_user}@{ssh_ip}', '-p', str(ssh_port)],
                    ['xterm', '-e', 'ssh', f'{ssh_user}@{ssh_ip}', '-p', str(ssh_port)]
                ]
                
                for cmd in terminal_cmds:
                    try:
                        subprocess.Popen(cmd)
                        break
                    except FileNotFoundError:
                        continue
                else:
                    print("Erro: Terminal não encontrado. Instale gnome-terminal, konsole ou xterm.")
                    
        except Exception as e:
            print(f"ERRO no SSHWorker para VM {self.vmid}: {e}")
            traceback.print_exc()