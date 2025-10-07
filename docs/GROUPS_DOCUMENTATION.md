# Tree Groups System - ProxManager

## Implemented Features

### 1. Tree View
- **Custom TreeWidget** that organizes VMs in expandable groups
- **Visual indicators** with colored icons for VM status
- **Expand/collapse** groups with state persistence
- **Dynamic count** of VMs per group

### 2. Drag & Drop
- **Drag VMs** between groups by simply dragging and dropping
- **Automatic detection** of target group
- **Visual feedback** during dragging
- **Automatic persistence** of changes

### 3. Group Management
- **Context menu** (right-click) for:
  - Create new groups
  - Rename existing groups
  - Delete groups (VMs go to "Ungrouped")
  - Expand/collapse all groups
- **Remove VMs** from specific groups

### 4. Integration with Existing System
- **Integrated VMWidget** within tree maintaining all functionality
- **Automatic update** when actions are performed on VMs
- **Synchronization** with MainWindow update system

## How to Use

### Drag and Drop
1. Click and hold any VM in the tree
2. Drag to desired group
3. Drop to move VM to the group
4. Change is saved automatically

### Manage Groups
1. **Create Group**: Right-click on empty area → "Create New Group"
2. **Rename**: Right-click on group → "Rename Group"  
3. **Delete**: Right-click on group → "Delete Group"
4. **Remove VM**: Right-click on VM → "Remove from Group"

### Expand/Collapse
- **Click folder icon** of group to expand/collapse
- **Context menu** offers "Expand All" and "Collapse All"
- **Persistent state** - groups remember if they were expanded

## Configuration Files

Group configurations are saved in:
```
./resources/vm_groups.json
```

Format:
```json
{
    "groups": {
        "Production": [100, 101, 102],
        "Development": [200, 201],
        "Testing": [300]
    },
    "ungrouped_vms": [999]
}
```

## Technical Structure

### Main Files
- `interface/tree_widget.py` - Main tree widget
- `interface/groups.py` - Group manager and persistence
- `interface/main_window.py` - Main window integration
- `interface/widgets.py` - VMWidget adapted for tree

### Main Classes
- `VMTreeWidget` - Main tree widget
- `GroupManager` - Manages groups and persistence
- `GroupItem` - Tree item for groups
- `DraggableVMItem` - Tree item for draggable VMs

## Benefits

1. **Visual Organization** - VMs organized by purpose/environment
2. **Ease of Use** - Intuitive drag & drop interface
3. **Persistence** - Groups maintained between sessions
4. **Flexibility** - Easy reorganization and management
5. **Complete Integration** - Works with all existing functionalities

## Possible Future Improvements

- Nested groups (subgroups)
- Import/export group configurations
- Filters and search in tree
- Batch actions per group
- Pre-defined group templates