#!/usr/bin/env python3
"""
AI Linux VM Terminal - Standalone MCP Server
Protocolo padrão JSON-RPC 2.0 via stdio para qualquer agente/LLM.
"""

import sys
import json
import os

# Garante que stdin e stdout usem codificação UTF-8 explicitamente em qualquer SO
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SERVER_NAME = "ai-linux-vm-terminal"
SERVER_VERSION = "1.0.0"

from vm.handlers import tool_vm_status, tool_vm_start, tool_vm_terminal


# === Protocolo JSON-RPC ===

def send_response(response: dict):
    out = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(out + "\n")
    sys.stdout.flush()


def make_response(id, result):
    return {"jsonrpc": "2.0", "id": id, "result": result}


def make_error(id, code, message):
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


# === Definição dos Schemas das Tools ===

TOOLS = {
    "vm_status": {
        "description": "Verifica o estado da VM no VirtualBox (ex: running, poweroff), IP de rede e disponibilidade do SSH.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_name": {
                    "type": "string",
                    "description": "Nome da máquina virtual no VirtualBox (ex: 'Ubuntu-Lab', 'clienteIPS'). Se omitido, usa a padrão configurada."
                }
            }
        }
    },
    "vm_start": {
        "description": "Inicia uma máquina virtual no VirtualBox em modo headless e aguarda a inicialização do SSH.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm_name": {
                    "type": "string",
                    "description": "Nome da máquina virtual no VirtualBox (ex: 'Ubuntu-Lab', 'clienteIPS')."
                },
                "host": {
                    "type": "string",
                    "description": "Host/IP para validação do SSH (default: 127.0.0.1 ou configurado)."
                },
                "port": {
                    "type": "integer",
                    "description": "Porta SSH da VM (default: 2222 ou configurada)."
                },
                "wait_ssh": {
                    "type": "boolean",
                    "description": "Se true, aguarda até o SSH estar respondendo conexões antes de retornar (default: true)."
                }
            }
        }
    },
    "vm_terminal": {
        "description": "Executa um comando dentro da VM Linux via SSH com sessão persistente (preserva diretório cwd, variáveis de ambiente e estado).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Comando Linux a ser executado dentro da VM (ex: 'uname -a', 'ls -la', 'pwd', 'ps aux')."
                },
                "persistent": {
                    "type": "boolean",
                    "description": "Se true (padrão), executa em sessão persistente preservando contexto de diretório e variáveis."
                },
                "host": {
                    "type": "string",
                    "description": "Host/IP da VM (default: 127.0.0.1 ou configurado)."
                },
                "port": {
                    "type": "integer",
                    "description": "Porta SSH da VM (default: 2222 ou configurada)."
                },
                "user": {
                    "type": "string",
                    "description": "Usuário SSH (default: ubuntu ou configurado)."
                },
                "key_path": {
                    "type": "string",
                    "description": "Caminho da chave privada SSH (opcional se já configurada no ssh-agent ou ~/.ssh)."
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout do comando em segundos (default: 60)."
                }
            },
            "required": ["command"]
        }
    }
}

TOOL_HANDLERS = {
    "vm_status": tool_vm_status,
    "vm_start": tool_vm_start,
    "vm_terminal": tool_vm_terminal,
}


# === Handlers do protocolo MCP ===

def handle_initialize(id, params):
    return make_response(id, {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": False}
        },
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}
    })


def handle_tools_list(id, params):
    tools_list = []
    for name, tool in TOOLS.items():
        tools_list.append({
            "name": name,
            "description": tool["description"],
            "inputSchema": tool["inputSchema"]
        })
    return make_response(id, {"tools": tools_list})


def handle_tools_call(id, params):
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if tool_name not in TOOL_HANDLERS:
        return make_error(id, -32602, f"Tool not found: {tool_name}")

    try:
        result_text = TOOL_HANDLERS[tool_name](arguments)
        return make_response(id, {
            "content": [{"type": "text", "text": result_text}]
        })
    except Exception as e:
        return make_response(id, {
            "content": [{"type": "text", "text": f"Erro: {str(e)}"}],
            "isError": True
        })


HANDLERS = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
}

NOTIFICATIONS = {"notifications/initialized", "initialized"}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method", "")
        msg_id = msg.get("id")

        if method in NOTIFICATIONS or msg_id is None:
            continue

        handler = HANDLERS.get(method)
        if handler:
            response = handler(msg_id, msg.get("params", {}))
        else:
            response = make_error(msg_id, -32601, f"Method not found: {method}")

        send_response(response)


if __name__ == "__main__":
    main()
