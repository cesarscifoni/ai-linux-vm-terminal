"""
Suíte de testes automatizados para as ferramentas da VM Linux:
- vm_status
- vm_start
- vm_terminal (tratamento de erros, timeouts, limites de segurança e formato JSON)
"""

import unittest
import json
import os
import sys

# Insere a pasta do MCP no sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vm.vbox import list_vms, get_vm_state
from vm.handlers import tool_vm_status, tool_vm_start, tool_vm_terminal
from vm.ssh_client import check_ssh_port_open, execute_ssh_command
from vm.config import MAX_CMD_LENGTH


class TestVMMCPIntegration(unittest.TestCase):

    def test_list_vms_finds_virtualbox(self):
        """Verifica se a integração com o VirtualBox está respondendo sem erros."""
        vms = list_vms()
        self.assertIsInstance(vms, list)

    def test_vm_status_inexistent(self):
        """Valida comportamento e retorno ao consultar VM inexistente."""
        raw_res = tool_vm_status({"vm_name": "VM_QUE_NAO_EXISTE_TESTE"})
        data = json.loads(raw_res)
        self.assertFalse(data.get("exists"))
        self.assertEqual(data.get("state"), "not_found")
        self.assertIn("registered_vms", data)

    def test_vm_status_existing_or_fallback(self):
        """Valida retorno dinâmico de status sem depender de nomes locais específicos."""
        vms = list_vms()
        vm_name = vms[0]["name"] if vms else "Ubuntu-Lab"
        raw_res = tool_vm_status({"vm_name": vm_name})
        data = json.loads(raw_res)
        self.assertIn("state", data)
        self.assertIn("exists", data)

    def test_vm_start_inexistent(self):
        """Valida que vm_start rejeita VM inexistente com mensagem amigável."""
        raw_res = tool_vm_start({"vm_name": "VM_FANTASMA", "wait_ssh": False})
        data = json.loads(raw_res)
        self.assertFalse(data.get("success"))
        self.assertIn("não existe", data.get("error"))

    def test_vm_terminal_missing_command(self):
        """Valida que comando vazio retorna erro."""
        raw_res = tool_vm_terminal({})
        data = json.loads(raw_res)
        self.assertIn("error", data)

    def test_vm_terminal_security_max_command_length(self):
        """Valida que comandos excessivamente longos são rejeitados por segurança."""
        huge_cmd = "a" * (MAX_CMD_LENGTH + 50)
        raw_res = tool_vm_terminal({"command": huge_cmd})
        data = json.loads(raw_res)
        self.assertIn("Comando rejeitado", data.get("stderr"))
        self.assertEqual(data.get("exit_code"), -1)

    def test_vm_terminal_connection_refused_handling(self):
        """Valida que falha de rede/porta fechada não quebra o MCP e retorna JSON estruturado."""
        raw_res = tool_vm_terminal({
            "command": "uname -a",
            "host": "127.0.0.1",
            "port": 54321,  # Porta improvável de estar aberta
            "timeout": 3,
            "persistent": False
        })
        data = json.loads(raw_res)
        self.assertEqual(data.get("command"), "uname -a")
        self.assertNotEqual(data.get("exit_code"), 0)
        self.assertIsInstance(data.get("duration_ms"), int)


if __name__ == "__main__":
    unittest.main()
