"""
Config Manager - Handles JSON configuration files for ProxManager
"""

import json
import os
from typing import Dict, Any


class ConfigManager:
    """Manages application configuration files"""
    
    def __init__(self, base_path: str = "resources"):
        self.base_path = base_path
        self.configs_file = os.path.join(base_path, "configs.json")
        self.login_file = os.path.join(base_path, "login.json")
    
    def load_configs(self) -> Dict[str, Any]:
        """Load application configurations"""
        try:
            if os.path.exists(self.configs_file):
                with open(self.configs_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading configs: {e}")
        
        # Default configurations
        return {
            "timer_interval": 300,
            "auto_refresh": True,
            "auto_login": False,
            "window": {
                "width": 1200,
                "height": 800,
                "maximized": False
            }
        }
    
    def save_configs(self, configs: Dict[str, Any]) -> bool:
        """Save application configurations"""
        try:
            os.makedirs(self.base_path, exist_ok=True)
            with open(self.configs_file, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving configs: {e}")
            return False
    
    def load_login_data(self) -> Dict[str, Any]:
        """Load login credentials"""
        try:
            if os.path.exists(self.login_file):
                with open(self.login_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading login data: {e}")
        
        # Default login data
        return {
            "host_ip": "",
            "user": "",
            "password": "",
            "totp": None,
            "auto_login": False
        }
    
    def save_login_data(self, login_data: Dict[str, Any]) -> bool:
        """Save login credentials"""
        try:
            os.makedirs(self.base_path, exist_ok=True)
            with open(self.login_file, 'w', encoding='utf-8') as f:
                json.dump(login_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving login data: {e}")
            return False
    
    def get_config_value(self, key: str, default=None):
        """Get specific configuration value"""
        configs = self.load_configs()
        keys = key.split('.')
        
        current = configs
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def set_config_value(self, key: str, value: Any) -> bool:
        """Set specific configuration value"""
        configs = self.load_configs()
        keys = key.split('.')
        
        current = configs
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
        return self.save_configs(configs)