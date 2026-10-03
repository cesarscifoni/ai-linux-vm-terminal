"""
Configurações da VM Linux e do VirtualBox.
Valores carregados de variáveis de ambiente com defaults seguros para laboratório.
"""

import os

# Caminho para VBoxManage
VBOXMANAGE_PATH = os.environ.get(
    "VBOXMANAGE_PATH",
    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
)

# Configurações padrão de conexão da VM
DEFAULT_VM_NAME = os.environ.get("VM_NAME", "Ubuntu-Lab")
DEFAULT_VM_HOST = os.environ.get("VM_HOST", "127.0.0.1")
DEFAULT_VM_SSH_PORT = int(os.environ.get("VM_SSH_PORT", "2222"))
DEFAULT_VM_USER = os.environ.get("VM_USER", "ubuntu")

# Caminho para chave SSH (padrão ~/.ssh/id_rsa ou id_ed25519 se existir)
DEFAULT_SSH_KEY_PATH = os.environ.get("SSH_KEY_PATH", "")

# Timeouts
SSH_CONNECT_TIMEOUT = int(os.environ.get("SSH_CONNECT_TIMEOUT", "10"))
CMD_TIMEOUT_SECONDS = int(os.environ.get("CMD_TIMEOUT_SECONDS", "60"))
VM_BOOT_TIMEOUT_SECONDS = int(os.environ.get("VM_BOOT_TIMEOUT_SECONDS", "120"))

# Limites de segurança
MAX_CMD_LENGTH = 10000
MAX_OUTPUT_LENGTH = 50000
