"""
Handlers das tools MCP para VirtualBox e terminal da VM.
"""

import json
from typing import Dict, Any
from vm.vbox import get_vm_state, start_vm, list_vms
from vm.ssh_client import check_ssh_port_open, wait_for_ssh, execute_ssh_command
from vm.config import (
    DEFAULT_VM_NAME,
    DEFAULT_VM_HOST,
    DEFAULT_VM_SSH_PORT,
    DEFAULT_VM_USER,
    DEFAULT_SSH_KEY_PATH,
    VM_BOOT_TIMEOUT_SECONDS,
    CMD_TIMEOUT_SECONDS,
)


def tool_vm_status(args: Dict[str, Any]) -> str:
    """Verifica o estado da VM configurada ou informada."""
    vm_name = args.get("vm_name") or DEFAULT_VM_NAME
    result = get_vm_state(vm_name)
    
    # Se a VM existe, também informa se o SSH responde na porta configurada
    if result.get("exists"):
        ssh_online = check_ssh_port_open(DEFAULT_VM_HOST, DEFAULT_VM_SSH_PORT, timeout=1.0)
        result["ssh_accessible"] = ssh_online
    else:
        # Lista as VMs existentes para ajudar o usuário se errou o nome
        available = list_vms()
        result["registered_vms"] = [v["name"] for v in available]

    return json.dumps(result, indent=2, ensure_ascii=False)


def tool_vm_start(args: Dict[str, Any]) -> str:
    """
    Inicia a VM se estiver desligada e aguarda até o SSH estar pronto.
    """
    vm_name = args.get("vm_name") or DEFAULT_VM_NAME
    host = args.get("host") or DEFAULT_VM_HOST
    port = int(args.get("port") or DEFAULT_VM_SSH_PORT)
    wait_ssh = args.get("wait_ssh", True)
    
    current_state = get_vm_state(vm_name)
    if not current_state.get("exists"):
        available = list_vms()
        return json.dumps({
            "success": False,
            "error": f"VM '{vm_name}' não existe no VirtualBox.",
            "registered_vms": [v["name"] for v in available]
        }, indent=2, ensure_ascii=False)

    state = current_state.get("state")
    if state == "running":
        ssh_ready = check_ssh_port_open(host, port)
        return json.dumps({
            "success": True,
            "message": f"VM '{vm_name}' já está em execução.",
            "state": "running",
            "ssh_ready": ssh_ready
        }, indent=2, ensure_ascii=False)

    # Inicia a VM
    start_res = start_vm(vm_name, headless=True)
    if not start_res.get("success"):
        return json.dumps(start_res, indent=2, ensure_ascii=False)

    if not wait_ssh:
        return json.dumps({
            "success": True,
            "message": f"VM '{vm_name}' foi disparada. Não aguardou SSH.",
            "state": "starting"
        }, indent=2, ensure_ascii=False)

    # Aguarda SSH ficar pronto
    ssh_ready = wait_for_ssh(host, port, max_wait_seconds=VM_BOOT_TIMEOUT_SECONDS)
    
    return json.dumps({
        "success": ssh_ready,
        "message": f"VM '{vm_name}' ligada e SSH pronto para conexões." if ssh_ready else f"VM ligada, mas o SSH na porta {port} não respondeu a tempo ({VM_BOOT_TIMEOUT_SECONDS}s).",
        "state": "running",
        "ssh_ready": ssh_ready
    }, indent=2, ensure_ascii=False)


from vm.session_manager import get_persistent_session


def tool_vm_terminal(args: Dict[str, Any]) -> str:
    """
    Executa um comando remotamente na VM Linux via SSH.
    Preserva contexto de diretório e variáveis em modo persistente.
    """
    command = args.get("command")
    if not command:
        return json.dumps({
            "error": "Parâmetro 'command' é obrigatório."
        }, indent=2, ensure_ascii=False)

    host = args.get("host") or DEFAULT_VM_HOST
    port = int(args.get("port") or DEFAULT_VM_SSH_PORT)
    user = args.get("user") or DEFAULT_VM_USER
    key_path = args.get("key_path") or DEFAULT_SSH_KEY_PATH
    timeout = int(args.get("timeout") or CMD_TIMEOUT_SECONDS)
    persistent = args.get("persistent", True)

    if persistent:
        try:
            session = get_persistent_session(
                user=user,
                host=host,
                port=port,
                key_path=key_path,
            )
            result = session.run_command(command, timeout=timeout)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except Exception as e:
            # Fallback transparente para o modo stateless se falhar a criação da sessão interativa
            pass

    # Modo stateless (execução direta isolada)
    result = execute_ssh_command(
        remote_command=command,
        user=user,
        host=host,
        port=port,
        key_path=key_path,
        timeout=timeout,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)
