#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Teste para verificar dados da API do Proxmox
"""

import sys
sys.path.append('.')
from api.api_client import ProxmoxAPIClient
from utils.config_manager import ConfigManager

def test_api_data():
    # Carregar configurações
    config_manager = ConfigManager()
    configs = config_manager.load_configs()

    # Criar cliente API
    client = ProxmoxAPIClient(
        host=configs.get('host', 'localhost'),
        user=configs.get('user', 'root@pam'),
        password=configs.get('password', ''),
        node=configs.get('node', 'pve')
    )

    # Buscar VMs
    vms = client.get_vms_list()
    print('VMs encontradas:')
    for vm in vms[:3]:  # Mostra apenas as primeiras 3
        print(f'VM {vm.get("vmid")}: {vm.get("name")}')
        print(f'  Tipo: {vm.get("type")}')
        print(f'  Status: {vm.get("status")}')
        print(f'  OSType: {vm.get("ostype")}')
        print(f'  Template: {vm.get("template")}')
        print(f'  Todas as chaves: {list(vm.keys())}')
        print()

if __name__ == "__main__":
    test_api_data()