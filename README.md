# AI Linux VM Terminal (MCP Server)

Servidor independente baseado no padrão **Model Context Protocol (MCP)** que capacita agentes de Inteligência Artificial (Google Antigravity, Claude Code, Cursor, Windsurf, ChatGPT, etc.) a controlar e operar com segurança uma Máquina Virtual Linux (Ubuntu/Debian) executada no VirtualBox via OpenSSH.

---

## 🌟 Principais Recursos

* **Compatibilidade Universal com LLMs**: Implementa o protocolo MCP JSON-RPC 2.0 padrão sobre `stdio`. Funciona com qualquer cliente ou agente compatível com MCP em qualquer máquina.
* **Sandbox Hermética e Segura**: Os comandos Linux solicitados pela IA rodam isolados dentro da VM, sem risco de corromper o sistema operacional hospedeiro (Windows/macOS/Linux).
* **Sessão de Terminal Persistente**: Preserva o diretório de trabalho atual (`cd`), variáveis de ambiente e estado do shell entre execuções sucessivas sem abrir novas conexões do zero.
* **Sem Caminhos ou Credenciais Hardcoded**: Detecção dinâmica do executável `VBoxManage` do VirtualBox e do cliente OpenSSH em qualquer sistema operacional. Parametrização via variáveis de ambiente.
* **Mecanismos de Proteção Ativa**: Validação de tamanho máximo do comando, timeout de execução, truncamento de saídas excessivas e garantia absoluta de que comandos Linux nunca sejam executados no shell do hospedeiro.

---

## 🛠 Ferramentas Disponíveis (MCP Tools)

| Ferramenta | Descrição | Parâmetros Principais |
|---|---|---|
| `vm_status` | Inspeciona o estado da VM no VirtualBox (`running`, `poweroff`), IP e disponibilidade da porta SSH. | `vm_name` (opcional) |
| `vm_start` | Inicia a VM em modo headless e aguarda ativamente a inicialização do serviço SSH. | `vm_name`, `wait_ssh`, `port` |
| `vm_terminal` | Executa comandos no Linux dentro da VM com sessão persistente (`cwd`, variáveis e código de saída). | `command`, `persistent`, `timeout`, `user`, `port` |

---

## 🚀 Instalação e Configuração

### 1. Pré-requisitos
* Python 3.10 ou superior
* Oracle VirtualBox instalado
* Cliente OpenSSH (nativo no Windows 10/11, Linux e macOS)
* Máquina virtual Linux (Ubuntu, Debian, etc.)

### 2. Configuração de Rede Recomendada (VirtualBox)
Para comunicação rápida e sem expor a VM à rede externa, use o **Redirecionamento de Portas (Port Forwarding)** no adaptador NAT:
* **Protocolo**: `TCP`
* **IP do Hospedeiro**: `127.0.0.1`
* **Porta do Hospedeiro**: `2222`
* **IP do Convidado**: *(deixar em branco)*
* **Porta do Convidado**: `22`

---

## ⚙️ Registro no seu Agente de IA

### Google Antigravity (`~/.gemini/config/mcp_config.json`):
```json
{
  "mcpServers": {
    "vm-terminal": {
      "command": "python",
      "args": ["<CAMINHO_DO_REPOSITORIO>/server.py"]
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "vm-terminal": {
      "command": "python",
      "args": ["<CAMINHO_DO_REPOSITORIO>/server.py"]
    }
  }
}
```

---

## 🔐 Variáveis de Ambiente Suportadas

Todas as configurações possuem padrões seguros e podem ser customizadas:

| Variável | Valor Padrão | Descrição |
|---|---|---|
| `VM_NAME` | `Ubuntu-Lab` | Nome da máquina virtual no VirtualBox |
| `VM_HOST` | `127.0.0.1` | Host/IP da VM |
| `VM_SSH_PORT` | `2222` | Porta SSH mapeada da VM |
| `VM_USER` | `ubuntu` | Usuário Linux para login SSH |
| `SSH_KEY_PATH` | *(automático: ~/.ssh/)* | Caminho customizado para a chave privada SSH |
| `CMD_TIMEOUT_SECONDS` | `60` | Tempo limite padrão por comando |
| `VM_BOOT_TIMEOUT_SECONDS` | `120` | Tempo máximo aguardando o boot e SSH da VM |

---

## 🧪 Testes Automatizados

Para validar o funcionamento em qualquer nova máquina:

```bash
python test_vm_tools.py
```
