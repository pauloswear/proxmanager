# controller.py

import os
import tempfile
import subprocess
from time import sleep
from typing import Union, Tuple, Any, Dict, List
from .api_client import ProxmoxAPIClient
from .spice_viewer import ViewerConfigGenerator


# --- CLASSE: ProxmoxController (Orquestra e Lida com o Cliente Local) ---
class ProxmoxController:
    def __init__(self, api_client: ProxmoxAPIClient, config_generator: ViewerConfigGenerator):
        self.api_client = api_client
        self.config_generator = config_generator


    def update_dashboard(self) -> Tuple[Dict[str, Any] | None, List[Dict[str, Any]] | None]:
        """
        Executa todas as chamadas de API necessárias para a atualização completa do dashboard.
        Este método é chamado pela thread de background.
        """
        
        # 1. Obter Status do Node (CPU, RAM, Load)
        # Assumindo que você tem este método implementado no seu ProxmoxAPIClient
        node_status = self.api_client.get_node_status()

        # 2. Obter Lista de VMs/Containers
        # Assumindo que você tem este método implementado no seu ProxmoxAPIClient
        vms_list = self.api_client.get_vms_list()
        
        # O retorno é uma tupla contendo os dois resultados.
        return node_status, vms_list

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
            
            print(f"Iniciando VM {vmid} via {protocol.upper()}...")
            subprocess.Popen([viewer_path, inifile_path]) 
            sleep(5) 
            return True

        except Exception as e:
            print(f"Ocorreu um erro durante a conexão {protocol.upper()}: {e}")
            return False
        
        finally:
            if inifile_path and os.path.exists(inifile_path):
                os.unlink(inifile_path)
                # print(f"Arquivo temporário {inifile_path} removido.")