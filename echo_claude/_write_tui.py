# Write tui_ui.py with new content
content = r'''"""
Echo Claude TUI ── 水仙主题界面
字体：浅绿 / 米黄    边框：翠绿 / 橙色    图标：水仙花 🌼
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, Footer, Input, RichLog, Static,
    Button, Select, Label, Markdown,
)
from textual.markup import escape

from ..core.agent import Agent
from ..config.settings import get_config
from ..providers import get_provider_class
from ..core.session import SessionManager
from ..utils.prompts import get_system_prompt

DAFFODIL_TITLE = r"""
╭─────────────────────────────────────────╮
│  🌼  Echo Claude  ·  水仙花助手  🌼     │
╰─────────────────────────────────────────╯
"""


class ModelSelector(Static):
    """模型选择器"""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label("🌼 模型:", classes="label")
            yield Select(
                [("加载中...", "loading")],
                value="loading",
                classes="provider-select",
            )
            yield Select(
                [("自动", "auto")],
                value="auto",
                classes="model-select",
            )

    def set_providers(self, providers: list, default_provider: str):
        options = [(p, p) for p in providers]
        provider_select = self.query_one(".provider-select", Select)
        provider_select.set_options(options)
        if default_provider in providers:
            provider_select.value = default_provider

    def set_models(self, models: list, default_model: str = None):
        options = [("自动", "auto")] + [(m, m) for m in models]
        model_select = self.query_one(".model-select", Select)
        model_select.set_options(options)
        if default_model and default_model in models:
            model_select.value = default_model


class EchoClaudeTUI(App):
    """Echo Claude ── 水仙主题 TUI"""

    CSS = """
    Screen {
        background: #0d1f0d;
        color: #98FB98;
        layout: vertical;
    }

    Header {
        background: #0a1a0a;
        color: #FFFDD0;
        text-style: bold;
    }

    Footer {
        background: #0a1a0a;
        color: #50C878;
    }

    #chat-container {
        height: 1fr;
        padding: 1 2;
        background: #0d1f0d;
        border: solid #50C878;
    }

    #input-container {
        height: auto;
        padding: 1 2;
        background: #0a1a0a;
        border: solid #50C878;
    }

    #message-input {
        width: 1fr;
        background: #152515;
        color: #98FB98;
        border: solid #FF8C00;
    }

    #message-input:focus {
        border: solid #50C878;
    }

    #send-btn {
        background: #50C878;
        color: #0d1f0d;
        min-width: 8;
    }

    #send-btn:hover {
        background: #FF8C00;
    }

    #status-bar {
        height: 1;
        padding: 0 2;
        background: #0a1a0a;
        color: #FFFDD0;
    }

    #model-selector {
        height: auto;
        padding: 0 2;
        background: #0a1a0a;
        border-bottom: solid #50C878;
    }

    .label {
        content-align: right middle;
        width: 10;
        color: #FFFDD0;
    }

    Select {
        width: 22;
        background: #152515;
        color: #98FB98;
        border: solid #50C878;
    }

    Select:focus {
        border: solid #FF8C00;
    }

    RichLog {
        background: #0d1f0d;
        color: #98FB98;
        scrollbar-color: #50C878;
        scrollbar-background: #0a1a0a;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "退出"),
        ("ctrl+enter", "send", "发送"),
        ("ctrl+l", "clear", "清空"),
        ("tab", "focus_next", "切换焦点"),
        ("f1", "help", "帮助"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = get_config()
        self.agent: Optional[Agent] = None
        self.session_manager: Optional[SessionManager] = None
        self._current_provider = self.config.default_provider
        self._current_model = self.config.default_model
        self._is_responding = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ModelSelector(id="model-selector")
        yield RichLog(id="chat-container", wrap=True, markup=True, highlight=True)
        with Horizontal(id="input-container"):
            yield Input(
                placeholder="输入消息，Ctrl+Enter 发送... 🌼",
                id="message-input",
            )
            yield Button("🌼 发送", variant="primary", id="send-btn")
        yield Static("🌼 就绪", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._initialize_agent()
        self._setup_model_selector()
        self._show_welcome()

    def _initialize_agent(self):
        try:
            provider_name = self.config.default_provider
            provider_config = self.config.get_provider(provider_name)

            if not provider_config:
                self._show_error(f"Provider '{provider_name}' 未配置")
                return

            ProviderClass = get_provider_class(provider_name)
            if not ProviderClass:
                self._show_error(f"不支持的提供者: {provider_name}")
                return

            provider = ProviderClass(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                models=provider_config.models,
            )

            self.session_manager = SessionManager(
                save_path=Path(self.config.session.save_path).expanduser()
            )

            self.agent = Agent(
                provider=provider,
                model=self.config.default_model
                or (provider_config.models[0] if provider_config.models else None),
                session=self.session_manager.get_or_create(),
                config=self.config,
                system_prompt=get_system_prompt(self.config.language),
            )

        except Exception as e:
            self._show_error(f"初始化失败: {e}")

    def _setup_model_selector(self):
        from ..config.providers import list_available_providers

        providers_data = list_available_providers()
        provider_names = [
            p["name"] for p in providers_data if p["name"] in self.config.providers
        ]
        selector = self.query_one("#model-selector", ModelSelector)
        selector.set_providers(provider_names, self.config.default_provider)

        def on_provider_changed(event: Select.Changed):
            if event.value != "loading":
                self._current_provider = event.value
                self._update_agent_provider(event.value)

        def on_model_changed(event: Select.Changed):
            if event.value != "auto":
                self._current_model = event.value
                self._update_agent_model(event.value)

        selector.query_one(".provider-select", Select).changed = on_provider_changed
        selector.query_one(".model-select", Select).changed = on_model_changed

    def _update_agent_provider(self, provider_name: str):
        try:
            provider_config = self.config.get_provider(provider_name)
            ProviderClass = get_provider_class(provider_name)
            provider = ProviderClass(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                models=provider_config.models,
            )
            self.agent.provider = provider
            self.agent.model = (
                provider_config.models[0] if provider_config.models else None
            )

            selector = self.query_one("#model-selector", ModelSelector)
            selector.set_models(provider_config.models, self.agent.model)
            self._update_status(f"已切换: {provider_name}")
        except Exception as e:
            self._show_error(f"切换提供者失败: {e}")

    def _update_agent_model(self, model_name: str):
        if self.agent:
            self.agent.model = model_name
            self._update_status(f"模型: {model_name}")

    def _show_welcome(self):
        version = __import__("echo_claude").__version__
        welcome = (
            f"[bold #50C878]{DAFFODIL_TITLE}[/bold #50C878]\n"
            f"\n"
            f"[#FFFDD0]版本:[/#FFFDD0] {version}  │  "
            f"[#FFFDD0]模型:[/#FFFDD0] {self._current_provider}/{self._current_model or '自动'}\n"
            f"\n"
            f"[#98FB98]快捷键:[/#98FB98]\n"
            f"  [bold #FF8C00]Ctrl+Enter[/bold #FF8C00] [#FFFDD0]发送消息[/#FFFDD0]    "
            f"[bold #FF8C00]Ctrl+Q[/bold #FF8C00] [#FFFDD0]退出[/#FFFDD0]\n"
            f"  [bold #FF8C00]Ctrl+L[/bold #FF8C00]     [#FFFDD0]清空对话[/#FFFDD0]    "
            f"[bold #FF8C00]F1[/bold #FF8C00]     [#FFFDD0]帮助[/#FFFDD0]\n"
            f"\n"
            f"[#50C878]输入 /help 查看更多命令[/#50C878]\n"
            f"🌿  🌱  🌿  🌱  🌿  🌱  🌿  🌱  🌿"
        )
        self._add_message("system", welcome.strip())

    def _update_status(self, text: str):
        status = self.query_one("#status-bar", Static)
        status.update(f"[#50C878]🌼[/#50C878] {text}")

    def _show_error(self, error: str):
        self._add_message("system", f"[bold #FF8C00]⚠ 错误: {error}[/bold #FF8C00]")

    def _add_message(self, role: str, content: str):
        chat_log = self.query_one("#chat-container", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if role == "user":
            prefix = "[bold #FF8C00]✦ 你[/bold #FF8C00]"
        elif role == "assistant":
            prefix = "[bold #50C878]🌼 Echo[/bold #50C878]"
        elif role == "system":
            prefix = "[#FFFDD0]⚙ 系统[/#FFFDD0]"
        else:
            prefix = f"[dim]{role}[/dim]"

        if role == "user":
            color = "#FF8C00"
        elif role == "assistant":
            color = "#98FB98"
        else:
            color = "#FFFDD0"

        chat_log.write(
            f"\n[dim #50C878]{timestamp}[/dim #50C878]  "
            f"{prefix}  "
            f"[{color}]{escape(content)}[/{color}]\n"
        )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "message-input":
            await self._handle_send()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            await self._handle_send()

    async def _handle_send(self):
        if self._is_responding:
            return

        input_widget = self.query_one("#message-input", Input)
        prompt = input_widget.value.strip()
        if not prompt:
            return

        input_widget.value = ""
        self._is_responding = True

        try:
            self._add_message("user", prompt)

            if prompt.startswith("/"):
                await self._handle_command(prompt)
            else:
                await self._send_to_agent(prompt)

        finally:
            self._is_responding = False

    async def _handle_command(self, command: str):
        parts = command.split(maxsplit=1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            from ..utils.prompts import command_help

            self._add_message("system", command_help(self.config.language))
        elif cmd == "/clear":
            if self.session_manager and self.session_manager.current_session:
                self.session_manager.current_session.clear()
            self.query_one("#chat-container", RichLog).clear()
            self._add_message("system", "[#50C878]会话已清空 ✿[/#50C878]")
        elif cmd == "/quit":
            self.exit()
        elif cmd == "/save":
            name = args or datetime.now().strftime("session_%Y%m%d_%H%M%S")
            if self.session_manager:
                self.session_manager.save_current_session(name)
                self._add_message("system", f"[#50C878]🌼 会话已保存: {name}[/#50C878]")
        elif cmd == "/model":
            self._add_message(
                "system",
                f"[#FFFDD0]当前模型: {self._current_provider}/{self._current_model or '自动'}[/#FFFDD0]",
            )
        else:
            self._add_message("system", f"[#FF8C00]未知命令: {cmd}。输入 /help 查看帮助。[/#FF8C00]")

    async def _send_to_agent(self, prompt: str):
        if not self.agent:
            self._show_error("Agent未初始化")
            return

        try:
            self._update_status("[#FF8C00]🌼 思考中...[/#FF8C00]")

            response = self.agent.chat(prompt, stream=False)
            self._add_message("assistant", str(response))

            self._update_status("就绪")
        except Exception as e:
            self._show_error(f"Agent错误: {e}")
            self._update_status("错误")

    def action_send(self):
        asyncio.create_task(self._handle_send())

    def action_clear(self):
        if self.session_manager and self.session_manager.current_session:
            self.session_manager.current_session.clear()
        self.query_one("#chat-container", RichLog).clear()

    def action_help(self):
        from ..utils.prompts import command_help

        self._add_message("system", command_help(self.config.language))


def run_tui():
    app = EchoClaudeTUI()
    app.run()
'''

target = r'C:\Users\郑丽君\Desktop\echo-claude\echo_claude\ui\tui_ui.py'
with open(target, 'w', encoding='utf-8') as f:
    f.write(content)
print('tui_ui.py written OK')
