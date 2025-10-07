# Sorting System - Groups and VMs

## 📊 Implemented Sorting Features

### 🗂️ **Group Sorting**
Groups are organized as follows:
1. **Custom groups** in alphabetical order (A-Z, case-insensitive)
2. **"Ungrouped"** always appears at the end of the list

```python
def _sort_groups(self, grouped_vms):
    # Separate "Ungrouped" from other groups
    # Sort other groups alphabetically
    # Put "Ungrouped" at the end
```

### 🖥️ **VM Sorting within Groups**
Within each group, VMs are sorted by:
1. **Status** (priority):
   - 🟢 **RUNNING** appear first
   - 🔴 **STOPPED/others** appear after
2. **Name** (alphabetical case-insensitive within each status)

```python
def _sort_vms_in_group(self, vms):
    # Priority: running = 0, others = 1
    # Then sort alphabetically by name
```

## 🎯 **Sorting Examples**

### **Groups:**
```
📁 Development (3 VMs)
📁 Production (5 VMs)  
📁 Testing (2 VMs)
📁 Ungrouped (4 VMs)  ← Always at the end
```

### **VMs within a group:**
```
📁 Production (5 VMs)
  ├── 🟢 api-server (running)      ← Running first
  ├── 🟢 database-prod (running)   ← Alphabetical within status
  ├── 🟢 web-frontend (running)    
  ├── 🔴 backup-server (stopped)   ← Stopped after
  └── 🔴 monitoring (stopped)      ← Alphabetical within status
```

## ⚙️ **Technical Implementation**

### **VM Sorting Key:**
```python
def sort_key(vm):
    status_priority = 0 if vm.status == 'running' else 1
    name = vm.name.lower()  # Case-insensitive
    return (status_priority, name)
```

### **Characteristics:**
- ✅ **Case-insensitive** - "Api" comes before "backend"
- ✅ **Priority status** - Running always at the top
- ✅ **Persistent** - Sorting maintained after drag & drop
- ✅ **Automatic** - Reorders with each update

## 🔄 **Behavior**

### **When Moving VMs:**
- Moved VM maintains sorted position in new group
- Does not break alphabetical/status sequence

### **When Creating Groups:**
- New groups inserted in correct alphabetical position
- "Ungrouped" always remains at the end

### **Real-time Updates:**
- VM status changes automatically reorder
- Name changes reorganize position

## 🎨 **Visual Benefits**

1. **📋 Clear Organization** - Easy VM location
2. **⚡ Visible Status** - Running VMs always at top
3. **🔤 Intuitive Alphabetical** - Expected natural order
4. **📌 Consistency** - Predictable behavior

The sorting makes the interface much more professional and easy to navigate!