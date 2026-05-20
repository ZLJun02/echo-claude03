"""
Echo Claude TUI
"""

import asyncio
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import RichLog, Static, Input
from textual.markup import escape
from textual.binding import Binding

from ..core.agent import Agent
from ..config.settings import get_config
from ..providers import get_provider_class
from ..core.session import SessionManager
from ..utils.prompts import get_system_prompt


class EchoClaudeTUI(App):

    CSS = """
    Screen { background: #0d1f0d; layout: vertical; }

    #top-row { height: 1fr; layout: horizontal; }

    #left-box {
        width: 78%;
        background: #0d1f0d;
    }

    #chat-log {
        height: 100%;
        background: #0d1f0d;
        padding: 0 1;
        scrollbar-color: #50C878;
        scrollbar-background: #0a1a0a;
    }

    #right-box {
        width: 22%;
        background: #0a1a0a;
        layout: vertical;
    }

    .right-section {
        height: 50%;
        padding: 1;
    }

    .section-title {
        color: #50C878;
        text-style: bold;
        height: 1;
    }

    .section-body {
        color: #98FB98;
    }

    #input-row {
        height: 3;
        background: #0a1a0a;
        padding: 0 1;
    }

    #msg-input {
        width: 100%;
        background: #152515;
        color: #98FB98;
    }

    #msg-input:focus { border: tall #50C878; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出"),
        Binding("ctrl+l", "clear", "清空"),
        Binding("ctrl+j", "send_msg", "发送"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = get_config()
        self.agent = None
        self.session_manager = None
        self._current_provider = self.config.default_provider
        self._current_model = self.config.default_model
        self._is_responding = False
        self._task_list = []
        self._work_summary = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-row"):
            with Vertical(id="left-box"):
                yield RichLog(id="chat-log", wrap=True, markup=True, highlight=True)
            with Vertical(id="right-box"):
                with Vertical(classes="right-section"):
                    yield Static("[bold #50C878]过程[/bold #50C878]", classes="section-title")
                    yield Static("[dim #98FB98]--[/dim #98FB98]", id="process-body", classes="section-body")
                with Vertical(classes="right-section"):
                    yield Static("[bold #50C878]任务[/bold #50C878]", classes="section-title")
                    yield Static("[dim #98FB98]--[/dim #98FB98]", id="task-body", classes="section-body")
        with Horizontal(id="input-row"):
            yield Input(placeholder="输入消息，Ctrl+J 发送...", id="msg-input")

    def on_mount(self):
        self._init_agent()
        self._show_welcome()
        self.query_one("#msg-input", Input).focus()

    def _init_agent(self):
        try:
            pn = self.config.default_provider
            pc = self.config.get_provider(pn)
            if not pc: return
            PC = get_provider_class(pn)
            if not PC: return
            p = PC(api_key=pc.api_key, base_url=pc.base_url, models=pc.models)
            self.session_manager = SessionManager(save_path=Path(self.config.session.save_path).expanduser())
            model = self.config.default_model or (pc.models[0] if pc.models else None)
            self.agent = Agent(provider=p, model=model,
                               session=self.session_manager.get_or_create(), config=self.config,
                               system_prompt=get_system_prompt(self.config.language))
        except Exception as e:
            self._error(f"init: {e}")

    def _show_welcome(self):
        self.query_one("#chat-log", RichLog).write(
            "[bold #50C878]🌼[/bold #50C878] [#98FB98]你好！我是 Echo Claude AI编程助手！[/#98FB98]"
        )

    def _error(self, msg):
        self._add_msg("sys", f"[bold #FF8C00]⚠ {msg}[/bold #FF8C00]")

    def _add_msg(self, role, text):
        log = self.query_one("#chat-log", RichLog)
        if role == "user":
            log.write(f"[bold #FF8C00]✦[/bold #FF8C00] [#98FB98]{escape(text)}[/#98FB98]")
        elif role == "assistant":
            log.write(f"[bold #50C878]🌼[/bold #50C878] [#98FB98]{escape(text)}[/#98FB98]")
        else:
            log.write(f"[#FFFDD0]{escape(text)}[/#FFFDD0]")

    def _update_process(self, text):
        self._work_summary = text
        self.query_one("#process-body", Static).update(
            f"[#98FB98]{text}[/#98FB98]" if text else "[dim #98FB98]--[/dim #98FB98]"
        )

    def _update_tasks(self):
        body = self.query_one("#task-body", Static)
        if self._task_list:
            body.update(chr(10).join(f"[#98FB98]- {t}[/#98FB98]" for t in self._task_list[-15:]))
        else:
            body.update("[dim #98FB98]--[/dim #98FB98]")

    async def _do_send(self):
        if self._is_responding: return
        inp = self.query_one("#msg-input", Input)
        prompt = inp.value.strip()
        if not prompt: return
        inp.value = ""
        self._is_responding = True
        try:
            self._add_msg("user", prompt)
            if prompt.startswith("/"):
                await self._cmd(prompt)
            else:
                await self._chat(prompt)
        finally:
            self._is_responding = False
            self.query_one("#msg-input", Input).focus()
            self.query_one("#chat-log", RichLog).scroll_end(animate=False)

    async def _cmd(self, cmd):
        parts = cmd.split(maxsplit=1)
        c = parts[0].lower()
        a = parts[1] if len(parts) > 1 else ""
        if c == "/clear":
            if self.session_manager and self.session_manager.current_session:
                self.session_manager.current_session.clear()
            self.query_one("#chat-log", RichLog).clear()
            self._task_list.clear()
            self._update_tasks()
            self._update_process("")
            self._show_welcome()
        elif c == "/quit":
            self.exit()
        elif c == "/save":
            n = a or __import__("datetime").datetime.now().strftime("s_%H%M")
            if self.session_manager: self.session_manager.save_current_session(n)
            self._add_msg("sys", f"[#50C878]🌼 saved: {n}[/#50C878]")
        elif c == "/task":
            self._task_list.append(a or "new")
            self._update_tasks()
            self._add_msg("sys", f"[#50C878]🌼 +task[/#50C878]")
        elif c == "/done":
            if self._task_list:
                self._task_list.pop(0)
                self._update_tasks()
                self._add_msg("sys", f"[#50C878]🌼 done[/#50C878]")
        elif c == "/load":
            sm = self.session_manager
            if sm:
                if a:
                    s = sm.load_session(a)
                    if s:
                        self.agent.session = s
                        self.query_one("#chat-log", RichLog).clear()
                        for m in s.messages[-20:]:
                            self._add_msg(m.role, m.content)
                        self._add_msg("sys", f"[#50C878]🌼 loaded: {a}[/#50C878]")
                    else:
                        self._add_msg("sys", f"[#FF8C00]not found[/#FF8C00]")
                else:
                    ss = sm.list_sessions()
                    self._add_msg("sys", f"[#FFFDD0]{', '.join(s.name for s in ss[:10]) or 'none'}[/#FFFDD0]")
        else:
            self._add_msg("sys", f"[#FF8C00]?: {c}[/#FF8C00]")

    async def _chat(self, prompt):
        if not self.agent: return
        try:
            self._update_process(f"...{prompt[:40]}...")
            resp = self.agent.chat(prompt, stream=False)
            text = str(resp)
            self._add_msg("assistant", text)
            self._update_process(text[:120] + ("..." if len(text) > 120 else ""))
        except Exception as e:
            self._error(f"{e}")
            self._update_process(f"err: {e}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input and event.input.id == "msg-input":
            asyncio.create_task(self._do_send())

    def on_key(self, event):
        # Enter key as fallback send
        if event.key == "enter":
            focused = self.focused
            if focused and focused.id == "msg-input":
                asyncio.create_task(self._do_send())
                event.prevent_default()

    def action_send_msg(self):
        asyncio.create_task(self._do_send())

    def action_clear(self):
        if self.session_manager and self.session_manager.current_session:
            self.session_manager.current_session.clear()
        self.query_one("#chat-log", RichLog).clear()
        self._task_list.clear()
        self._update_tasks()
        self._update_process("")
        self._show_welcome()


def run_tui():
    EchoClaudeTUI().run()
