# tree_widget.py - Custom tree widget for VM groups

from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QHeaderView, QMenu, QAction, QInputDialog, 
    QMessageBox, QAbstractItemView
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QMimeData, QSize, QPoint, QTimer
)
from PyQt5.QtGui import QDrag, QPainter, QPixmap, QIcon, QFont

from .widgets import VMWidget
from .groups import GroupManager
from api import ProxmoxController


class DraggableVMItem(QTreeWidgetItem):
    """Tree widget item representing a VM that can be dragged"""
    
    def __init__(self, vm_data: Dict[str, Any], vm_widget: VMWidget):
        super().__init__()
        self.vm_data = vm_data
        self.vm_widget = vm_widget
        self.vmid = vm_data.get('vmid', -1)
        
        # Configure item - no text since we use custom widget
        self.setData(0, Qt.UserRole, {'type': 'vm', 'vmid': self.vmid, 'vm_data': vm_data})
        
        # Allow dragging
        self.setFlags(self.flags() | Qt.ItemIsDragEnabled)


class GroupWidget(QWidget):
    """Custom widget to display a group"""
    
    expand_clicked = pyqtSignal()
    collapse_clicked = pyqtSignal()
    
    def __init__(self, group_name: str, vm_count: int = 0, is_expanded: bool = True):
        super().__init__()
        self.group_name = group_name
        self.vm_count = vm_count
        self.is_expanded = is_expanded
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("""
            GroupWidget {
                background-color: #383838;
                border-radius: 4px;
                margin: 0px;
                padding: 5px;
            }
            GroupWidget:hover {
                background-color: #454545;
            }
        """)
        self.setFixedHeight(35)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 5, 2, 5)
        
        # Expand/Collapse button
        self.expand_btn = QPushButton()
        self.expand_btn.setFixedSize(20, 20)
        self.expand_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                color: #CCCCCC;
                font-weight: bold;
                font-size: 14px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #555555;
                color: white;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        self.expand_btn.clicked.connect(self.toggle_expansion)
        self.update_expand_button()
        layout.addWidget(self.expand_btn)
        
        # Folder icon
        icon_label = QLabel("📁")
        icon_label.setStyleSheet("font-size: 16px; color: #FFC107;")
        layout.addWidget(icon_label)
        
        # Name and count
        self.text_label = QLabel(f"{self.group_name} ({self.vm_count} VMs)")
        self.text_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        layout.addWidget(self.text_label)
        
        layout.addStretch()
    
    def update_count(self, vm_count: int):
        """Updates the VM count"""
        self.vm_count = vm_count
        self.text_label.setText(f"{self.group_name} ({vm_count} VMs)")
    
    def toggle_expansion(self):
        """Toggles the expansion state and emits appropriate signal"""
        self.is_expanded = not self.is_expanded
        self.update_expand_button()
        
        if self.is_expanded:
            self.expand_clicked.emit()
        else:
            self.collapse_clicked.emit()
    
    def update_expand_button(self):
        """Updates the expand/collapse button appearance"""
        if self.is_expanded:
            self.expand_btn.setText("−")  # Minus sign for collapse
        else:
            self.expand_btn.setText("+")  # Plus sign for expand
    
    def set_expanded(self, expanded: bool):
        """Sets the expansion state without emitting signals"""
        self.is_expanded = expanded
        self.update_expand_button()


