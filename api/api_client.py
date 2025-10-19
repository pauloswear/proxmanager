from proxmoxer import ProxmoxAPI
from typing import Union, Dict, Any, List


# --- CLASSE: ProxmoxAPIClient (Lida com a API Remota) ---
class ProxmoxAPIClient:
    def __init__(self, host, user, password, totp):
        self.host = host
        self.user = user
        self.password = password
        self.totp = totp
        self.proxmox = self._connect()
        # Detecta automaticamente o node correto após a conexão
        self.node = self._detect_node()

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

    def _detect_node(self) -> str:
        """
        Detecta automaticamente o node correto.
        Primeiro tenta o node preferido, caso não exista, usa o primeiro disponível.
        """
        available_nodes = self.proxmox.nodes.get()
        node_names = [node['node'] for node in available_nodes]
        
        print(f"Nodes disponíveis: {node_names}")
        
        # Verifica se o node preferido existe
        first_node = node_names[0] if node_names else "pve"
        print(f"Node '{first_node}' encontrado. Usando: '{first_node}'")
        return first_node
            
            
    def get_vms_list(self) -> List[Dict[str, Any]]:
        """ 
        Obtém a lista de todas as VMs e Containers (LXC/QEMU) 
        e anexa a chave 'type' a cada item. 
        Endpoint: /cluster/resources?type=vm
        """
        all_vms = []
        try:
            # Busca todos os recursos de cluster, filtrando por tipo 'vm' 
            # (que inclui tanto qemu quanto lxc)
            resources = self.proxmox.cluster.resources.get(type='vm')
            
            for resource in resources:
                # O resource no Proxmoxer já indica o tipo no campo 'type' (e.g., 'qemu', 'lxc')
                
                # Exemplo: id: "qemu/100", type: "qemu"
                
                # Filtramos apenas os tipos que nos interessam (qemu/lxc)
                if resource.get('type') in ['qemu', 'lxc']:
                    
                    # Garantimos que 'type' esteja na raiz do dicionário para facilitar o Controller
                    vm_data = resource.copy()
                    vm_data['type'] = resource['type'] 
                    
                    # Renomeia 'id' para 'vmid' para padronizar com as outras chamadas
                    # vm_data['vmid'] = int(resource['vmid']) # resource['vmid'] já deve ser o ID
                    
                    # O campo 'id' vem como "qemu/100" ou "lxc/101". O vmid é a parte numérica.
                    # No endpoint de resources, a chave é 'vmid'
                    # Mas se você for testar com o endpoint antigo (qemu.get()), a chave é 'vmid'.
                    # Vamos garantir o vmid como inteiro para usar nas chamadas
                    vm_data['vmid'] = int(vm_data['vmid'])
                    
                    all_vms.append(vm_data)
                    
            return all_vms
        except Exception as e:
            # Usando DEBUG_SIGNAL se você já implementou a janela de debug
            # DEBUG_SIGNAL.message.emit(f"Erro ao obter lista de VMs/LXC: {e}")
            print(f"Erro ao obter lista de VMs/LXC: {e}")
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

    def get_rdp_config(self, vmid: Union[str, int]) -> Dict[str, Any]:
        """ 
        Obtém a configuração RDP para a VM.
        Retorna informações necessárias para conexão RDP.
        """
        try:
            # Para RDP, precisamos do IP da VM e da porta (geralmente 3389)
            vm_config = self.proxmox.nodes(self.node).qemu(str(vmid)).config.get()
            vm_status = self.proxmox.nodes(self.node).qemu(str(vmid)).status.current.get()
            
            # Busca o IP da VM através do guest-agent se disponível
            vm_ip = None
            try:
                agent_info = self.proxmox.nodes(self.node).qemu(str(vmid)).agent('network-get-interfaces').get()
                if 'result' in agent_info:
                    for interface in agent_info['result']:
                        if 'ip-addresses' in interface:
                            for ip_info in interface['ip-addresses']:
                                ip_addr = ip_info.get('ip-address', '')
                                ip_type = ip_info.get('ip-address-type', '')
                                # Pega o primeiro IP IPv4 válido (não loopback)
                                if ip_addr and ip_type == 'ipv4' and not ip_addr.startswith('127.'):
                                    vm_ip = ip_addr
                                    break
                        if vm_ip:
                            break
            except Exception:
                pass
            
            return {
                'vmid': vmid,
                'ip': vm_ip,
                'port': 3389,  # Porta padrão do RDP
                'name': vm_config.get('name', f'VM-{vmid}'),
                'status': vm_status.get('status', 'unknown')
            }
        except Exception as e:
            print(f"Erro ao obter configurações RDP para VM {vmid}: {e}")
            return {
                'vmid': vmid,
                'ip': None,
                'port': 3389,
                'name': f'VM-{vmid}',
                'status': 'unknown'
            }

    def get_novnc_config(self, vmid: Union[str, int]) -> Dict[str, Any]:
        """ 
        Obtém a configuração noVNC para a VM.
        Gera um proxy VNC temporário e retorna a URL do noVNC.
        """
        try:
            # Gera um proxy VNC temporário
            vnc_config = self.proxmox.nodes(self.node).qemu(str(vmid)).vncproxy.post()
            
            # Constrói a URL do noVNC
            # O Proxmox geralmente serve o noVNC em: https://{host}:8006/?console=kvm&novnc=1&vmid={vmid}&node={node}
            novnc_url = f"https://{self.host}:8006/?console=kvm&novnc=1&vmid={vmid}&node={self.node}"
            
            return {
                'vmid': vmid,
                'url': novnc_url,
                'host': self.host,
                'port': vnc_config.get('port', 5900),
                'ticket': vnc_config.get('ticket', ''),
                'protocol_type': 'novnc'
            }
        except Exception as e:
            print(f"Erro ao obter configurações noVNC para VM {vmid}: {e}")
            return {
                'vmid': vmid,
                'url': None,
                'host': self.host,
                'port': 5900,
                'ticket': '',
                'protocol_type': 'novnc'
            }

    def get_ssh_config(self, vmid: Union[str, int]) -> Dict[str, Any]:
        """ 
        Obtém a configuração SSH para a VM.
        Detecta IP, sistema operacional e sugere usuário apropriado.
        """
        try:
            vm_config = self.proxmox.nodes(self.node).qemu(str(vmid)).config.get()
            vm_status = self.proxmox.nodes(self.node).qemu(str(vmid)).status.current.get()
            
            # Busca o IP da VM através do guest-agent
            vm_ip = None
            os_info = None
            try:
                agent_info = self.proxmox.nodes(self.node).qemu(str(vmid)).agent('network-get-interfaces').get()
                if 'result' in agent_info:
                    for interface in agent_info['result']:
                        if 'ip-addresses' in interface:
                            for ip_info in interface['ip-addresses']:
                                ip_addr = ip_info.get('ip-address', '')
                                ip_type = ip_info.get('ip-address-type', '')
                                # Pega o primeiro IP IPv4 válido (não loopback)
                                if ip_addr and ip_type == 'ipv4' and not ip_addr.startswith('127.'):
                                    vm_ip = ip_addr
                                    break
                        if vm_ip:
                            break
                
                # Tenta detectar o OS via guest-agent
                try:
                    os_info = self.proxmox.nodes(self.node).qemu(str(vmid)).agent('get-osinfo').get()
                except Exception:
                    pass
                    
            except Exception:
                pass
            
            # Determina usuário padrão baseado no OS
            default_user = "root"  # Padrão para Linux
            vm_os = "linux"  # Padrão
            
            if os_info and 'result' in os_info:
                os_name = os_info['result'].get('name', '').lower()
                if 'windows' in os_name:
                    default_user = "Administrator"
                    vm_os = "windows"
                elif 'ubuntu' in os_name or 'debian' in os_name:
                    default_user = "ubuntu" if 'ubuntu' in os_name else "debian"
                    vm_os = "linux"
            
            # Detecta pelo nome da VM se não conseguiu via agent
            vm_name = vm_config.get('name', '').lower()
            if 'windows' in vm_name or 'win' in vm_name:
                default_user = "Administrator"
                vm_os = "windows"
            elif 'ubuntu' in vm_name:
                default_user = "ubuntu"
            
            return {
                'vmid': vmid,
                'ip': vm_ip,
                'port': 22,  # Porta padrão SSH
                'default_user': default_user,
                'os_type': vm_os,
                'name': vm_config.get('name', f'VM-{vmid}'),
                'status': vm_status.get('status', 'unknown'),
                'os_info': os_info.get('result', {}) if os_info else {}
            }
        except Exception as e:
            print(f"Erro ao obter configurações SSH para VM {vmid}: {e}")
            return {
                'vmid': vmid,
                'ip': None,
                'port': 22,
                'default_user': 'root',
                'os_type': 'linux',
                'name': f'VM-{vmid}',
                'status': 'unknown',
                'os_info': {}
            }

    def get_vm_config(self, vmid: Union[str, int], vm_type: str) -> Dict[str, Any] | None:
        """
        Busca a configuração completa da VM/Container, incluindo ostype.
        Endpoint: /nodes/{node}/(lxc|qemu)/{vmid}/config
        """
        if vm_type not in ['lxc', 'qemu']:
            print(f"Tipo de VM desconhecido: {vm_type}")
            return None
            
        try:
            if vm_type == 'lxc':
                config_data = self.proxmox.nodes(self.node).lxc(str(vmid)).config.get()
            else:
                config_data = self.proxmox.nodes(self.node).qemu(str(vmid)).config.get()
                
            return config_data
        except Exception as e:
            print(f"Erro ao buscar configuração da {vm_type} {vmid}: {e}")
            return None

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

    def get_vm_network_info(self, vmid: Union[str, int], vm_type: str) -> List[str]:
        """
        Busca informações de rede da VM/Container, incluindo endereços IP.
        Para QEMU VMs: Usa qemu-guest-agent se disponível
        Para LXC: Usa as interfaces de rede do container
        Retorna uma lista de IPs encontrados
        """
        ip_addresses = []

        
        try:
            if vm_type == 'lxc':
                # Para containers LXC, busca as interfaces de rede
                # Endpoint: /nodes/{node}/lxc/{vmid}/interfaces
                interfaces = self.proxmox.nodes(self.node).lxc(str(vmid)).interfaces.get()

                
                for interface in interfaces:

                    # Cada interface pode ter múltiplos IPs
                    if 'inet' in interface and interface['inet']:
                        # Remove a máscara de rede se presente (ex: 192.168.1.100/24 -> 192.168.1.100)
                        ip = interface['inet'].split('/')[0]
                        if ip and ip != '127.0.0.1':
                            ip_addresses.append(ip)
                    if 'inet6' in interface and interface['inet6'] and interface['inet6'] != '::1/128':
                        ip6 = interface['inet6'].split('/')[0]
                        if ip6 != '::1':
                            ip_addresses.append(ip6)
                        
            elif vm_type == 'qemu':
                # Para VMs QEMU, tenta usar o guest-agent
                try:
                    # Endpoint: /nodes/{node}/qemu/{vmid}/agent/network-get-interfaces
                    agent_info = self.proxmox.nodes(self.node).qemu(str(vmid)).agent('network-get-interfaces').get()

                    
                    if 'result' in agent_info:
                        for interface in agent_info['result']:
                            if 'ip-addresses' in interface:
                                for ip_info in interface['ip-addresses']:
                                    ip_addr = ip_info.get('ip-address', '')
                                    ip_type = ip_info.get('ip-address-type', '')
                                    # Filtra apenas IPs válidos (não loopback)
                                    if ip_addr and ip_addr not in ['127.0.0.1', '::1']:
                                        if ip_type == 'ipv4' or ip_type == 'ipv6':
                                            ip_addresses.append(ip_addr)
                                            
                except Exception as e:

                    # Fallback: tenta buscar via config da VM
                    try:
                        config = self.proxmox.nodes(self.node).qemu(str(vmid)).config.get()

                        # Analisa configuração de rede se disponível
                    except Exception as config_e:

                        pass
            

            return ip_addresses
            
        except Exception as e:
            print(f"Erro ao buscar informações de rede da {vm_type} {vmid}: {e}")
            return []