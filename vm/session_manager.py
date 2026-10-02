"""
Sessão persistente do terminal Linux remoto via processo interativo SSH com pipes stdio.
Mantém diretório de trabalho, variáveis de ambiente e estado do shell entre chamadas.
"""

import subprocess
import threading
import time
import uuid
import re
import os
from typing import Dict, Any, Optional
from vm.config import (
    DEFAULT_VM_HOST,
    DEFAULT_VM_SSH_PORT,
    DEFAULT_VM_USER,
    DEFAULT_SSH_KEY_PATH,
    CMD_TIMEOUT_SECONDS,
    MAX_CMD_LENGTH,
    MAX_OUTPUT_LENGTH,
)
from vm.ssh_client import get_ssh_base_command


class PersistentSSHSession:
    """
    Mantém um processo SSH interativo (bash/sh) aberto com a VM.
    Executa comandos enviando-os pelo stdin e detecta o fim da execução
    através de um sentinela único com captura do exit code e pwd.
    """

    def __init__(
        self,
        vm_key: str,
        user: str = DEFAULT_VM_USER,
        host: str = DEFAULT_VM_HOST,
        port: int = DEFAULT_VM_SSH_PORT,
        key_path: str = DEFAULT_SSH_KEY_PATH,
    ):
        self.vm_key = vm_key
        self.user = user
        self.host = host
        self.port = port
        self.key_path = key_path
        self.process: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.current_cwd = "~"
        self._start_session()

    def _start_session(self):
        """Inicia o processo SSH remoto com um shell bash interativo limpo."""
        base_cmd = get_ssh_base_command(
            user=self.user,
            host=self.host,
            port=self.port,
            key_path=self.key_path,
        )
        # Força alocação de shell simples sem echo e sem prompt ruidoso
        # Executa bash em modo não-interativo com subshell para controle exato de I/O
        cmd = base_cmd + ["/bin/bash"]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Unifica stdout e stderr na sessão interativa
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,  # Line-buffered
            )
        except Exception as e:
            self.process = None
            raise RuntimeError(f"Falha ao iniciar processo SSH persistente: {str(e)}")

    def is_alive(self) -> bool:
        """Verifica se o processo SSH ainda está rodando."""
        return self.process is not None and self.process.poll() is None

    def close(self):
        """Encerra a sessão SSH."""
        if self.is_alive():
            try:
                self.process.stdin.write("exit\n")
                self.process.stdin.flush()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None

    def run_command(self, command: str, timeout: int = CMD_TIMEOUT_SECONDS) -> Dict[str, Any]:
        """
        Executa um comando na sessão aberta e aguarda o sentinela.
        """
        if len(command) > MAX_CMD_LENGTH:
            return {
                "command": command[:100] + "...",
                "stdout": "",
                "stderr": f"Comando rejeitado: tamanho de {len(command)} caracteres excede o limite máximo.",
                "exit_code": -1,
                "duration_ms": 0,
            }

        with self.lock:
            # Se a conexão caiu, tenta reconectar
            if not self.is_alive():
                try:
                    self._start_session()
                except Exception as e:
                    return {
                        "command": command,
                        "stdout": "",
                        "stderr": f"Erro de conexão com a VM: {str(e)}",
                        "exit_code": -1,
                        "duration_ms": 0,
                    }

            token = uuid.uuid4().hex[:12]
            start_marker = f"__AGY_START_{token}__"
            end_marker = f"__AGY_END_{token}__"

            # Script encapsulador para executar o comando e imprimir sentinelas
            # Formato do sentinela final: __AGY_END_token__:EXIT_CODE:CURRENT_DIR
            wrapper = (
                f"echo '{start_marker}'\n"
                f"{command}\n"
                f"__agy_ec=$?\n"
                f"echo '{end_marker}':$__agy_ec:\"$(pwd)\"\n"
            )

            start_time = time.time()
            try:
                self.process.stdin.write(wrapper)
                self.process.stdin.flush()
            except Exception as e:
                self.close()
                return {
                    "command": command,
                    "stdout": "",
                    "stderr": f"Falha ao enviar comando para sessão SSH: {str(e)}",
                    "exit_code": -1,
                    "duration_ms": int((time.time() - start_time) * 1000),
                }

            # Leitura do output até encontrar o marcador final
            output_lines = []
            capturing = False
            exit_code = 0
            new_cwd = self.current_cwd

            deadline = time.time() + timeout
            while time.time() < deadline:
                if not self.is_alive():
                    return {
                        "command": command,
                        "stdout": "\n".join(output_lines),
                        "stderr": "Conexão SSH com a VM foi encerrada inesperadamente.",
                        "exit_code": -1,
                        "duration_ms": int((time.time() - start_time) * 1000),
                    }

                line = self.process.stdout.readline()
                if not line:
                    time.sleep(0.05)
                    continue

                line_str = line.rstrip("\r\n")

                if start_marker in line_str:
                    capturing = True
                    continue

                if end_marker in line_str:
                    # Encontrou o final!
                    # Formato: __AGY_END_token__:0:/home/usuario
                    parts = line_str.split(f"{end_marker}:")
                    if len(parts) > 1:
                        meta = parts[1].split(":", 1)
                        if len(meta) >= 1:
                            try:
                                exit_code = int(meta[0])
                            except ValueError:
                                exit_code = 0
                        if len(meta) >= 2:
                            new_cwd = meta[1]
                    break

                if capturing:
                    output_lines.append(line_str)

            else:
                # Timeout estourado
                return {
                    "command": command,
                    "stdout": "\n".join(output_lines),
                    "stderr": f"Timeout de {timeout}s atingido aguardando resposta do comando.",
                    "exit_code": 124,
                    "duration_ms": int((time.time() - start_time) * 1000),
                }

            self.current_cwd = new_cwd
            raw_output = "\n".join(output_lines)
            if len(raw_output) > MAX_OUTPUT_LENGTH:
                raw_output = raw_output[:MAX_OUTPUT_LENGTH] + "\n\n[AVISO: Saída truncada pelo limite de segurança]"

            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "command": command,
                "stdout": raw_output,
                "stderr": "",
                "exit_code": exit_code,
                "cwd": self.current_cwd,
                "duration_ms": duration_ms,
            }


# Pool de sessões persistentes ativas { "user@host:port": PersistentSSHSession }
_SESSION_POOL: Dict[str, PersistentSSHSession] = {}


def get_persistent_session(
    user: str = DEFAULT_VM_USER,
    host: str = DEFAULT_VM_HOST,
    port: int = DEFAULT_VM_SSH_PORT,
    key_path: str = DEFAULT_SSH_KEY_PATH,
) -> PersistentSSHSession:
    """Obtém ou cria a sessão persistente para a VM alvo."""
    session_key = f"{user}@{host}:{port}"
    session = _SESSION_POOL.get(session_key)
    if session is None or not session.is_alive():
        session = PersistentSSHSession(
            vm_key=session_key,
            user=user,
            host=host,
            port=port,
            key_path=key_path,
        )
        _SESSION_POOL[session_key] = session
    return session
