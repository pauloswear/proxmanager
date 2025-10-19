# utils.py
import ctypes
import os
import json
import traceback 
from typing import Dict, Any
from PyQt5.QtCore import QRunnable, QThreadPool
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


# --- CLASSE WORKER PARA EXECUTAR TAREFAS EM SEGUNDO PLANO ---
class ViewerWorker(QRunnable):
    """
    QRunnable para executar a conexão do viewer (SPICE/VNC) em um thread.
    Isso evita que a GUI congele durante o processo de conexão.
    """
    def __init__(self, controller: ProxmoxController, vmid: int, protocol: str):
        super().__init__()
        self.controller = controller
        self.vmid = vmid
        self.protocol = protocol
        # Garante que o worker seja deletado após a execução
        self.setAutoDelete(True) 

    def run(self):
        """ Lógica que será executada no thread separado. """
        try:
            print(f"Worker: Tentando conectar via {self.protocol.upper()} para VM {self.vmid}...")
            # A chamada que bloqueia a thread principal é movida para aqui
            success = self.controller.start_viewer(self.vmid, protocol=self.protocol)
            
            if not success and self.protocol == 'spice':
                 print(f"Worker: SPICE falhou. Tentando VNC para VM {self.vmid}...")
                 self.controller.start_viewer(self.vmid, protocol='vnc')

        except Exception as e:
            # Captura exceções no thread para depuração
            print(f"ERRO no ViewerWorker para VM {self.vmid}: {e}")
            traceback.print_exc()


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
            import subprocess
            import os
            
            ssh_ip = self.ssh_config['ip']
            ssh_port = self.ssh_config['port']
            ssh_user = self.ssh_config['user']
            
            print(f"Worker: Conectando SSH para VM {self.vmid} ({ssh_user}@{ssh_ip}:{ssh_port})...")
            
            if os.name == 'nt':  # Windows
                # Localiza o caminho do SSH do Windows
                ssh_paths = [
                    r'C:\Windows\System32\OpenSSH\ssh.exe',
                    r'C:\Program Files\OpenSSH\ssh.exe',
                    'ssh'  # Fallback para PATH
                ]
                
                ssh_found = False
                for ssh_path in ssh_paths:
                    try:
                        # Testa se o SSH existe
                        if ssh_path != 'ssh':
                            if not os.path.exists(ssh_path):
                                continue
                        
                        # Abre CMD em nova janela com SSH
                        ssh_cmd = f'start "SSH - VM {self.vmid}" cmd /k "{ssh_path}" {ssh_user}@{ssh_ip} -p {ssh_port}'
                        subprocess.Popen(ssh_cmd, shell=True)
                        ssh_found = True
                        break
                    except Exception:
                        continue
                
                if not ssh_found:
                    # Fallback para PuTTY
                    try:
                        putty_args = ['putty', f'{ssh_user}@{ssh_ip}', '-P', str(ssh_port)]
                        subprocess.Popen(putty_args)
                    except Exception as final_e:
                        print(f"Erro: OpenSSH e PuTTY não encontrados. Instale um cliente SSH. Erro: {final_e}")
            else:  # Linux/Unix
                # Usa terminal nativo
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