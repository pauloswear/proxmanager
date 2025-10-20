# controller.py
import platform
import os
import tempfile
import subprocess
import shutil
from time import sleep
from typing import Union, Tuple, Any, Dict, List, Optional
from .api_client import ProxmoxAPIClient
from .spice_viewer import ViewerConfigGenerator


# --- CLASSE: ProxmoxController (Orquestra e Lida com o Cliente Local) ---
class ProxmoxController:
    def __init__(self, api_client: ProxmoxAPIClient, config_generator: ViewerConfigGenerator):
        self.api_client = api_client
        self.config_generator = config_generator


    def update_dashboard(self) -> Tuple[Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
        """
        Coleta dados do Node e de todas as VMs/Containers, buscando métricas
        precisas de memória para cada VM.
        (Executado na thread de background)
        """
        
        node_status = None
        vms_list = None
        updated_vms_list = []
        
        try:
            # 1. Obter Status do Node (CPU, RAM, Uptime)
            node_status = self.api_client.get_node_status()

            # 2. Obter Lista de VMs/Containers (Dados básicos)
            vms_list = self.api_client.get_vms_list()
            
            # 3. Iterar e enriquecer os dados com a chamada /status/current e informações de rede
            if vms_list:
                for vm in vms_list:
                    vmid = vm.get('vmid')
                    vm_type = vm.get('type')
                    
                    if vmid is None or vm_type is None:
                        continue 
                        
                    # Busca os dados mais detalhados de RAM/CPU no endpoint /status/current
                    # ⭐️ ESTA É A CHAMADA CHAVE QUE VOCÊ QUER USAR
                    detailed_status = self.api_client.get_vm_current_status(vmid, vm_type)
                    
                    if detailed_status:
                        # Substitui as métricas básicas (mem/maxmem/cpu) pelas mais precisas
                        # Isso garante que o VMWidget use a fonte correta
                        vm.update(detailed_status)
                    
                    # Busca ostype da configuração da VM para detectar se é Linux
                    vm_config = self.api_client.get_vm_config(vmid, vm_type)
                    if vm_config and 'ostype' in vm_config:
                        vm['ostype'] = vm_config['ostype']
                    
                    # Busca informações de rede (IP addresses) apenas se a VM estiver rodando
                    if vm.get('status') == 'running':
                        try:
                            ip_addresses = self.api_client.get_vm_network_info(vmid, vm_type)
                            vm['ip_addresses'] = ip_addresses
                        except Exception as e:
                            vm['ip_addresses'] = []
                    else:
                        vm['ip_addresses'] = []
                        
                    updated_vms_list.append(vm)

        except Exception as e:
            # Em caso de erro de API, permite que a thread_error da MainWindow lide com isso.
            raise e
            
        # Retorna os dados do Node e a lista de VMs enriquecida
        return node_status, updated_vms_list



    def _get_remote_viewer_path(self):
        """ Obtém o caminho para o executável do visualizador remoto (remote-viewer) """
        # ... (código de detecção de path omitido, mantém o que está no seu exemplo) ...
        if os.name == 'nt':
            try:
                program_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
                viewer_path = os.path.join(program_files, 'VirtViewer', 'bin', 'remote-viewer.exe')
                if os.path.exists(viewer_path): return viewer_path
            except: pass
            try:
                result = subprocess.check_output('ftype VirtViewer.vvfile', shell=True)
                cmdresult = result.decode('utf-8')
                cmdparts = cmdresult.split('=')
                path = cmdparts[1].strip().split('"')[1]
                return path
            except: return None
        elif os.name == 'posix':
            cmd1 = 'which remote-viewer'
            try:
                result = subprocess.check_output(cmd1, shell=True)
                return result.decode('utf-8').strip()
            except subprocess.CalledProcessError: return None
        return None

    def start_viewer(self, vmid: Union[str, int], protocol: str = 'spice') -> bool:
        """
        Inicia a conexão (SPICE ou VNC), cria e limpa o arquivo temporário.
        Retorna True em caso de sucesso, False em caso de falha (ex: VM sem o protocolo).
        """
        viewer_path = self._get_remote_viewer_path()
        # Para RDP, noVNC e SSH, não precisamos do remote-viewer
        if protocol not in ['rdp', 'novnc', 'ssh'] and not viewer_path:
            print("ERRO: O executável 'remote-viewer' ou 'virt-viewer' não foi encontrado.")
            return False

        inifile_path = None
        
        try:
            # 1. Obtém a configuração do servidor baseada no protocolo
            if protocol == 'rdp':
                # RDP tem tratamento especial
                config_json = self.api_client.get_rdp_config(vmid)
                
                if not config_json.get('ip'):
                    print(f"Erro: IP não disponível para VM {vmid}. Certifique-se que o guest-agent está ativo.")
                    return False
                
                # Inicia conexão RDP usando mstsc (Windows) ou rdesktop (Linux)
                rdp_ip = config_json['ip']
                rdp_port = config_json['port']
                
                if os.name == 'nt':  # Windows
                    # Usa o cliente RDP nativo do Windows (mstsc)
                    rdp_args = ['mstsc', f'/v:{rdp_ip}:{rdp_port}']
                    print(f"Iniciando VM {vmid} via RDP ({rdp_ip}:{rdp_port})...")
                    subprocess.Popen(rdp_args)
                else:  # Linux/Unix
                    # Tenta usar rdesktop ou xfreerdp
                    try:
                        # Primeiro tenta xfreerdp
                        rdp_args = ['xfreerdp', f'/v:{rdp_ip}:{rdp_port}', '/cert-tofu']
                        subprocess.Popen(rdp_args)
                    except FileNotFoundError:
                        try:
                            # Fallback para rdesktop
                            rdp_args = ['rdesktop', f'{rdp_ip}:{rdp_port}']
                            subprocess.Popen(rdp_args)
                        except FileNotFoundError:
                            print("Erro: Cliente RDP não encontrado. Instale xfreerdp ou rdesktop.")
                            return False
                    print(f"Iniciando VM {vmid} via RDP ({rdp_ip}:{rdp_port})...")
                
                return True
                
            elif protocol == 'novnc':
                # noVNC abre no navegador web
                config_json = self.api_client.get_novnc_config(vmid)
                
                if not config_json.get('url'):
                    print(f"Erro: URL noVNC não disponível para VM {vmid}.")
                    return False
                
                # Abre a URL do noVNC no navegador padrão
                novnc_url = config_json['url']
                print(f"Abrindo VM {vmid} via noVNC ({novnc_url})...")
                
                try:
                    import webbrowser
                    webbrowser.open(novnc_url)
                    return True
                except Exception as e:
                    print(f"Erro ao abrir noVNC no navegador: {e}")
                    return False
                
            elif protocol == 'ssh':
                # SSH abre terminal/cliente SSH
                config_json = self.api_client.get_ssh_config(vmid)
                
                if not config_json.get('ip'):
                    print(f"Erro: IP não disponível para VM {vmid}. Certifique-se que o guest-agent está ativo.")
                    return False
                
                ssh_ip = config_json['ip']
                ssh_port = config_json['port']
                default_user = config_json['default_user']
                
                print(f"Iniciando SSH para VM {vmid} ({default_user}@{ssh_ip}:{ssh_port})...")

                if os.name == 'nt':  # Windows
                    try:
                        # Adiciona o caminho do OpenSSH no PATH se necessário
                        if platform.architecture()[0] == "32bit" and os.name == "nt":
                            os.environ["PATH"] += r";C:\Windows\Sysnative\OpenSSH"
                        

                        # Usa start para abrir nova janela do CMD com SSH
                        ssh_cmd = f'start "SSH - VM {vmid}" cmd /k ssh {default_user}@{ssh_ip} -P {ssh_port}'
                        print(f"Executando: {ssh_cmd}")
                        os.system(ssh_cmd)
                        print(f"SSH conectando para {default_user}@{ssh_ip}:{ssh_port}")
                        return True
                    except Exception as e:
                        print(f"Erro ao executar SSH: {e}")
                        
                        # Fallback para PuTTY se SSH não funcionar
                        try:
                            putty_path = shutil.which('putty')
                            if putty_path or os.path.exists(r'C:\Program Files\PuTTY\putty.exe'):
                                putty_exe = putty_path or r'C:\Program Files\PuTTY\putty.exe'
                                putty_args = [putty_exe, f'{default_user}@{ssh_ip}', '-P', str(ssh_port)]
                                subprocess.Popen(putty_args)
                                print(f"SSH conectando via PuTTY: {putty_exe}")
                                return True
                        except Exception:
                            pass
                        
                        print("Erro: SSH e PuTTY não funcionaram. Verifique se o OpenSSH está instalado.")
                        return False
                else:  # Linux/Unix
                    # Usa terminal nativo
                    terminal_cmds = [
                        ['gnome-terminal', '--', 'ssh', f'{default_user}@{ssh_ip}', '-p', str(ssh_port)],
                        ['konsole', '-e', 'ssh', f'{default_user}@{ssh_ip}', '-p', str(ssh_port)],
                        ['xterm', '-e', 'ssh', f'{default_user}@{ssh_ip}', '-p', str(ssh_port)]
                    ]
                    
                    for cmd in terminal_cmds:
                        try:
                            subprocess.Popen(cmd)
                            break
                        except FileNotFoundError:
                            continue
                    else:
                        print("Erro: Terminal não encontrado. Instale gnome-terminal, konsole ou xterm.")
                        return False
                
                return True
                
            else:
                # SPICE e VNC usam o remote-viewer
                if protocol == 'spice':
                    config_json = self.api_client.get_spice_config(vmid)
                elif protocol == 'vnc':
                    config_json = self.api_client.get_vnc_config(vmid)
                else:
                    raise ValueError(f"Protocolo desconhecido: {protocol}")
                
                # Adiciona o tipo de protocolo no JSON para que o ViewerConfigGenerator saiba o que fazer
                config_json['protocol_type'] = protocol
                    
                # 2. Gera o conteúdo .vv formatado
                vv_content = self.config_generator.convert_json_to_vv_format(config_json)
                
                # 3. Cria e executa o arquivo temporário
                with tempfile.NamedTemporaryFile(mode='w+t', suffix='.vv', delete=False, encoding="utf-8") as temp_file:
                    temp_file.write(vv_content)
                    inifile_path = temp_file.name
                
                # 4. Carregar configurações SPICE
                from utils.config_manager import ConfigManager
                config_manager = ConfigManager()
                configs = config_manager.load_configs()
                
                # Preparar argumentos para o viewer
                viewer_args = [viewer_path]
                
                # Auto-resize baseado na configuração
                if configs.get('spice_autoresize', False):
                    viewer_args.append("--auto-resize=always")
                else:
                    viewer_args.append("--auto-resize=never")
                
                viewer_args.append(inifile_path)
                
                print(f"Iniciando VM {vmid} via {protocol.upper()}...")
                subprocess.Popen(viewer_args) 
                sleep(5) 
                return True

        except Exception as e:
            print(f"Ocorreu um erro durante a conexão {protocol.upper()}: {e}")
            return False
        
        finally:
            if inifile_path and os.path.exists(inifile_path):
                os.unlink(inifile_path)
                # print(f"Arquivo temporário {inifile_path} removido.")