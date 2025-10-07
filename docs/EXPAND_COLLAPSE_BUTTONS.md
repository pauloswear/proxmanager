# Botões de Expandir/Colapsar Grupos

## 🎯 Nova Funcionalidade Implementada

Adicionados botões **+** e **−** nos cabeçalhos dos grupos para controle intuitivo de expansão/colapso.

## 🔧 Componentes Implementados

### 1. **Botão de Expansão no GroupWidget**
```python
self.expand_btn = QPushButton()
self.expand_btn.setFixedSize(20, 20)
```

**Características:**
- ✅ **Tamanho**: 20x20 pixels (compacto)
- ✅ **Design**: Transparente com hover effect
- ✅ **Ícones**: "+" para expandir, "−" para colapsar
- ✅ **Posicionamento**: Lado esquerdo do cabeçalho do grupo

### 2. **Sinais de Comunicação**
```python
expand_clicked = pyqtSignal()   # Quando usuário clica para expandir
collapse_clicked = pyqtSignal() # Quando usuário clica para colapsar
```

### 3. **Estados Visuais do Botão**
| Estado | Ícone | Ação |
|--------|-------|------|
| Expandido | **−** | Clique colapsa o grupo |
| Colapsado | **+** | Clique expande o grupo |

## 🎨 Design e Estilo

### **Botão de Expansão:**
```css
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
```

### **Layout do Cabeçalho:**
```
[±] 📁 Nome do Grupo (X VMs)
```
- **[±]**: Botão expandir/colapsar
- **📁**: Ícone da pasta  
- **Nome (Count)**: Texto do grupo

## 🔄 Funcionalidades

### **1. Controle Manual:**
- ✅ Clique no botão **+** → Expande grupo
- ✅ Clique no botão **−** → Colapsa grupo
- ✅ Feedback visual imediato

### **2. Sincronização Automática:**
- ✅ Botão reflete estado atual (expandido/colapsado)
- ✅ Estado preservado durante refresh da interface
- ✅ Integração com sistema de salvamento de estado existente

### **3. Métodos de Controle:**
```python
# Programático (sem emitir sinais)
widget.set_expanded(True/False)

# Manual (emite sinais)  
widget.toggle_expansion()

# Estados
widget.is_expanded  # True/False
```

## 🚀 Integração com Sistema Existente

### **Preservação de Estado:**
- ✅ Estado de expansão salvo durante `_save_expansion_state()`
- ✅ Estado restaurado durante reconstrução da árvore
- ✅ Botões sincronizados automaticamente após restauração

### **Compatibilidade:**
- ✅ Funciona com drag & drop existente
- ✅ Compatible com scroll preservation
- ✅ Não interfere com timer de atualização

## 🎯 Experiência do Usuário

### **Antes:**
- Apenas clique duplo ou seta no item para expandir/colapsar
- Área de clique pouco intuitiva

### **Depois:**  
- ✅ **Botão visual claro** com + e − 
- ✅ **Área de clique definida** (20x20px)
- ✅ **Feedback hover** para melhor usabilidade
- ✅ **Controle preciso** e intuitivo

## 📊 Benefícios

### **Usabilidade:**
- 🎯 **Controle intuitivo** com ícones universais (+ / −)
- 👆 **Área de clique bem definida** e fácil de acertar
- ⚡ **Feedback visual** imediato no hover/press
- 🎨 **Design integrado** ao tema escuro

### **Funcionalidade:**
- 🔄 **Estado sincronizado** automaticamente
- 💾 **Persistência** durante refreshs  
- 🎛️ **Controle programático** disponível
- 🔗 **Integração perfeita** com sistema existente

## 🎉 Resultado Final

Agora cada grupo tem um botão claro e intuitivo para expandir/colapsar, tornando a navegação muito mais user-friendly. Os usuários podem facilmente organizar a visualização dos grupos sem precisar adivinhar onde clicar!

**Interface mais intuitiva + Controle preciso = Melhor experiência do usuário! 🚀**