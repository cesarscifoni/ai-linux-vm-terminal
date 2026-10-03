"""
Utilitários de verificação e execução de comandos SSH na VM Linux.
"""

import socket
import subprocess
import time
import os
import shutil
from typing import Dict, Any, Tuple
from vm.config import (
    DEFAULT_VM_HOST,
    DEFAULT_VM_SSH_PORT,
    DEFAULT_VM_USER,
    DEFAULT_SSH_KEY_PATH,
    CMD_TIMEOUT_SECONDS,
    MAX_CMD_LENGTH,
    MAX_OUTPUT_LENGTH,
)


def check_ssh_port_open(host: str = DEFAULT_VM_HOST, port: int = DEFAULT_VM_SSH_PORT, timeout: float = 2.0) -> bool:
    """Verifica rapidamente se a porta SSH está respondendo a conexões TCP."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def wait_for_ssh(host: str, port: int, max_wait_seconds: int = 60, interval: float = 2.0) -> bool:
    """Aguarda até que a porta SSH esteja aberta e aceitando conexões."""
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        if check_ssh_port_open(host, port, timeout=1.5):
            return True
        time.sleep(interval)
    return False


def get_ssh_base_command(
    user: str = DEFAULT_VM_USER,
    host: str = DEFAULT_VM_HOST,
    port: int = DEFAULT_VM_SSH_PORT,
    key_path: str = DEFAULT_SSH_KEY_PATH,
) -> list:
    """
    Monta a linha base segura do cliente OpenSSH de forma agnóstica de sistema operacional.
    - Sem invocação de shell intermediário (evita injeção de comandos).
    - Opções para não travar com prompts de confirmação interativa.
    """
    # 1. Procura 'ssh' no PATH (Linux, macOS e Windows com OpenSSH no PATH)
    ssh_bin = shutil.which("ssh") or shutil.which("ssh.exe")

    # 2. Fallback padrão do OpenSSH nativo do Windows
    if not ssh_bin:
        win_ssh = r"C:\Windows\System32\OpenSSH\ssh.exe"
        if os.path.exists(win_ssh):
            ssh_bin = win_ssh
        else:
            ssh_bin = "ssh"

    cmd = [
        ssh_bin,
        "-p", str(port),
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
    ]

    if key_path and os.path.exists(key_path):
        cmd.extend(["-i", key_path])

    cmd.append(f"{user}@{host}")
    return cmd


def execute_ssh_command(
    remote_command: str,
    user: str = DEFAULT_VM_USER,
    host: str = DEFAULT_VM_HOST,
    port: int = DEFAULT_VM_SSH_PORT,
    key_path: str = DEFAULT_SSH_KEY_PATH,
    timeout: int = CMD_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Executa um comando remotamente na VM Linux via SSH.
    - Segurança: Não usa shell do Windows (subprocess.run com lista de args).
    - Limites de payload e output para segurança da IA e do sistema.
    - Captura stdout, stderr, exit code e tempo de execução em milissegundos.
    """
    if len(remote_command) > MAX_CMD_LENGTH:
        return {
            "command": remote_command[:100] + "...",
            "stdout": "",
            "stderr": f"Comando rejeitado: tamanho de {len(remote_command)} caracteres excede o limite máximo de {MAX_CMD_LENGTH}.",
            "exit_code": -1,
            "duration_ms": 0,
        }

    base_cmd = get_ssh_base_command(user=user, host=host, port=port, key_path=key_path)
    # Passa o comando a ser executado pelo shell remoto (bash/sh da VM)
    full_cmd = base_cmd + [remote_command]

    start_time = time.time()
    try:
        proc = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        duration_ms = int((time.time() - start_time) * 1000)

        stdout = proc.stdout
        stderr = proc.stderr

        # Truncamento de segurança para não explodir o contexto
        if len(stdout) > MAX_OUTPUT_LENGTH:
            stdout = stdout[:MAX_OUTPUT_LENGTH] + f"\n\n[AVISO: Saída truncada em {MAX_OUTPUT_LENGTH} caracteres pelo MCP]"
        if len(stderr) > MAX_OUTPUT_LENGTH:
            stderr = stderr[:MAX_OUTPUT_LENGTH] + f"\n\n[AVISO: Erro truncado em {MAX_OUTPUT_LENGTH} caracteres pelo MCP]"

        return {
            "command": remote_command,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
        }

    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "command": remote_command,
            "stdout": "",
            "stderr": f"Timeout: O comando excedeu o tempo limite de {timeout} segundos.",
            "exit_code": 124,
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "command": remote_command,
            "stdout": "",
            "stderr": f"Erro interno ao invocar SSH: {str(e)}",
            "exit_code": -1,
            "duration_ms": duration_ms,
        }
