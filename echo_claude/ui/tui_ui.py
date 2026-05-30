# -*- coding: utf-8 -*-
"""
Echo Claude TUI -- Improved layout
"""

import asyncio
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Header, Footer, RichLog, Static, TextArea,
)
from textual.markup import escape
from textual.binding import Binding
from textual import work
from rich.text import Text
from rich.markdown import Markdown

from ..core.agent import Agent
from ..config.settings import get_config
from ..providers import get_provider_class
from ..core.session import SessionManager
from ..utils.prompts import get_system_prompt, command_help


class EchoClaudeTUI(App):
    """Echo Claude -- Improved TUI."""

    CSS = """
    Screen { background: #061206; color: #98FB98; }

    Header  { background: #061206; color: #FFFDD0; text-style: bold; dock: top; }
    Footer  { background: #061206; color: #50C878; dock: bottom; }

    #main-area  { height: 1fr; layout: vertical; }
    #chat-panel { height: 1fr; background: #061206; }
    #chat-log {
        background: #061206; color: #98FB98; padding: 1 2;
        scrollbar-color: #50C878; scrollbar-background: #071207;
        scrollbar-size-vertical: 1;
    }

    #streaming-area {
        height: 15; border-top: solid #1a3a1a;
        background: #061206; color: #98FB98;
        padding: 1 2;
        display: none;
    }
    #streaming-area.visible {
        display: block;
    }

    #input-area {
        height: auto; background: #061206; padding: 1 2;
        border-top: solid #1a3a1a; layout: horizontal;
    }
    #msg-input {
        width: 1fr; height: 5; background: #0a1f0a; color: #98FB98;
        border: none;
    }
    #msg-input:focus {
        border: none;
    }

    #status-bar { height: 1; background: #0a160a; padding: 0 2; border-top: solid #1a3a1a; }
    #status-left { width: 1fr; content-align: left middle; padding: 0 1; }
    #status-right { width: auto; content-align: right middle; padding: 0 1; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear chat"),
        Binding("ctrl+s", "quick_save", "Save session"),
        Binding("escape", "focus_input", "Focus input"),
        Binding("f1", "show_help", "Help"),
        Binding("enter", "send", "Send", priority=True),
        Binding("shift+enter", "newline", "Newline", priority=True),
        Binding("ctrl+up", "history_prev", "History prev"),
        Binding("ctrl+down", "history_next", "History next"),
        Binding("ctrl+g", "cancel", "Cancel"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = get_config()
        self.agent: Optional[Agent] = None
        self.session_manager: Optional[SessionManager] = None
        self._provider = self.config.default_provider
        self._model = self.config.default_model or "auto"
        self._busy = False
        self._msg_n = 0
        self._history: List[str] = []
        self._history_index = -1
        self._streaming_buffer = ""
        self._current_worker: Optional[object] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="main-area"):
            with Vertical(id="chat-panel"):
                yield RichLog(id="chat-log", wrap=True, markup=True, highlight=True)
            yield RichLog(id="streaming-area", wrap=True, markup=True, highlight=True)

        with Horizontal(id="input-area"):
            yield TextArea(placeholder="Enter to send, Shift+Enter for newline ...", id="msg-input", soft_wrap=True)

        with Horizontal(id="status-bar"):
            yield Static("", id="status-left")
            yield Static("Ready", id="status-right", markup=True)

        yield Footer()

    def on_mount(self) -> None:
        self._init_agent()
        self.query_one("#msg-input").soft_wrap = True
        self.title = Text("🍅  ", style="#9370DB") + Text(f"Echo Claude - {self._provider}/{self._model}")
        self._show_welcome()
        self.query_one("#msg-input").focus()

    def _init_agent(self):
        try:
            pc = self.config.get_provider(self._provider)
            if not pc:
                return
            PC = get_provider_class(self._provider)
            if not PC:
                return
            provider = PC(api_key=pc.api_key, base_url=pc.base_url, models=pc.models)
            self.session_manager = SessionManager(
                save_path=Path(self.config.session.save_path).expanduser()
            )
            self.agent = Agent(
                provider=provider,
                model=self._model if self._model != "auto"
                else (pc.models[0] if pc.models else None),
                session=self.session_manager.get_or_create(),
                config=self.config,
                system_prompt=get_system_prompt(self.config.language),
            )
            self._update_session_info()
            self._update_token_display()
        except Exception as e:
            self._sys(f"[bold #FF8C00]Init error: {e}[/bold #FF8C00]")

    def _update_session_info(self):
        session_name = (
            self.session_manager.current_session.name
            if self.session_manager and self.session_manager.current_session
            else "none"
        )
        left_text = f"Provider: {self._provider or '---'} | Model: {self._model or 'auto'} | Session: {session_name}"
        self.query_one("#status-left", Static).update(left_text)

    def _update_token_display(self):
        if not self.agent:
            return
        usage = self.agent.get_token_usage()
        right_text = f"Tokens: {usage['prompt_tokens']}/{usage['completion_tokens']} | Msgs: {self._msg_n}"
        self.query_one("#status-right", Static).update(right_text)

    def _show_welcome(self):
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold #50C878]  Echo Claude  AI Assistant[/bold #50C878]\n")
        log.write("[dim #7ab87a]Type /help for commands, Ctrl+Q to quit[/dim #7ab87a]\n")
        self._update_session_info()
        self._update_token_display()

    def _show_streaming(self):
        area = self.query_one("#streaming-area", RichLog)
        area.add_class("visible")

    def _hide_streaming(self):
        area = self.query_one("#streaming-area", RichLog)
        area.remove_class("visible")
        area.clear()
        self._streaming_buffer = ""

    def _update_streaming(self, text: str):
        area = self.query_one("#streaming-area", RichLog)
        area.clear()
        area.write(Markdown(text))

    def _add(self, role: str, text: str):
        log = self.query_one("#chat-log", RichLog)
        ts = datetime.now().strftime("%H:%M")
        if self._msg_n > 0:
            log.write("[dim]──────────────────────────────────────[/dim]")
        if role == "user":
            log.write(
                f"[dim #50C878]{ts}[/dim #50C878]  "
                f"[bold #FF8C00]You[/bold #FF8C00]  "
                f"[#98FB98]{escape(text)}[/#98FB98]"
            )
        elif role == "assistant":
            log.write(
                f"[dim #50C878]{ts}[/dim #50C878]  "
                f"[bold #50C878]Echo[/bold #50C878]"
            )
            log.write(Markdown(text))
        else:
            log.write(f"[dim #50C878]{ts}[/dim #50C878]  [#FFFDD0]{text}[/#FFFDD0]")
        self._msg_n += 1
        self._update_token_display()

    def _status(self, text: str):
        self.query_one("#status-right", Static).update(f"[#7ab87a]{text}[/#7ab87a]")

    def _sys(self, text: str):
        self._add("system", text)

    def _err(self, msg: str):
        self._sys(f"[bold #FF8C00]{msg}[/bold #FF8C00]")

    def _blocking_stream(self, prompt: str, q: queue.Queue):
        """Runs in a separate thread; puts chunks into queue."""
        try:
            if not self.agent:
                q.put(None)
                return
            for chunk in self.agent.chat(prompt, stream=True):
                q.put(chunk)
        except Exception as e:
            q.put(f"[ERROR]{e}")
        finally:
            q.put(None)  # sentinel

    async def _perform_streaming_chat(self, prompt: str):
        if not self.agent:
            self._err("Agent not initialized")
            return

        # Set up streaming buffer and UI
        self._streaming_buffer = ""
        self._show_streaming()
        self._update_streaming("")

        q = queue.Queue()
        thread = threading.Thread(target=self._blocking_stream, args=(prompt, q), daemon=True)
        thread.start()

        try:
            while True:
                # Wait for chunk from the worker thread
                chunk = await asyncio.get_running_loop().run_in_executor(None, q.get)
                if chunk is None:
                    break
                if isinstance(chunk, str) and chunk.startswith("[ERROR]"):
                    raise RuntimeError(chunk[7:])
                self._streaming_buffer += chunk
                self._update_streaming(self._streaming_buffer)
                # Yield control to event loop
                await asyncio.sleep(0)
        finally:
            # Cleanup will be handled by _do_send finally
            pass

    @work(exclusive=True)
    async def _do_send(self):
        if self._busy:
            return
        inp = self.query_one("#msg-input", TextArea)
        self._busy = True
        try:
            text = inp.text.strip()
            if not text:
                return
            # Add to history
            if not self._history or self._history[-1] != text:
                self._history.append(text)
            self._history_index = -1
            inp.text = ""
            self._add("user", text)
            if text.startswith("/"):
                await self._handle_cmd(text)
            else:
                await self._perform_streaming_chat(text)
                if self._streaming_buffer:
                    # Session message already added by agent during streaming
                    self._add("assistant", self._streaming_buffer)
                self._status("Ready")
        except asyncio.CancelledError:
            self._status("Cancelled")
        except Exception as e:
            self._err(f"Error: {e}")
            self._status(f"Error: {e}")
        finally:
            self._busy = False
            self._current_worker = None
            self._hide_streaming()
            inp.focus()

    async def _handle_cmd(self, cmd: str):
        parts = cmd.split(maxsplit=1)
        c = parts[0].lower()
        a = parts[1] if len(parts) > 1 else ""

        if c == "/help":
            self._sys(command_help(self.config.language))
        elif c == "/clear":
            if self.session_manager and self.session_manager.current_session:
                self.session_manager.current_session.clear()
            self.query_one("#chat-log", RichLog).clear()
            self._msg_n = 0
            self._show_welcome()
        elif c == "/quit":
            self.exit()
        elif c == "/save":
            name = a or datetime.now().strftime("session_%Y%m%d_%H%M%S")
            if self.session_manager:
                self.session_manager.save_current_session(name)
                self._sys(f"[#50C878]Saved: {name}[/#50C878]")
        elif c == "/load":
            sm = self.session_manager
            if sm:
                if a:
                    s = sm.load_session(a)
                    if s:
                        self.agent.session = s
                        self.query_one("#chat-log", RichLog).clear()
                        self._msg_n = 0
                        for m in s.messages[-20:]:
                            self._add(m.role, m.content)
                        self._sys(f"[#50C878]Loaded: {a}[/#50C878]")
                        self._update_session_info()
                    else:
                        self._err(f"Session not found: {a}")
                else:
                    sessions = sm.list_sessions()
                    names = ", ".join(s.name for s in sessions[:10]) or "none"
                    self._sys(f"[#FFFDD0]Sessions: {names}[/#FFFDD0]")
        elif c == "/model":
            self._sys(
                f"[#FFFDD0]Provider: {self._provider}  "
                f"Model: {self._model}[/#FFFDD0]"
            )
        else:
            self._err(f"Unknown: {c}  (try /help)")

    def action_send(self):
        if not self._current_worker or not self._current_worker.is_running:
            self._current_worker = self._do_send()

    def action_clear(self):
        if self.session_manager and self.session_manager.current_session:
            self.session_manager.current_session.clear()
        self.query_one("#chat-log", RichLog).clear()
        self._msg_n = 0
        self._show_welcome()

    def action_quick_save(self):
        sm = self.session_manager
        if sm and sm.current_session:
            sm.save_current_session()
            self._status(f"Session saved: {sm.current_session.name}")
        else:
            self._status("No session to save")

    def action_show_help(self):
        self._sys(command_help(self.config.language))

    def action_focus_input(self):
        self.query_one("#msg-input", TextArea).focus()

    def action_cancel(self):
        if self._current_worker and self._current_worker.is_running:
            self._status("Cancelling...")
            self._current_worker.cancel()

    def action_quit(self):
        self.exit()

    def action_history_prev(self):
        if not self._history:
            return
        inp = self.query_one("#msg-input", TextArea)
        if self._history_index == -1:
            self._history_index = len(self._history) - 1
        else:
            self._history_index = max(0, self._history_index - 1)
        inp.text = self._history[self._history_index]
        inp.cursor_position = len(inp.text)

    def action_history_next(self):
        if not self._history or self._history_index == -1:
            return
        inp = self.query_one("#msg-input", TextArea)
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
        else:
            self._history_index = -1
            inp.text = ""
            return
        inp.text = self._history[self._history_index]
        inp.cursor_position = len(inp.text)


    def action_newline(self):
        inp = self.query_one("#msg-input", TextArea)
        inp.insert("\n")
        inp.focus()


def run_tui():
    EchoClaudeTUI().run()
