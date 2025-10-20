# worker.py

from PyQt5.QtCore import QRunnable, pyqtSignal, QObject, QThreadPool, pyqtSlot
import traceback
import sys

# --- Classe para emitir sinais de volta para a Thread Principal ---
class WorkerSignals(QObject):
    """
    Define os sinais disponíveis do Worker para a Thread Principal.
    """
    finished = pyqtSignal()  # Sinaliza que o trabalho terminou
    error = pyqtSignal(tuple) # Envia exceção (type, value, traceback)
    result = pyqtSignal(object) # Envia o resultado da função

class ProgressiveWorkerSignals(QObject):
    """
    Sinais para Worker que atualiza progressivamente.
    """
    progress = pyqtSignal(object)  # Emite cada VM conforme fica pronta
    finished = pyqtSignal()  # Sinaliza que todas as VMs terminaram
    error = pyqtSignal(tuple)  # Envia exceção

# --- Classe Principal do Worker (QRunnable) ---
class Worker(QRunnable):
    """
    QRunnable para executar uma função em uma thread separada.
    """
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        
        # Armazena a função e argumentos/kwargs para execução
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        """ Executa o trabalho definido no QRunnable. """
        try:
            # Chama a função principal (ex: self.controller.update_dashboard)
            result = self.fn(*self.args, **self.kwargs)
        except:
            # Captura e envia o erro de volta para a Thread Principal
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            # Envia o resultado de volta para a Thread Principal
            self.signals.result.emit(result)  
        finally:
            # Sinaliza que o trabalho (thread) terminou
            self.signals.finished.emit()


class ProgressiveVMWorker(QRunnable):
    """
    Worker que carrega VMs progressivamente, emitindo cada uma conforme fica pronta.
    """
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.signals = ProgressiveWorkerSignals()
        self.setAutoDelete(True)
    
    @pyqtSlot()
    def run(self):
        """Carrega VMs e emite cada uma progressivamente"""
        try:
            # Busca lista básica de VMs
            vms_list = self.api_client.get_vms_list()
            
            if vms_list:
                for vm in vms_list:
                    vmid = vm.get('vmid')
                    vm_type = vm.get('type')
                    
                    if vmid is None or vm_type is None:
                        continue
                    
                    # Get detailed status
                    try:
                        detailed_status = self.api_client.get_vm_current_status(vmid, vm_type)
                        if detailed_status:
                            vm.update(detailed_status)
                    except:
                        pass
                    
                    # Get config
                    try:
                        vm_config = self.api_client.get_vm_config(vmid, vm_type)
                        if vm_config:
                            if 'ostype' in vm_config:
                                vm['ostype'] = vm_config['ostype']
                            if 'vga' in vm_config:
                                vm['vga'] = vm_config['vga']
                    except:
                        pass
                    
                    # Get IPs
                    if vm.get('status') == 'running':
                        try:
                            ip_addresses = self.api_client.get_vm_network_info(vmid, vm_type)
                            vm['ip_addresses'] = ip_addresses
                        except:
                            vm['ip_addresses'] = []
                    else:
                        vm['ip_addresses'] = []
                    
                    # EMITE A VM IMEDIATAMENTE
                    self.signals.progress.emit(vm)
            
        except Exception as e:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            self.signals.finished.emit()