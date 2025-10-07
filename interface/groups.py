import json
import os
from typing import Dict, List, Any

# Define the configuration file name for groups
CONFIG_FILE = './resources/vm_groups.json'

class GroupManager:
    """
    Manages reading and writing VM groups.
    Data format: 
    {
        "group_name": [vmid1, vmid2, ...],
        "Other Group": [vmid3, ...]
    }
    """
    
    def __init__(self):
        # Main data structure, initialized empty or loaded
        self.groups: Dict[str, List[int]] = {}
        # List of VMs that don't belong to any group
        self.ungrouped_vms: List[int] = []
        # Order of groups for display (group names list)
        self.group_order: List[str] = []
        # Estado de expansão dos grupos
        self.group_expansion_state: Dict[str, bool] = {}
        self.load_groups()

    def load_groups(self):
        """Loads group data from JSON file."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Load defined groups
                    self.groups = data.get('groups', {})
                    
                    # Load ungrouped VMs
                    self.ungrouped_vms = data.get('ungrouped_vms', [])
                    
                    # Load group order
                    self.group_order = data.get('group_order', [])
                    
                    # Load group expansion state
                    self.group_expansion_state = data.get('group_expansion_state', {})

                print(f"Groups loaded from {CONFIG_FILE}.")
            except json.JSONDecodeError:
                print(f"Error reading JSON from {CONFIG_FILE}. Initializing empty.")
            except Exception as e:
                print(f"Error loading groups: {e}")
        else:
            print(f"Configuration file {CONFIG_FILE} not found. Initializing empty.")

    def save_groups(self):
        """Saves the current group structure to JSON file."""
        # Carregar dados existentes para preservar group_expansion_state
        existing_data = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except:
                pass
        
        data = {
            'groups': self.groups,
            'ungrouped_vms': self.ungrouped_vms,
            'group_order': self.group_order,
            'group_expansion_state': existing_data.get('group_expansion_state', {})
        }
        try:
            # Create 'resources' folder if it doesn't exist
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True) 
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"Groups saved to {CONFIG_FILE}.")
        except Exception as e:
            print(f"Error saving groups: {e}")

    # --- Group Manipulation Methods ---
    
    def add_vm_to_group(self, vmid: int, group_name: str):
        """Adds a VM to a group, removing it from another if necessary."""
        vmid = int(vmid)
        group_name = group_name.strip()
        
        # 1. Remove from any other group (including ungrouped)
        self.remove_vm_from_groups(vmid)
            
        if not group_name:
            # If group name is empty, move to ungrouped
            if vmid not in self.ungrouped_vms:
                self.ungrouped_vms.append(vmid)
        else:
            # 2. Create group if it doesn't exist
            if group_name not in self.groups:
                self.groups[group_name] = []
                # Add to group order if new group
                if group_name not in self.group_order:
                    self.group_order.append(group_name)
                
            # 3. Add VM to new group
            if vmid not in self.groups[group_name]:
                self.groups[group_name].append(vmid)

    def remove_vm_from_groups(self, vmid: int):
        """Removes VM from all groups and ungrouped list."""
        vmid = int(vmid)
        
        # Remove from named groups
        for group in self.groups.values():
            if vmid in group:
                group.remove(vmid)
                
        # Remove from ungrouped list
        if vmid in self.ungrouped_vms:
            self.ungrouped_vms.remove(vmid)
            
        # Note: We keep empty groups to allow user-created empty groups
        # Groups are only removed when explicitly deleted by user

    def get_group_for_vm(self, vmid: int) -> str | None:
        """Returns the name of the group the VM belongs to, or None."""
        vmid = int(vmid)
        if vmid in self.ungrouped_vms:
            # If VM is explicitly in 'ungrouped', consider it without group
            return None 
            
        for group_name, vms in self.groups.items():
            if vmid in vms:
                return group_name
        return None
        
    def get_all_group_names(self) -> List[str]:
        """Returns a list with all defined group names."""
        return list(self.groups.keys())
    
    def set_group_order(self, order: List[str]):
        """Sets the display order of groups."""
        # Validate that all groups in order exist
        valid_groups = [group for group in order if group in self.groups]
        
        # Add any missing groups to the end
        for group_name in self.groups.keys():
            if group_name not in valid_groups:
                valid_groups.append(group_name)
        
        self.group_order = valid_groups
    
    def get_group_order(self) -> List[str]:
        """Gets the current display order of groups."""
        # Ensure all existing groups are in the order list
        for group_name in self.groups.keys():
            if group_name not in self.group_order:
                self.group_order.append(group_name)
        
        # Remove any groups that no longer exist
        self.group_order = [group for group in self.group_order if group in self.groups]
        
        return self.group_order.copy()

    def delete_group(self, group_name: str):
        """
        Deletes a group and moves its VMs to the ungrouped list.
        """
        if group_name in self.groups:
            # Move all VMs to ungrouped list
            for vmid in self.groups[group_name]:
                if vmid not in self.ungrouped_vms:
                    self.ungrouped_vms.append(vmid)
                    
            del self.groups[group_name]
            # Remove from group order as well
            if group_name in self.group_order:
                self.group_order.remove(group_name)
            self.save_groups()
            return True
        return False
        
    def get_vms_grouped_by_name(self, all_vms: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Organizes the complete VM list by their defined groups.
        This is crucial for MainWindow/Dashboard rendering logic.
        """
        grouped_vms: Dict[str, List[Dict[str, Any]]] = {}
        
        # Map VMs by ID for quick access
        vms_by_id = {int(vm.get('vmid', -1)): vm for vm in all_vms}
        
        # 1. Process Named Groups
        for group_name, vm_ids in self.groups.items():
            vm_list = []
            for vmid in vm_ids:
                if vmid in vms_by_id:
                    vm_list.append(vms_by_id[vmid])
                    
            # Always add group, even if empty, to show all created groups
            grouped_vms[group_name] = vm_list
                
        # 2. Process Ungrouped VMs
        assigned_vms = set()
        for vms in self.groups.values():
            assigned_vms.update(vms)
            
        final_ungrouped_list = []
        for vm in all_vms:
            vmid = int(vm.get('vmid', -1))
            if vmid not in assigned_vms:
                # If not in ANY named group, goes to Ungrouped
                final_ungrouped_list.append(vm)

        if final_ungrouped_list:
            grouped_vms["Não Agrupadas"] = final_ungrouped_list
            
        return grouped_vms

    def get_group_expansion_state(self) -> Dict[str, bool]:
        """Obtém o estado de expansão dos grupos do arquivo JSON."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('group_expansion_state', {})
            except Exception as e:
                print(f"Error loading group expansion state: {e}")
        return {}

    def save_group_expansion_state(self, expansion_state: Dict[str, bool]):
        """Salva o estado de expansão dos grupos no arquivo JSON."""
        try:
            # Carregar dados existentes
            existing_data = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            
            # Atualizar apenas o estado de expansão
            existing_data['group_expansion_state'] = expansion_state
            
            # Salvar de volta
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4)
                
            print(f"Group expansion state saved to {CONFIG_FILE}.")
        except Exception as e:
            print(f"Error saving group expansion state: {e}")