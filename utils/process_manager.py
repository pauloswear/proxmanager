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
        """Registra um novo processo para uma VM"""
        self.processes[vmid] = ProcessInfo(pid=pid, protocol=protocol)
    
    def get_process(self, vmid: int) -> Optional[ProcessInfo]:
        """Obtém informações do processo de uma VM"""
        return self.processes.get(vmid)
    
    def has_active_process(self, vmid: int) -> bool:
        """Verifica se a VM tem um processo ativo"""
        if vmid not in self.processes:
            return False
        
        process_info = self.processes[vmid]
        return self.is_process_running(process_info.pid)
    
    def is_process_running(self, pid: int) -> bool:
        """Verifica se um processo ainda está rodando"""
        try:
            if self.is_windows:
                # No Windows, usa tasklist para verificar se o PID existe
                import subprocess
                result = subprocess.run(
                    ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                return str(pid) in result.stdout
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
        
        # Verifica se o processo ainda está rodando
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
                
                # Se a janela está minimizada, restaura
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                
                # Traz para frente
                win32gui.SetForegroundWindow(hwnd)
                
                # Atualiza o handle
                process_info.handle = hwnd
                return True
            
            return False
            
        except ImportError:
            # pywin32 não está instalado, tenta método alternativo
            return self._bring_to_front_windows_fallback(process_info)
        except Exception as e:
            print(f"Erro ao trazer janela para frente: {e}")
            return False
    
    def _bring_to_front_windows_fallback(self, process_info: ProcessInfo) -> bool:
        """Método alternativo sem pywin32 (menos confiável)"""
        try:
            import subprocess
            
            # Tenta usar PowerShell para trazer janela para frente
            ps_script = f"""
            $process = Get-Process -Id {process_info.pid} -ErrorAction SilentlyContinue
            if ($process) {{
                $process.MainWindowHandle | ForEach-Object {{
                    [void][System.Reflection.Assembly]::LoadWithPartialName("Microsoft.VisualBasic")
                    [Microsoft.VisualBasic.Interaction]::AppActivate($process.Id)
                }}
            }}
            """
            
            subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                timeout=2
            )
            return True
            
        except Exception:
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
