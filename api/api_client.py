# api_client.py

from proxmoxer import ProxmoxAPI
from typing import Union, Dict, Any, List


# --- CLASSE: ProxmoxAPIClient (Lida com a API Remota) ---
class ProxmoxAPIClient:
    def __init__(self, host, user, password, totp, node_name="xeon"):
        self.host = host
        self.user = user
        self.password = password
        self.totp = totp
        # Usamos o node_name fixo (ou fornecido) para operações de Node
        self.node = node_name 
        self.proxmox = self._connect()

    def _connect(self) -> ProxmoxAPI:
        """ Conecta à API do Proxmox e valida a autenticação. """
        user_formatted = f"{self.user}@pam" if "@" not in self.user else self.user
        
        try:
            api = ProxmoxAPI(
                host=self.host, 
                user=user_formatted, 
                password=self.password,
                otp=self.totp, 
                verify_ssl=False
            )
            # Tente uma chamada simples (e necessária) para validar a conexão/autenticação
            # Se a autenticação estiver errada, a proxmoxer levanta uma exceção aqui.
            api.nodes.get() 
            return api
        except Exception as e:
            # Se houver qualquer falha (rede, SSL, auth), levante a exceção.
            raise Exception(f"Falha de autenticação ou conexão: {e}") 

    def get_vms_list(self) -> List[Dict[str, Any]]:
        """ Obtém a lista de todas as VMs em todos os nodes """
        vms = []
        try:
            # Note: A proxmoxer lida com o endpoint /nodes.
            for node in self.proxmox.nodes.get():
                # Endpoint: /nodes/{node}/qemu
                vms.extend(self.proxmox.nodes(node["node"]).qemu.get())
            return vms
        except Exception as e:
            print(f"Erro ao obter lista de VMs: {e}")
            return []

    # ⭐️ NOVO MÉTODO: OBTÉM O STATUS DO NODE ⭐️
    def get_node_status(self) -> Dict[str, Any] | None:
        """
        Busca o status de performance do node (CPU, RAM, disco, uptime).
        Endpoint: /nodes/{self.node}/status
        """
        try:
            # Usando proxmoxer: self.proxmox.nodes('{node}').status.get()
            # Retorna as principais métricas do *node* logado
            status_data = self.proxmox.nodes(self.node).status.get()
            return status_data
        except Exception as e:
            print(f"Erro ao buscar status do Node '{self.node}': {e}")
            return None

    def get_spice_config(self, vmid: Union[str, int]) -> Dict[str, Any]:
        """ Obtém a configuração SPICE temporária para a VM """
        return self.proxmox.nodes(self.node).qemu(str(vmid)).spiceproxy.post()

    def get_vnc_config(self, vmid: Union[str, int]) -> Dict[str, Any]:
        """ Obtém a configuração VNC temporária para a VM """
        return self.proxmox.nodes(self.node).qemu(str(vmid)).vncproxy.post()

    # --- FUNÇÕES DE AÇÃO ---
    def stop_vm(self, vmid: Union[str, int]):
        """ Desliga (stop) a VM """
        try:
            self.proxmox.nodes(self.node).qemu(str(vmid)).status.stop.post()
            return True
        except Exception as e:
            print(f"Erro ao desligar VM {vmid}: {e}")
            return False

    def start_vm(self, vmid: Union[str, int]):
        """ Inicia (start) a VM """
        try:
            self.proxmox.nodes(self.node).qemu(str(vmid)).status.start.post()
            return True
        except Exception as e:
            print(f"Erro ao iniciar VM {vmid}: {e}")
            return False

    def reboot_vm(self, vmid: Union[str, int]):
        """ Reinicia (reboot) a VM """
        try:
            self.proxmox.nodes(self.node).qemu(str(vmid)).status.reboot.post()
            return True
        except Exception as e:
            print(f"Erro ao reiniciar VM {vmid}: {e}")
            return False