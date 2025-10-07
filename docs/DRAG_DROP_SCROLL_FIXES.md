# Correções de Problemas no Sistema de Drag & Drop e Scroll

## Problemas Identificados e Soluções

### 1. Problema: Drag & Drop Degradado
**Descrição**: Após as melhorias anteriores, o drag & drop ficou pior e não conseguia soltar VMs dentro dos grupos.

**Causa Raiz**: 
- Detecção de drop muito restritiva no `dragMoveEvent()`
- Lógica de detecção de grupo alvo muito complexa e com falhas

**Soluções Implementadas**:

#### A. Simplificação do `dragMoveEvent()`
```python
def dragMoveEvent(self, event):
    """Handle drag move event - simplified to accept all valid drags"""
    if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
        event.accept()
    else:
        event.ignore()
```
- ✅ Removida lógica restritiva que estava bloqueando drops válidos
- ✅ Aceita todos os drags válidos para permitir melhor fluidez

#### B. Refatoração Completa do `_handle_vm_drop()`
```python
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
```

#### C. Novos Métodos Auxiliares
- **`_get_group_from_item()`**: Extrai nome do grupo de um item (grupo ou VM)
- **`_find_group_by_position()`**: Busca grupo por coordenadas com área expandida
- **Área de hit expandida**: `expanded_rect = group_rect.adjusted(-5, -5, 5, 5)`

### 2. Problema: Scroll Volta ao Topo no Refresh
**Descrição**: A cada atualização do QTimer (1 segundo), o scroll voltava para o topo da lista.

**Causa Raiz**: 
- Método `update_tree()` fazia `self.clear()` sem preservar posição do scroll
- Reconstrução completa da árvore resetava a posição

**Soluções Implementadas**:

#### A. Salvamento da Posição do Scroll
```python
def _save_scroll_position(self) -> dict:
    """Saves the current scroll position"""
    scrollbar = self.verticalScrollBar()
    return {
        'vertical_value': scrollbar.value(),
        'vertical_max': scrollbar.maximum()
    }
```

#### B. Restauração Inteligente da Posição
```python
def _restore_scroll_position(self, position_data: dict):
    """Restores the scroll position"""
    # Use QTimer to defer scroll restoration until after the UI has updated
    def restore_position():
        scrollbar = self.verticalScrollBar()
        if scrollbar.maximum() > 0:
            old_max = position_data.get('vertical_max', 0)
            old_value = position_data.get('vertical_value', 0)
            
            if old_max > 0:
                # Calculate percentage and apply to new maximum
                percentage = old_value / old_max
                new_value = int(percentage * scrollbar.maximum())
                scrollbar.setValue(new_value)
    
    QTimer.singleShot(10, restore_position)  # Small delay to ensure UI is ready
```

#### C. Integração no `update_tree()`
```python
def update_tree(self, vms_list: List[Dict[str, Any]]):
    # Save expansion state of groups and scroll position
    expanded_groups = self._save_expansion_state()
    scroll_position = self._save_scroll_position()
    
    # ... rebuild tree ...
    
    # Restore scroll position
    self._restore_scroll_position(scroll_position)
```

## Benefícios das Correções

### Drag & Drop Melhorado
- ✅ **Detecção Robusta**: Múltiplos métodos de detecção garantem sucesso
- ✅ **Área de Hit Expandida**: Mais fácil acertar o alvo durante drag
- ✅ **Fallback Inteligente**: Se não encontrar grupo específico, vai para "Não Agrupadas"
- ✅ **Código Limpo**: Lógica separada em métodos específicos para manutenibilidade

### Scroll Preservado
- ✅ **Posição Mantida**: Scroll não volta ao topo durante refresh automático
- ✅ **Cálculo Proporcional**: Se o conteúdo mudar de tamanho, mantém posição relativa
- ✅ **Timing Correto**: Usa `QTimer.singleShot()` para aguardar UI estar pronta
- ✅ **Experiência Fluida**: Usuário não perde contexto durante atualizações

### Robustez Geral
- ✅ **Tratamento de Erros**: Verifica se há conteúdo antes de restaurar scroll
- ✅ **Performance**: Operações otimizadas sem impacto na responsividade
- ✅ **Manutenibilidade**: Código organizado em métodos especializados

## Arquivos Modificados
- `interface/tree_widget.py`: 
  - Simplificado `dragMoveEvent()`
  - Refatorado `_handle_vm_drop()` 
  - Adicionados `_get_group_from_item()` e `_find_group_by_position()`
  - Implementado sistema de preservação de scroll
  - Melhorado `update_tree()` com salvamento/restauração de estado

## Resultado Final
O sistema agora oferece uma experiência muito mais fluida e confiável:
- **Drag & Drop**: Funciona consistentemente em qualquer área do grupo
- **Scroll**: Mantém posição durante atualizações automáticas  
- **Performance**: Não há lag ou comportamentos inesperados
- **UX**: Interface responsiva e previsível para o usuário