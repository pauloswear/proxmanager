# spice_viewer.py

from typing import Dict, Any

class ViewerConfigGenerator:
    PROXY_PORT = 3128

    def __init__(self, host_ip: str):
        self.host_ip = host_ip

    def _get_optimization_settings(self, configs: Dict[str, Any]) -> Dict[str, str]:
        """ Define os parâmetros de otimização de fluidez SPICE baseado nas configurações """
        
        # Configurações de fluidez baseadas na preferência do usuário
        fluidity_mode = configs.get('spice_fluidity_mode', 'balanced')  # balanced, performance, quality
        
        settings = {}
        
        # Configurações de smartcard e USB redirect baseadas na interface
        smartcard_enabled = "1" if configs.get('spice_smartcard', True) else "0"
        usb_enabled = "1" if configs.get('spice_usbredirect', True) else "0"
        
        if fluidity_mode == 'performance':
            # Configurações para máxima fluidez em conexões lentas
            settings.update({
                "image-compression": "lz4",        # Compressão mais rápida
                "jpeg-compression": "70",          # Mais compressão = menos dados
                "streaming-video": "all",          # Otimiza todos os vídeos
                "playback-compression": "on",      # Compressão de áudio/vídeo
                "ca-file": "",                     # Remove verificação SSL para speed
                "enable-smartcard": smartcard_enabled,
                "enable-usbredir": usb_enabled
            })
        elif fluidity_mode == 'quality':
            # Configurações para máxima qualidade visual
            settings.update({
                "image-compression": "auto_glz",   # Melhor compressão de qualidade
                "jpeg-compression": "auto",        # Qualidade automática
                "streaming-video": "off",          # Sem otimização de vídeo
                "playback-compression": "off",     # Sem compressão de áudio
                "enable-smartcard": smartcard_enabled,
                "enable-usbredir": usb_enabled
            })
        else:  # balanced (padrão)
            # Equilibrio entre qualidade e performance
            settings.update({
                "image-compression": "auto_lz",
                "jpeg-compression": "auto",
                "streaming-video": "filter",       # Filtra apenas vídeos necessários
                "playback-compression": "auto",    # Compressão automática
                "enable-smartcard": smartcard_enabled,
                "enable-usbredir": usb_enabled
            })
            
        return settings

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
            
            # Carregar configurações SPICE
            from utils.config_manager import ConfigManager
            config_manager = ConfigManager()
            configs = config_manager.load_configs()
            
            # Otimizações SPICE baseadas nas configurações
            for key, value in self._get_optimization_settings(configs).items():
                vv_file_content_list.append(f"{key}={value}")
            
            # Configuração de fullscreen baseada nas configurações
            fullscreen_value = "1" if configs.get('spice_fullscreen', False) else "0"
            
            # Configuração de kiosk mode baseada nas configurações
            kiosk_value = "1" if configs.get('spice_kiosk', False) else "0"
            
            # Outros SPICE
            vv_file_content_list.extend([
                f"secure-attention={json_data.get('secure-attention', 'ctrl+alt+end')}",
                f"release-cursor={json_data.get('release-cursor', 'shift+f12')}",
                f"toggle-fullscreen={json_data.get('toggle-fullscreen', 'no')}",
                f"fullscreen={fullscreen_value}",
                f"kiosk={kiosk_value}",
                f"auto-resize=never"
            ])
            
        elif protocol == 'vnc':
            # CAMPOS ESPECÍFICOS VNC
            vv_file_content_list.extend([
                f"port={int(json_data['port'])}",
                f"type=vnc" # O campo tipo VNC é essencial
            ])
            
        return "\n".join(vv_file_content_list).strip()