class GroupItem(QTreeWidgetItem):
    """Tree widget item representing a group"""
    
    def __init__(self, group_name: str, vm_count: int = 0):
        super().__init__()
        self.group_name = group_name
        self.vm_count = vm_count
        self.setData(0, Qt.UserRole, {'type': 'group', 'group_name': group_name})
        
        # Configure as group item
        self.setFlags(self.flags() | Qt.ItemIsDropEnabled)
        self.setExpanded(True)
    
    def create_widget(self, tree_widget):
        """Creates the custom widget for the group"""
        widget = GroupWidget(self.group_name, self.vm_count, self.isExpanded())
        
        # Connect expansion signals to tree operations
        widget.expand_clicked.connect(lambda: self._expand_group(tree_widget))
        widget.collapse_clicked.connect(lambda: self._collapse_group(tree_widget))
        
        return widget
    
    def _expand_group(self, tree_widget):
        """Expands this group item"""
        self.setExpanded(True)
        tree_widget.expandItem(self)
        # Salva o estado após a expansão
        if hasattr(tree_widget, '_save_expansion_state'):
            tree_widget._save_expansion_state()
    
    def _collapse_group(self, tree_widget):
        """Collapses this group item"""
        self.setExpanded(False)
        tree_widget.collapseItem(self)
        # Salva o estado após o colapso
        if hasattr(tree_widget, '_save_expansion_state'):
            tree_widget._save_expansion_state()
    
    def update_display(self, vm_count: int):
        """Updates the VM count in the widget"""
        self.vm_count = vm_count


