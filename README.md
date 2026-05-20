# Echo Claude

[中文](#中文) | [English](#english)

---

## 中文

Echo Claude 是一个对中文友好的 AI 编程 Agent 命令行工具，支持连接国内外各大 AI 模型，集成了多模型切换、工具调用、会话管理等功能。

### 特性

- **全平台模型支持**: 支持 OpenAI、Claude、DeepSeek、文心一言、通义千问、智谱 GLM、Moonshot (Kimi)、Ollama 等国内外主流 AI 模型
- **工具调用能力**: 像 Claude Code 一样执行文件读写、Shell 命令、代码搜索等操作（严格安全沙箱）
- **双界面模式**:
  - 传统 CLI 模式（默认）- 简洁高效，适合日常使用
  - TUI 模式（可选）- 富文本显示，交互更友好
- **本地模型支持**: 可连接本地运行的模型（Ollama、LM Studio、LocalAI 等）
- **会话管理**: 对话历史持久化、会话导入导出、上下文保持
- **中文友好**: 界面、提示词、文档全部支持中文
- **插件系统**: 可扩展的插件架构，方便添加新功能

### 安装

```bash
# 使用 pip 安装
pip install echo-claude

# 或从源码安装
git clone https://github.com/echo-claude/echo-claude.git
cd echo-claude
pip install -e .
```

### 快速开始

1. **配置模型** (首次运行)

```bash
# 交互式配置
ec config init

# 或手动编辑配置文件
# ~/.echo-claude/config.yaml
```

2. **开始对话**

```bash
# CLI 模式
ec chat "帮我写一个快速排序算法"

# TUI 模式
ec tui
```

3. **使用工具**

```bash
# 读取文件
ec chat "读取 src/main.py 文件并分析"

# 执行命令（需在安全白名单内）
ec chat "列出当前目录的文件"
```

### 配置

配置文件位置：`~/.echo-claude/config.yaml`

```yaml
# 默认模型配置
default_provider: "openai"
default_model: "gpt-4"

# 模型提供者配置
providers:
  openai:
    api_key: "sk-..."
    base_url: "https://api.openai.com/v1"
    models: ["gpt-4", "gpt-3.5-turbo"]

  anthropic:
    api_key: "sk-ant-..."
    models: ["claude-3-opus", "claude-3-sonnet"]

  deepseek:
    api_key: "sk-..."
    base_url: "https://api.deepseek.com/v1"
    models: ["deepseek-chat", "deepseek-coder"]

  local:
    base_url: "http://localhost:11434"
    models: ["llama2", "codellama"]

# 工具配置
tools:
  enabled:
    - "file_read"
    - "file_write"
    - "shell"
  safe_dirs: ["./", "~/projects"]
  allowed_commands: ["ls", "grep", "cat", "python", "pytest"]

# 会话配置
session:
  auto_save: true
  history_limit: 1000
  save_path: "~/.echo-claude/sessions"
```

### 命令参考

| 命令 | 说明 |
|------|------|
| `ec chat <prompt>` | 单轮对话 |
| `ec tui` | 启动 TUI 界面 |
| `ec config init` | 初始化配置 |
| `ec config show` | 显示当前配置 |
| `ec session list` | 列出所有会话 |
| `ec session save <name>` | 保存当前会话 |
| `ec session load <name>` | 加载会话 |
| `ec tool list` | 列出可用工具 |
| `ec model list` | 列出所有配置的模型 |
| `ec model switch <name>` | 切换当前模型 |

### 安全警告

工具调用功能具有潜在风险：
- 文件操作会限制在配置的安全目录内
- Shell 命令会经过严格过滤（白名单机制）
- 建议在生产环境中禁用危险工具

详细安全说明请查看文档。

### 文档

- [快速入门](docs/guides/getting-started.md)
- [配置详解](docs/guides/configuration.md)
- [工具系统](docs/guides/tools.md)
- [模型集成](docs/guides/providers.md)
- [会话管理](docs/guides/sessions.md)

### 贡献

欢迎提交 Issue 和 Pull Request！

### 许可证

MIT License

---

## English

Echo Claude is a Chinese-friendly AI programming agent CLI tool that connects to major AI models worldwide, featuring multi-model switching, tool calling, session management, and more.

### Features

- **Full platform support**: OpenAI, Claude, DeepSeek, ERNIE Bot, Qwen, GLM, Moonshot, Ollama, and more
- **Tool calling**: File read/write, shell commands, code search (with strict sandbox)
- **Dual interface**:
  - CLI mode (default) - simple and efficient
  - TUI mode (optional) - rich text display, friendly interaction
- **Local model support**: Connect to locally running models (Ollama, LM Studio, LocalAI)
- **Session management**: Persistent conversation history, import/export, context keeping
- **Chinese friendly**: Full Chinese support for UI, prompts, and documentation
- **Plugin system**: Extensible architecture for custom functionality

### Installation

```bash
# Install with pip
pip install echo-claude

# Or install from source
git clone https://github.com/echo-claude/echo-claude.git
cd echo-claude
pip install -e .
```

### Quick Start

1. **Configure models** (first run)

```bash
# Interactive configuration
ec config init

# Or edit config manually
# ~/.echo-claude/config.yaml
```

2. **Start chatting**

```bash
# CLI mode
ec chat "help me write a quick sort algorithm"

# TUI mode
ec tui
```

3. **Use tools**

```bash
# Read file
ec chat "read and analyze src/main.py"

# Execute commands (must be in whitelist)
ec chat "list files in current directory"
```

### Commands

| Command | Description |
|---------|-------------|
| `ec chat <prompt>` | Single turn chat |
| `ec tui` | Launch TUI interface |
| `ec config init` | Initialize configuration |
| `ec config show` | Show current configuration |
| `ec session list` | List all sessions |
| `ec session save <name>` | Save current session |
| `ec session load <name>` | Load session |
| `ec tool list` | List available tools |
| `ec model list` | List all configured models |
| `ec model switch <name>` | Switch current model |

### Security

Tool calling has potential risks:
- File operations are restricted to configured safe directories
- Shell commands are filtered (whitelist mechanism)
- Danger tools should be disabled in production

See documentation for detailed security information.

### Documentation

- [Getting Started](docs/guides/getting-started.md)
- [Configuration](docs/guides/configuration.md)
- [Tools](docs/guides/tools.md)
- [Providers](docs/guides/providers.md)
- [Sessions](docs/guides/sessions.md)

### License

MIT