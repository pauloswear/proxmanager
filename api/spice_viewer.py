# spice_viewer.py

from typing import Dict, Any

class ViewerConfigGenerator:
    PROXY_PORT = 3128

    def __init__(self, host_ip: str):
        self.host_ip = host_ip

    def _get_optimization_settings(self) -> Dict[str, str]:
        """ Define os parâmetros de otimização de fluidez SPICE """
        return {
            "image-compression": "lz4", 
            "jpeg-compression": "30" 
        }

    def convert_json_to_vv_format(self, json_data: Dict[str, Any]) -> str:
        """ Converte a resposta JSON da API em um arquivo de configuração .vv para SPICE ou VNC. """
        
        # O protocolo vem injetado no JSON pelo ProxmoxController
        protocol = json_data.get('protocol_type', 'spice') # Default para SPICE
        vv_file_content_list = ["[virt-viewer]"]
        
        # Campos Comuns
        host = json_data.get("host") 
        password = json_data["password"]
        title = json_data.get("title", f"Proxmox VM {json_data.get('vmid', '')}")
        delete_this_file = "1" 

        vv_file_content_list.extend([
            f"host={host}",
            f"password={password}",
            f"delete-this-file={delete_this_file}",
            f"title={title}"
        ])

        if protocol == 'spice':
            # CAMPOS ESPECÍFICOS SPICE
            proxy = f"http://{self.host_ip}:{self.PROXY_PORT}" 
            
            vv_file_content_list.extend([
                f"tls-port={int(json_data['tls-port'])}",
                f"host-subject={json_data['host-subject']}",
                f"ca={json_data['ca']}",
                f"type={json_data['type']}", # Deve ser 'spice'
                f"proxy={proxy}",
            ])
            
            # Otimizações SPICE
            for key, value in self._get_optimization_settings().items():
                vv_file_content_list.append(f"{key}={value}")

            # Carregar configurações SPICE
            from utils.config_manager import ConfigManager
            config_manager = ConfigManager()
            configs = config_manager.load_configs()
            
            # Configuração de fullscreen baseada nas configurações
            fullscreen_value = "1" if configs.get('spice_fullscreen', False) else "0"
            
            # Outros SPICE
            vv_file_content_list.extend([
                f"secure-attention={json_data.get('secure-attention', 'ctrl+alt+end')}",
                f"release-cursor={json_data.get('release-cursor', 'shift+f12')}",
                f"toggle-fullscreen={json_data.get('toggle-fullscreen', 'no')}",
                f"fullscreen={fullscreen_value}",
                f"auto-resize=never"
            ])
            
        elif protocol == 'vnc':
            # CAMPOS ESPECÍFICOS VNC
            vv_file_content_list.extend([
                f"port={int(json_data['port'])}",
                f"type=vnc" # O campo tipo VNC é essencial
            ])
            
        return "\n".join(vv_file_content_list).strip()