class VMTreeWidget(QTreeWidget):
    """Custom tree widget to display VMs organized in groups"""
    
    vm_action_performed = pyqtSignal()
    drag_started = pyqtSignal()
    drag_finished = pyqtSignal()
    
    def __init__(self, controller: ProxmoxController, process_manager):
        super().__init__()
        self.controller = controller
        self.process_manager = process_manager
        self.group_manager = GroupManager()
        self.dragging_item = None  # Track the item being dragged
        self.is_dragging = False   # Flag to prevent updates during drag
        
        # State for hover tracking
        self.mouse_over_widget = False
        self.hover_timer = QTimer()
        self.hover_timer.timeout.connect(self._on_hover_timeout)
        self.hover_timer.setSingleShot(True)
        
        self.setup_tree()
        self.setup_drag_drop()
        self.setup_context_menu()
        self.setup_expansion_signals()
    
    def setup_tree(self):
        """Configures the basic appearance and behavior of the tree"""
        # Remove header
        self.setHeaderHidden(True)
        
        # Allow multiple selection
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # Configure automatic expansion
        self.setRootIsDecorated(True)
        self.setIndentation(30)
        self.setUniformRowHeights(False)
        self.setItemsExpandable(True)
        
        # Estilo
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #1E1E1E;
                border: 1px solid #333333;
                border-radius: 6px;
                color: white;
                font-size: 12px;
                outline: 0;
            }
            QTreeWidget::item {
                padding: 2px 5px;
                border: none;
                margin: 0px;
                background: transparent;
            }
            QTreeWidget::item:selected {
                background-color: transparent;
                border: none;
            }
            QTreeWidget::item:hover {
                background-color: transparent;
            }
            QTreeWidget::branch:has-siblings:!adjoins-item {
                border-image: none;
                border: none;
            }
            QTreeWidget::branch:has-siblings:adjoins-item {
                border-image: none;
                border: none;
            }
            QTreeWidget::branch:!has-children:!has-siblings:adjoins-item {
                border-image: none;
                border: none;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                border-image: none;
                image: none;
                background: transparent;
            }
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                border-image: none;
                image: none;
                background: transparent;
            }
        """)
    
    def setup_expansion_signals(self):
        """Conecta sinais de expansão/colapso para salvar estado"""
        self.itemExpanded.connect(self._on_item_expanded)
        self.itemCollapsed.connect(self._on_item_collapsed)
    
    def _on_item_expanded(self, item):
        """Callback quando um item é expandido"""
        self._save_expansion_state()
    
    def _on_item_collapsed(self, item):
        """Callback quando um item é colapsado"""
        self._save_expansion_state()
    
    def setup_drag_drop(self):
        """Configures drag and drop functionality"""
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDropIndicatorShown(True)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
    
    def startDrag(self, supportedActions):
        """Override to capture the dragging item and signal drag start"""
        self.is_dragging = True
        self.dragging_item = self.currentItem()
        
        # Signal that drag has started (to pause timer)
        self.drag_started.emit()
        
        super().startDrag(supportedActions)
    
    def dragEnterEvent(self, event):
        """Handle drag enter event - accept all drags"""
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.accept()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move event - simplified to accept all valid drags"""
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.accept()
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        """Handle when drag leaves the widget area"""
        self._end_drag_operation()
        event.accept()
    
    def mousePressEvent(self, event):
        """Override to detect drag cancellation"""
        # If we're not dragging and user presses mouse, ensure drag state is clean
        if not self.is_dragging:
            self.dragging_item = None
        super().mousePressEvent(event)
    
    def _end_drag_operation(self):
        """Clean up drag state and signal end of drag"""
        if self.is_dragging:
            self.is_dragging = False
            self.dragging_item = None
            self.drag_finished.emit()
        
    def setup_context_menu(self):
        """Configures the context menu (right-click)"""
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def update_tree(self, vms_list: List[Dict[str, Any]], expand_groups_with_results: bool = False):
        """Updates the tree with a new list of VMs
        
        Args:
            vms_list: List of VM data
            expand_groups_with_results: If True, expands groups that contain VMs (useful for filtering)
        """
        # Don't update during drag & drop operations or when mouse is hovering
        if self.is_dragging or self.mouse_over_widget:
            return
        
        # Save current expansion state (sem sobrescrever o persistido ainda)
        current_expanded_groups = self._get_current_expansion_state()
        
        # Carregar estado persistido do GroupManager
        persistent_expansion_state = self.group_manager.get_group_expansion_state()
        
        # Combinar estado atual com persistido (atual tem prioridade)
        expanded_groups = persistent_expansion_state.copy()
        expanded_groups.update(current_expanded_groups)
            
        scroll_position = self._save_scroll_position()
        selection_state = self._save_selection_state()
        
        # Block signals and disable updates to prevent visual flashing
        self.blockSignals(True)
        self.setUpdatesEnabled(False)
        
        # Clear current tree
        self.clear()
        
        # Get VMs organized by groups
        grouped_vms = self.group_manager.get_vms_grouped_by_name(vms_list)
        
        # Sort groups alphabetically, keeping "Ungrouped" always at the end
        sorted_groups = self._sort_groups(grouped_vms)
        
        # Add groups and VMs to tree
        for group_name, vms in sorted_groups:
            # Create group item
            group_item = GroupItem(group_name, len(vms))
            self.addTopLevelItem(group_item)
            
            # Set custom widget for group
            group_widget = group_item.create_widget(self)
            self.setItemWidget(group_item, 0, group_widget)
            
            # Sort VMs within group by status (running first) then alphabetically
            sorted_vms = self._sort_vms_in_group(vms)
            
            # Add VMs to group
            for vm_data in sorted_vms:
                vm_widget = VMWidget(vm_data, self.controller, self.process_manager)
                vm_widget.action_performed.connect(self.vm_action_performed)
                
                vm_item = DraggableVMItem(vm_data, vm_widget)
                group_item.addChild(vm_item)
                
                # Set custom widget for item
                self.setItemWidget(vm_item, 0, vm_widget)
            
            # Determine expansion state
            should_expand = False
            
            if expand_groups_with_results and len(vms) > 0:
                # Force expand groups that have VMs when filtering
                should_expand = True
            elif group_name in expanded_groups:
                # Restore saved expansion state
                should_expand = expanded_groups[group_name]
            else:
                # Default behavior: expand non-empty groups
                should_expand = len(vms) > 0
            
            group_item.setExpanded(should_expand)
            
            # Update the button state to match the expansion state
            group_widget.set_expanded(should_expand)
        
        # Adjust tree size
        self.resizeColumnToContents(0)
        
        # Restore scroll position and selection before re-enabling updates
        self._restore_scroll_position_immediate(scroll_position)
        self._restore_selection_state(selection_state)
        
        # Re-enable signals and updates to show final result
        self.blockSignals(False)
        self.setUpdatesEnabled(True)
    
    def update_single_vm(self, vm_data: Dict[str, Any]):
        """Updates a single VM widget without rebuilding the entire tree"""
        vmid = vm_data.get('vmid')
        
        # Find the VM item in the tree
        for group_idx in range(self.topLevelItemCount()):
            group_item = self.topLevelItem(group_idx)
            
            for vm_idx in range(group_item.childCount()):
                vm_item = group_item.child(vm_idx)
                
                if isinstance(vm_item, DraggableVMItem):
                    existing_vmid = vm_item.vm_data.get('vmid')
                    
                    if existing_vmid == vmid:
                        # Found the VM, update its widget
                        vm_widget = self.itemWidget(vm_item, 0)
                        if isinstance(vm_widget, VMWidget):
                            vm_widget.update_data(vm_data)
                        return
        
        # VM not found in tree, might be new - do nothing (será adicionada no próximo update completo)
    
    def _sort_vms_in_group(self, vms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sorts VMs within a group by status (running first) then alphabetically"""
        def sort_key(vm: Dict[str, Any]):
            # Priority: running = 0, other status = 1
            status_priority = 0 if vm.get('status', 'unknown') == 'running' else 1
            # Lowercase name for case-insensitive alphabetical sorting
            name = vm.get('name', 'z').lower()
            return (status_priority, name)
        
        return sorted(vms, key=sort_key)
    
    def _sort_groups(self, grouped_vms: Dict[str, List[Dict[str, Any]]]) -> List[tuple]:
        """Sorts groups by custom order or alphabetically, keeping 'Ungrouped' always at the end"""
        groups_list = list(grouped_vms.items())
        
        # Separate "Ungrouped" group from others
        ungrouped = None
        other_groups = []
        
        for group_name, vms in groups_list:
            if group_name == "Não Agrupadas":
                ungrouped = (group_name, vms)
            else:
                other_groups.append((group_name, vms))
        
        # Get custom group order if available
        group_order = self.group_manager.get_group_order()
        
        if group_order:
            # Sort using custom order
            ordered_groups = []
            group_dict = dict(other_groups)
            
            # Add groups in custom order
            for group_name in group_order:
                if group_name in group_dict:
                    ordered_groups.append((group_name, group_dict[group_name]))
            
            # Add any remaining groups not in custom order (alphabetically)
            remaining_groups = [(name, vms) for name, vms in other_groups if name not in group_order]
            remaining_groups.sort(key=lambda x: x[0].lower())
            ordered_groups.extend(remaining_groups)
            
            other_groups = ordered_groups
        else:
            # Sort other groups alphabetically (case-insensitive)
            other_groups.sort(key=lambda x: x[0].lower())
        
        # Add "Ungrouped" at the end, if it exists
        if ungrouped:
            other_groups.append(ungrouped)
        
        return other_groups
    
    def _get_current_expansion_state(self) -> Dict[str, bool]:
        """Gets the current expansion state of groups without saving"""
        state = {}
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item:
                data = item.data(0, Qt.UserRole)
                if data and data.get('type') == 'group':
                    state[data['group_name']] = item.isExpanded()
        return state
    
    def _save_expansion_state(self) -> Dict[str, bool]:
        """Saves the expansion state of groups to persistent storage"""
        state = self._get_current_expansion_state()
        
        # Persistir estado no GroupManager
        self.group_manager.save_group_expansion_state(state)
        
        return state
    
    def _save_scroll_position(self) -> dict:
        """Saves the current scroll position"""
        scrollbar = self.verticalScrollBar()
        return {
            'vertical_value': scrollbar.value(),
            'vertical_max': scrollbar.maximum()
        }
    
    def _restore_scroll_position(self, position_data: dict):
        """Restores the scroll position smoothly without flash"""
        if not position_data:
            return
        
        # Disable scroll bars temporarily to prevent flash
        scrollbar = self.verticalScrollBar()
        
        # Store original scroll bar policy
        original_policy = self.verticalScrollBarPolicy()
        
        # Temporarily hide scroll bar to prevent visual jump
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Use QTimer with multiple attempts for smooth restoration
        from PyQt5.QtCore import QTimer
        
        attempt_count = 0
        max_attempts = 5
        
        def restore_position():
            nonlocal attempt_count
            attempt_count += 1
            
            if scrollbar.maximum() > 0:  # Only restore if there's content to scroll
                old_max = position_data.get('vertical_max', 0)
                old_value = position_data.get('vertical_value', 0)
                
                if old_max > 0:
                    # Calculate percentage and apply to new maximum
                    percentage = old_value / old_max
                    new_value = int(percentage * scrollbar.maximum())
                    scrollbar.setValue(new_value)
                else:
                    scrollbar.setValue(old_value)
                
                # Re-enable scroll bar after restoration
                self.setVerticalScrollBarPolicy(original_policy)
            elif attempt_count < max_attempts:
                # If content not ready yet, try again in a bit
                QTimer.singleShot(20, restore_position)
            else:
                # Give up after max attempts and restore scroll bar
                self.setVerticalScrollBarPolicy(original_policy)
        
        # Start restoration process
        QTimer.singleShot(1, restore_position)
    
    def _restore_scroll_position_immediate(self, position_data: dict):
        """Restores scroll position immediately without timer (for use with setUpdatesEnabled)"""
        if not position_data:
            return
        
        scrollbar = self.verticalScrollBar()
        
        # Calculate new position
        old_max = position_data.get('vertical_max', 0)
        old_value = position_data.get('vertical_value', 0)
        
        if old_max > 0 and scrollbar.maximum() > 0:
            # Calculate percentage and apply to new maximum
            percentage = old_value / old_max
            new_value = int(percentage * scrollbar.maximum())
            scrollbar.setValue(new_value)
        elif old_value <= scrollbar.maximum():
            scrollbar.setValue(old_value)
    
    def _save_selection_state(self) -> Dict[str, Any]:
        """Save current selection state"""
        selection_data = {
            'current_item': None,
            'selected_items': []
        }
        
        # Save current item
        current = self.currentItem()
        if current:
            item_data = current.data(0, Qt.UserRole)
            if item_data:
                selection_data['current_item'] = {
                    'type': item_data.get('type'),
                    'vmid': item_data.get('vmid'),
                    'group_name': item_data.get('group_name')
                }
        
        # Save selected items
        for item in self.selectedItems():
            item_data = item.data(0, Qt.UserRole)
            if item_data:
                selection_data['selected_items'].append({
                    'type': item_data.get('type'),
                    'vmid': item_data.get('vmid'),
                    'group_name': item_data.get('group_name')
                })
        
        return selection_data
    
    def _restore_selection_state(self, selection_data: Dict[str, Any]):
        """Restore selection state"""
        if not selection_data:
            return
        
        # Clear current selection
        self.clearSelection()
        self.setCurrentItem(None)
        
        # Find and restore selected items
        def find_item_by_data(target_data):
            """Find item by its data"""
            for i in range(self.topLevelItemCount()):
                group_item = self.topLevelItem(i)
                group_data = group_item.data(0, Qt.UserRole)
                
                # Check if this is the group we're looking for
                if (target_data.get('type') == 'group' and 
                    group_data and group_data.get('group_name') == target_data.get('group_name')):
                    return group_item
                
                # Check VMs in this group
                for j in range(group_item.childCount()):
                    vm_item = group_item.child(j)
                    vm_data = vm_item.data(0, Qt.UserRole)
                    if (vm_data and target_data.get('type') == 'vm' and
                        vm_data.get('vmid') == target_data.get('vmid')):
                        return vm_item
            return None
        
        # Restore selected items
        items_to_select = []
        for item_data in selection_data.get('selected_items', []):
            item = find_item_by_data(item_data)
            if item:
                items_to_select.append(item)
        
        # Apply selection
        for item in items_to_select:
            item.setSelected(True)
        
        # Restore current item
        current_data = selection_data.get('current_item')
        if current_data:
            current_item = find_item_by_data(current_data)
            if current_item:
                self.setCurrentItem(current_item)
    
    def dropEvent(self, event):
        """Handles the drop event for an item"""
        # Use the captured dragging item instead of currentItem()
        source_item = self.dragging_item
        
        if not source_item:
            # Fallback to currentItem() if dragging_item is None
            source_item = self.currentItem()
        
        if not source_item:
            self._end_drag_operation()
            return
        
        # Get source item data
        source_data = source_item.data(0, Qt.UserRole)
        if not source_data:
            self._end_drag_operation()
            return
        
        # Handle different types of drag operations
        if source_data.get('type') == 'vm':
            self._handle_vm_drop(event, source_item, source_data)
        elif source_data.get('type') == 'group':
            self._handle_group_drop(event, source_item, source_data)
        
        # Clean up drag operation
        self._end_drag_operation()
        
        event.accept()
    
    def _handle_vm_drop(self, event, source_item, source_data):
        """Handle dropping a VM item"""
        target_group_name = None
        
        # Try multiple methods to find target group
        target_item = self.itemAt(event.pos())
        
        # Method 1: Direct hit on an item
        if target_item:
            target_group_name = self._get_group_from_item(target_item)
        
        # Method 2: If no direct hit, search by coordinates  
        if not target_group_name:
            target_group_name = self._find_group_by_position(event.pos())
        
        # Method 3: Default to "Ungrouped" if nothing found
        if not target_group_name:
            target_group_name = "Não Agrupadas"
        
        # Move VM to target group
        vmid = source_data['vmid']
        group_name_for_manager = "" if target_group_name == "Não Agrupadas" else target_group_name
        
        self.group_manager.add_vm_to_group(vmid, group_name_for_manager)
        self.group_manager.save_groups()
        self.vm_action_performed.emit()
    
    def _get_group_from_item(self, item):
        """Get group name from a tree item (group or VM item)"""
        if not item:
            return None
        
        data = item.data(0, Qt.UserRole)
        if not data:
            return None
        
        if data.get('type') == 'group':
            return data['group_name']
        elif data.get('type') == 'vm':
            # If it's a VM, get the parent group
            parent = item.parent()
            if parent:
                parent_data = parent.data(0, Qt.UserRole)
                if parent_data and parent_data.get('type') == 'group':
                    return parent_data['group_name']
        
        return None
    
    def _find_group_by_position(self, pos):
        """Find group by scanning all top-level items for position match"""
        for i in range(self.topLevelItemCount()):
            group_item = self.topLevelItem(i)
            group_rect = self.visualItemRect(group_item)
            
            # Expand the hit area slightly for easier targeting
            expanded_rect = group_rect.adjusted(-5, -5, 5, 5)
            
            if expanded_rect.contains(pos):
                data = group_item.data(0, Qt.UserRole)
                if data and data.get('type') == 'group':
                    return data['group_name']
            
            # Also check child items (VMs) in this group
            for j in range(group_item.childCount()):
                child_item = group_item.child(j)
                child_rect = self.visualItemRect(child_item)
                if child_rect.contains(pos):
                    return data['group_name'] if data and data.get('type') == 'group' else None
        
        return None
    
    def _handle_group_drop(self, event, source_item, source_data):
        """Handle dropping a group item (reordering groups)"""
        target_item = self.itemAt(event.pos())
        
        if not target_item:
            return
        
        target_data = target_item.data(0, Qt.UserRole)
        if not target_data or target_data.get('type') != 'group':
            return
        
        source_group_name = source_data['group_name']
        target_group_name = target_data['group_name']
        
        if source_group_name == target_group_name:
            return
        
        # Reorder groups by updating their display order
        self._reorder_groups(source_group_name, target_group_name)
    
    def _reorder_groups(self, source_group: str, target_group: str):
        """Reorder groups by changing their position in the tree"""
        # Get current group order from the tree
        group_order = []
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            data = item.data(0, Qt.UserRole)
            if data and data.get('type') == 'group':
                group_order.append(data['group_name'])
        
        # Remove source group from its current position
        if source_group in group_order:
            group_order.remove(source_group)
        
        # Insert source group before target group
        target_index = group_order.index(target_group) if target_group in group_order else len(group_order)
        group_order.insert(target_index, source_group)
        
        # Save the new order to group manager
        self.group_manager.set_group_order(group_order)
        self.group_manager.save_groups()
        
        # Emit signal to update interface
        self.vm_action_performed.emit()
    
    def show_context_menu(self, position: QPoint):
        """Shows the context menu"""
        item = self.itemAt(position)
        menu = QMenu(self)
        
        if item:
            data = item.data(0, Qt.UserRole)
            
            if data and data.get('type') == 'group':
                # Menu for groups
                group_name = data['group_name']
                
                if group_name != "Não Agrupadas":
                    rename_action = QAction("Rename Group", self)
                    rename_action.triggered.connect(lambda: self.rename_group(group_name))
                    menu.addAction(rename_action)
                    
                    delete_action = QAction("Delete Group", self)
                    delete_action.triggered.connect(lambda: self.delete_group(group_name))
                    menu.addAction(delete_action)
                    
                    menu.addSeparator()
                
                expand_action = QAction("Expand All", self)
                expand_action.triggered.connect(self.expandAll)
                menu.addAction(expand_action)
                
                collapse_action = QAction("Collapse All", self)
                collapse_action.triggered.connect(self.collapseAll)
                menu.addAction(collapse_action)
                
            elif data and data.get('type') == 'vm':
                # Menu for VMs
                vmid = data['vmid']
                
                remove_action = QAction("Remove from Group", self)
                remove_action.triggered.connect(lambda: self.remove_vm_from_group(vmid))
                menu.addAction(remove_action)
        else:
            # Menu for empty area
            create_action = QAction("Create New Group", self)
            create_action.triggered.connect(self.create_new_group)
            menu.addAction(create_action)
        
        if not menu.isEmpty():
            menu.exec_(self.mapToGlobal(position))
    
    def create_new_group(self):
        """Creates a new group"""
        group_name, ok = QInputDialog.getText(
            self, "New Group", "Group name:"
        )
        
        if ok and group_name.strip():
            group_name = group_name.strip()
            
            # Check if group already exists
            if group_name in self.group_manager.get_all_group_names():
                QMessageBox.warning(self, "Error", f"Group '{group_name}' already exists!")
                return
            
            # Create empty group
            self.group_manager.groups[group_name] = []
            self.group_manager.save_groups()
            
            # Update interface
            self.vm_action_performed.emit()
    
    def rename_group(self, old_name: str):
        """Renames a group"""
        new_name, ok = QInputDialog.getText(
            self, "Rename Group", f"New name for '{old_name}':", text=old_name
        )
        
        if ok and new_name.strip() and new_name.strip() != old_name:
            new_name = new_name.strip()
            
            # Check if new name already exists
            if new_name in self.group_manager.get_all_group_names():
                QMessageBox.warning(self, "Error", f"Group '{new_name}' already exists!")
                return
            
            # Rename group
            if old_name in self.group_manager.groups:
                self.group_manager.groups[new_name] = self.group_manager.groups[old_name]
                del self.group_manager.groups[old_name]
                self.group_manager.save_groups()
                
                # Update interface
                self.vm_action_performed.emit()
    
    def delete_group(self, group_name: str):
        """Deletes a group"""
        reply = QMessageBox.question(
            self, "Delete Group", 
            f"Are you sure you want to delete group '{group_name}'?\n"
            "VMs will be moved to 'Ungrouped'.",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.group_manager.delete_group(group_name)
            self.vm_action_performed.emit()
    
    def remove_vm_from_group(self, vmid: int):
        """Removes a VM from its current group"""
        self.group_manager.add_vm_to_group(vmid, "")  # Move to ungrouped
        self.group_manager.save_groups()
        self.vm_action_performed.emit()

    def enterEvent(self, event):
        """Called when mouse enters the widget area"""
        self.mouse_over_widget = True
        self.hover_timer.stop()  # Cancel any pending hover timeout
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Called when mouse leaves the widget area"""
        # Start a short timer before allowing updates again
        # This prevents immediate updates if mouse briefly leaves
        self.hover_timer.start(100)  # 100ms delay
        super().leaveEvent(event)

    def _on_hover_timeout(self):
        """Called when hover timer expires - mouse has been away for a while"""
        self.mouse_over_widget = False
    
    def update_all_vm_buttons(self):
        """Atualiza os botões de todas as VMs para refletir status dos processos"""
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                vm_item = group_item.child(j)
                if hasattr(vm_item, 'vm_widget'):
                    vm_item.vm_widget.update_action_buttons()