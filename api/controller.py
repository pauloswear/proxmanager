# controller.py

import os
import tempfile
import subprocess
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
            
            # 3. Iterar e enriquecer os dados com a chamada /status/current
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
        if not viewer_path:
            print("ERRO: O executável 'remote-viewer' ou 'virt-viewer' não foi encontrado.")
            return False

        inifile_path = None
        
        try:
            # 1. Obtém a configuração do servidor baseada no protocolo
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