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