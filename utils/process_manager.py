# process_manager.py - Gerencia processos abertos de VMs

import os
import platform
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ProcessInfo:
    """Informações sobre um processo aberto"""
    pid: int
    protocol: str  # 'spice', 'novnc', 'rdp', 'ssh'
    handle: Optional[int] = None  # Handle da janela no Windows


class ProcessManager:
    """
    Gerencia processos abertos para cada VM.
    Rastreia PIDs e permite trazer janelas para frente.
    """
    
    def __init__(self):
        # Dicionário: {vmid: ProcessInfo}
        self.processes: Dict[int, ProcessInfo] = {}
        self.is_windows = platform.system() == 'Windows'
    
    def register_process(self, vmid: int, pid: int, protocol: str) -> None:
        """Registra um novo processo para uma VM e tenta cachear handle da janela"""
        self.processes[vmid] = ProcessInfo(pid=pid, protocol=protocol)
        
        # Se for Windows, tenta cachear o handle imediatamente (em background)
        if self.is_windows:
            # Aguarda um pouco para a janela ser criada
            import threading
            import time
            
            def cache_handle():
                # Tenta múltiplas vezes com intervalos curtos
                for attempt in range(5):  # 5 tentativas
                    time.sleep(0.1 * (attempt + 1))  # 100ms, 200ms, 300ms, 400ms, 500ms
                    try:
                        import win32gui
                        import win32process
                        
                        def callback(hwnd, windows):
                            if win32gui.IsWindowVisible(hwnd):
                                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                                if found_pid == pid:
                                    windows.append(hwnd)
                            return True
                        
                        windows = []
                        win32gui.EnumWindows(callback, windows)
                        
                        if windows and vmid in self.processes:
                            self.processes[vmid].handle = windows[0]
                            break  # Sucesso! Para de tentar
                    except:
                        pass
            
            # Executa em thread separada para não bloquear
            thread = threading.Thread(target=cache_handle, daemon=True)
            thread.start()
    
    def get_process(self, vmid: int) -> Optional[ProcessInfo]:
        """Obtém informações do processo de uma VM"""
        return self.processes.get(vmid)
    
    def has_active_process(self, vmid: int) -> bool:
        """Verifica se a VM tem um processo ativo (verificação rápida)"""
        # Apenas verifica se está no dicionário
        # A verificação de se está rodando é feita no bring_to_front
        return vmid in self.processes
    
    def is_process_running(self, pid: int) -> bool:
        """Verifica se um processo ainda está rodando"""
        try:
            if self.is_windows:
                # No Windows, usa método mais rápido com ctypes
                import ctypes
                import ctypes.wintypes
                
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                kernel32 = ctypes.windll.kernel32
                
                # Tenta abrir handle do processo
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if handle:
                    # Verifica código de saída
                    exit_code = ctypes.wintypes.DWORD()
                    if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                        kernel32.CloseHandle(handle)
                        # 259 (STILL_ACTIVE) significa que ainda está rodando
                        return exit_code.value == 259
                    kernel32.CloseHandle(handle)
                return False
            else:
                # No Linux/Unix, envia sinal 0 para testar se o processo existe
                os.kill(pid, 0)
                return True
        except (ProcessLookupError, PermissionError, Exception):
            return False
    
    def bring_to_front(self, vmid: int) -> bool:
        """
        Tenta trazer a janela do processo para frente.
        Retorna True se conseguiu, False caso contrário.
        """
        if vmid not in self.processes:
            return False
        
        process_info = self.processes[vmid]
        
        # Se já temos um handle válido (Windows), usa diretamente
        if self.is_windows and process_info.handle:
            try:
                import win32gui
                import win32con
                
                # Verifica se o handle ainda é válido
                if win32gui.IsWindow(process_info.handle):
                    # Se está minimizado, restaura
                    if win32gui.IsIconic(process_info.handle):
                        win32gui.ShowWindow(process_info.handle, win32con.SW_RESTORE)
                    
                    # Traz para frente
                    win32gui.SetForegroundWindow(process_info.handle)
                    return True
                else:
                    # Handle inválido, limpa
                    process_info.handle = None
            except:
                pass
        
        # Se não tem handle ou falhou, faz busca completa
        # Mas primeiro verifica se o processo ainda está rodando
        if not self.is_process_running(process_info.pid):
            # Remove processo morto
            del self.processes[vmid]
            return False
        
        if self.is_windows:
            return self._bring_to_front_windows(process_info)
        else:
            return self._bring_to_front_linux(process_info)
    
    def _bring_to_front_windows(self, process_info: ProcessInfo) -> bool:
        """Traz janela para frente no Windows usando pywin32"""
        try:
            import win32gui
            import win32con
            import win32process
            
            # Se já temos handle, tenta usar diretamente
            if process_info.handle and win32gui.IsWindow(process_info.handle):
                try:
                    if win32gui.IsIconic(process_info.handle):
                        win32gui.ShowWindow(process_info.handle, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(process_info.handle)
                    return True
                except:
                    process_info.handle = None
            
            # Busca janela por PID
            def callback(hwnd, windows):
                """Callback para enumerar janelas"""
                if win32gui.IsWindowVisible(hwnd):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid == process_info.pid:
                        windows.append(hwnd)
                return True
            
            windows = []
            win32gui.EnumWindows(callback, windows)
            
            if windows:
                # Pega a primeira janela encontrada para esse PID
                hwnd = windows[0]
                
                # Cache o handle para próximas vezes
                process_info.handle = hwnd
                
                # Se a janela está minimizada, restaura
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                
                # Traz para frente - usa método mais agressivo
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
                
                # Força o foco
                try:
                    win32gui.SetActiveWindow(hwnd)
                except:
                    pass
                
                return True
            
            return False
            
        except ImportError:
            # pywin32 não está instalado, tenta método alternativo
            return self._bring_to_front_windows_fallback(process_info)
        except Exception as e:
            print(f"Erro ao trazer janela para frente: {e}")
            return False
    
    def _bring_to_front_windows_fallback(self, process_info: ProcessInfo) -> bool:
        """Método alternativo usando ctypes (mais rápido, sem pywin32)"""
        try:
            import ctypes
            from ctypes import wintypes
            
            # Define constantes
            SW_RESTORE = 9
            SW_SHOW = 5
            HWND_TOP = 0
            SWP_SHOWWINDOW = 0x0040
            
            # Define funções da API do Windows
            user32 = ctypes.windll.user32
            
            # Callback para EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            
            found_windows = []
            
            def enum_callback(hwnd, lparam):
                # Verifica se janela é visível
                if user32.IsWindowVisible(hwnd):
                    # Get PID da janela
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    
                    if pid.value == process_info.pid:
                        found_windows.append(hwnd)
                return True
            
            # Enumera todas as janelas
            callback = EnumWindowsProc(enum_callback)
            user32.EnumWindows(callback, 0)
            
            if found_windows:
                hwnd = found_windows[0]
                
                # Cache handle
                process_info.handle = hwnd
                
                # Verifica se está minimizado
                if user32.IsIconic(hwnd):
                    user32.ShowWindow(hwnd, SW_RESTORE)
                else:
                    user32.ShowWindow(hwnd, SW_SHOW)
                
                # Traz para topo
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                
                # Método adicional: SetWindowPos para garantir
                user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_SHOWWINDOW | 0x0002 | 0x0001)
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Erro no fallback: {e}")
            return False
    
    def _bring_to_front_linux(self, process_info: ProcessInfo) -> bool:
        """Traz janela para frente no Linux usando wmctrl ou xdotool"""
        try:
            import subprocess
            
            # Tenta usar wmctrl primeiro
            try:
                # Lista janelas e encontra pela PID
                result = subprocess.run(
                    ['wmctrl', '-lp'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                
                for line in result.stdout.split('\n'):
                    if str(process_info.pid) in line:
                        # Extrai o ID da janela (primeira coluna)
                        window_id = line.split()[0]
                        # Ativa a janela
                        subprocess.run(['wmctrl', '-ia', window_id], timeout=2)
                        return True
                        
            except FileNotFoundError:
                # wmctrl não disponível, tenta xdotool
                try:
                    # Busca janelas do processo
                    result = subprocess.run(
                        ['xdotool', 'search', '--pid', str(process_info.pid)],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    
                    if result.stdout.strip():
                        window_id = result.stdout.strip().split('\n')[0]
                        # Ativa a janela
                        subprocess.run(['xdotool', 'windowactivate', window_id], timeout=2)
                        return True
                        
                except FileNotFoundError:
                    pass
            
            return False
            
        except Exception as e:
            print(f"Erro ao trazer janela para frente no Linux: {e}")
            return False
    
    def remove_process(self, vmid: int) -> None:
        """Remove um processo do rastreamento"""
        if vmid in self.processes:
            del self.processes[vmid]
    
    def cleanup_dead_processes(self) -> None:
        """Remove processos que não estão mais rodando"""
        dead_vmids = []
        
        for vmid, process_info in self.processes.items():
            if not self.is_process_running(process_info.pid):
                dead_vmids.append(vmid)
        
        for vmid in dead_vmids:
            del self.processes[vmid]
