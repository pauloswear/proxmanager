# Melhorias no Sistema de Drag & Drop

## Alterações Implementadas

### 1. Melhoria na Detecção de Drop para VMs
- **Problema**: Era necessário arrastar a VM um pouco para o lado para conseguir fazer o drop no grupo
- **Solução**: 
  - Adicionados métodos `dragEnterEvent()` e `dragMoveEvent()` para melhor detecção
  - Habilitado `setDropIndicatorShown(True)` para feedback visual
  - Melhorada a detecção de área de drop em `_handle_vm_drop()`
  - Agora é possível arrastar diretamente para cima sobre um grupo

### 2. Reordenação de Grupos
- **Nova Funcionalidade**: Agora é possível arrastar um grupo para reordená-lo
- **Implementação**:
  - Método `_handle_group_drop()` para processar drops de grupos
  - Método `_reorder_groups()` para reorganizar a ordem dos grupos
  - Sistema de persistência da ordem personalizada no `GroupManager`

### 3. Melhorias no GroupManager
- **Novos campos**:
  - `group_order`: Lista que mantém a ordem personalizada dos grupos
- **Novos métodos**:
  - `set_group_order(order)`: Define a ordem personalizada dos grupos
  - `get_group_order()`: Retorna a ordem atual dos grupos
- **Persistência**: A ordem personalizada é salva no arquivo JSON

### 4. Sistema de Ordenação Inteligente
- **Modificada função `_sort_groups()`**:
  - Prioriza ordem personalizada quando disponível
  - Mantém ordenação alfabética como fallback
  - Grupos "Não Agrupadas" sempre no final
  - Adiciona automaticamente novos grupos à ordem

## Como Funciona

### Arrastar VMs
1. **Detecção Melhorada**: O sistema agora detecta drops em qualquer parte do grupo (cabeçalho ou área de VMs)
2. **Feedback Visual**: Indicador de drop mostra onde a VM será solta
3. **Área Expandida**: Possível arrastar diretamente para cima sobre grupos

### Reordenar Grupos
1. **Arrastar Grupo**: Clique e arraste o cabeçalho de um grupo
2. **Drop em Outro Grupo**: Solte sobre o cabeçalho de outro grupo para reordenar
3. **Persistência**: A nova ordem é salva automaticamente
4. **Ordem Mantida**: A ordem personalizada é preservada entre reinicializações

## Arquivos Modificados
- `interface/tree_widget.py`: Melhorias no drag & drop e reordenação
- `interface/groups.py`: Sistema de ordem personalizada de grupos
- `resources/vm_groups.json`: Agora inclui campo `group_order`

## Benefícios
- ✅ Drop mais intuitivo e preciso para VMs
- ✅ Possibilidade de organizar grupos em ordem preferida
- ✅ Feedback visual melhorado durante operações de drag & drop
- ✅ Persistência da organização personalizada
- ✅ Experiência de usuário mais fluida e responsiva