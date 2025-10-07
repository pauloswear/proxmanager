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
            api.nodes.get() 
            return api
        except Exception as e:
            # Se houver qualquer falha (rede, SSL, auth), levante a exceção.
            raise Exception(f"Falha de autenticação ou conexão: {e}") 

    def get_vms_list(self) -> List[Dict[str, Any]]:
        """ Obtém a lista de todas as VMs em todos os nodes """
        vms = []
        try:
            for node in self.proxmox.nodes.get():
                # Endpoint: /nodes/{node}/qemu
                vms.extend(self.proxmox.nodes(node["node"]).qemu.get())
            return vms
        except Exception as e:
            print(f"Erro ao obter lista de VMs: {e}")
            return []

    def get_node_status(self) -> Dict[str, Any] | None:
        """
        Busca o status de performance do node (CPU, RAM, disco, uptime).
        Endpoint: /nodes/{self.node}/status
        """
        try:
            # Usando proxmoxer: self.proxmox.nodes('{node}').status.get()
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

    def get_vm_current_status(self, vmid: Union[str, int], vm_type: str) -> Dict[str, Any] | None:
        """
        Busca o status atual ('status/current') da VM (QEMU) ou Container (LXC).
        Este endpoint contém as métricas de memória e CPU mais precisas.
        Endpoint: /nodes/{node}/(lxc|qemu)/{vmid}/status/current
        """
        # Garante que o tipo é 'lxc' ou 'qemu'
        if vm_type not in ['lxc', 'qemu']:
            print(f"Tipo de VM desconhecido: {vm_type}")
            return None
            
        try:
            # Seleciona o endpoint correto (lxc ou qemu)
            if vm_type == 'lxc':
                # Chamada para container LXC (Endpoint: /nodes/{node}/lxc/{vmid}/status/current)
                status_data = self.proxmox.nodes(self.node).lxc(str(vmid)).status.current.get()
            else:
                # Chamada para VM QEMU (Endpoint: /nodes/{node}/qemu/{vmid}/status/current)
                status_data = self.proxmox.nodes(self.node).qemu(str(vmid)).status.current.get()
                
            # O status retornado tem as chaves 'mem' (usado) e 'maxmem' (total)
            return status_data
            
        except Exception as e:
            # Em caso de falha (VMID inexistente, VM desligada, etc.)
            print(f"Erro ao buscar status atual da {vm_type} {vmid}: {e}")
            return None

    # --- FUNÇÕES DE AÇÃO DA VM ---
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
            
    # ⭐️ --- NOVOS MÉTODOS DE CONTROLE DO NODE --- ⭐️

    def restart_node(self):
        """ Reinicia o Node do Proxmox. Endpoint: /nodes/{node}/status/reboot """
        try:
            # A chamada .reboot.post() envia o comando para reiniciar o Node
            self.proxmox.nodes(self.node).status.reboot.post()
            return True
        except Exception as e:
            print(f"Erro ao tentar reiniciar o Node '{self.node}': {e}")
            return False

    def shutdown_node(self):
        """ Desliga o Node do Proxmox. Endpoint: /nodes/{node}/status/shutdown """
        try:
            # A chamada .shutdown.post() envia o comando para desligar o Node
            self.proxmox.nodes(self.node).status.shutdown.post()
            return True
        except Exception as e:
            print(f"Erro ao tentar desligar o Node '{self.node}': {e}")
            return False