"""
Wrapper seguro para controle do VirtualBox via VBoxManage.
"""

import os
import subprocess
import shutil
import re
from typing import Dict, Any, List, Optional
from vm.config import VBOXMANAGE_PATH


def get_vboxmanage_bin() -> str:
    """Localiza o binário do VBoxManage no sistema."""
    if os.path.exists(VBOXMANAGE_PATH):
        return VBOXMANAGE_PATH
    found = shutil.which("VBoxManage") or shutil.which("VBoxManage.exe")
    if found:
        return found
    raise FileNotFoundError(
        f"VBoxManage não encontrado em '{VBOXMANAGE_PATH}' nem no PATH do sistema."
    )


def run_vbox_command(args: List[str], timeout: int = 15) -> subprocess.CompletedProcess:
    """
    Executa um comando VBoxManage com segurança:
    - Passa argumentos como lista (sem shell=True) para evitar injeção de comandos.
    - Captura stdout e stderr com encoding UTF-8.
    """
    vbox_bin = get_vboxmanage_bin()
    cmd = [vbox_bin] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace"
    )


def list_vms() -> List[Dict[str, str]]:
    """Lista todas as VMs registradas no VirtualBox."""
    proc = run_vbox_command(["list", "vms"])
    if proc.returncode != 0:
        return []
    
    # Formato: "Ubuntu-Lab" {UUID}
    pattern = re.compile(r'"([^"]+)"\s+\{([^}]+)\}')
    vms = []
    for line in proc.stdout.splitlines():
        match = pattern.search(line)
        if match:
            vms.append({"name": match.group(1), "uuid": match.group(2)})
    return vms


def list_running_vms() -> List[Dict[str, str]]:
    """Lista as VMs que estão em execução no momento."""
    proc = run_vbox_command(["list", "runningvms"])
    if proc.returncode != 0:
        return []
    
    pattern = re.compile(r'"([^"]+)"\s+\{([^}]+)\}')
    vms = []
    for line in proc.stdout.splitlines():
        match = pattern.search(line)
        if match:
            vms.append({"name": match.group(1), "uuid": match.group(2)})
    return vms


def get_vm_state(vm_name: str) -> Dict[str, Any]:
    """
    Obtém informações e o estado detalhado da VM.
    Retorna estado ('running', 'poweroff', 'saved', 'not_found', etc.) e dados de rede.
    """
    try:
        proc = run_vbox_command(["showvminfo", vm_name, "--machinereadable"])
    except FileNotFoundError as e:
        return {"error": str(e), "state": "unknown"}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout ao consultar VBoxManage", "state": "unknown"}

    if proc.returncode != 0:
        return {
            "vm": vm_name,
            "exists": False,
            "state": "not_found",
            "message": f"VM '{vm_name}' não encontrada no VirtualBox."
        }

    info: Dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k.strip()] = v.strip().strip('"')

    vm_state = info.get("VMState", "unknown")
    
    # Tenta obter o IP pelo Guest Additions se estiver ligada
    guest_ip = None
    if vm_state == "running":
        try:
            prop_proc = run_vbox_command(["guestproperty", "get", vm_name, "/VirtualBox/GuestInfo/Net/0/V4/IP"])
            if prop_proc.returncode == 0 and "Value:" in prop_proc.stdout:
                guest_ip = prop_proc.stdout.split("Value:")[1].strip()
        except Exception:
            pass

    # Verifica regras de port forwarding (ex: SSH redirecionado)
    port_forwarding = []
    for k, v in info.items():
        if k.startswith("Forwarding("):
            port_forwarding.append(v)

    return {
        "vm": vm_name,
        "exists": True,
        "state": vm_state,
        "os": info.get("ostype", "unknown"),
        "guest_ip": guest_ip,
        "port_forwarding": port_forwarding
    }


def start_vm(vm_name: str, headless: bool = True) -> Dict[str, Any]:
    """Inicia a VM via VBoxManage em modo headless."""
    cmd = ["startvm", vm_name]
    if headless:
        cmd.extend(["--type", "headless"])
        
    proc = run_vbox_command(cmd, timeout=30)
    if proc.returncode == 0:
        return {"success": True, "message": f"VM '{vm_name}' iniciada com sucesso em modo {'headless' if headless else 'gui'}."}
    else:
        return {
            "success": False,
            "message": f"Falha ao iniciar VM '{vm_name}': {proc.stderr.strip() or proc.stdout.strip()}"
        }
