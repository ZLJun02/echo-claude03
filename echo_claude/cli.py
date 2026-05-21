"""
Echo Claude 命令行界面
使用 Typer 实现，中英友好
"""

import json
from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.prompt import Prompt, Confirm

from .config.settings import get_config, init_config, AppConfig
from .config.providers import list_available_providers, get_provider_template
from .core.agent import Agent
from .core.session import Session, SessionManager
from .providers import get_provider_class

app = typer.Typer(
    name="ec",
    help="Echo Claude - 中文友好 AI 编程助手",
    add_completion=False,
)
console = Console()

# 全局会话管理器
_session_manager: Optional[SessionManager] = None


def get_agent(provider_name: str = None, model_name: str = None) -> Agent:
    """创建 Agent 实例"""
    config = get_config()

    provider = provider_name or config.default_provider
    model = model_name

    provider_config = config.get_provider(provider)
    if not provider_config:
        raise typer.BadParameter(f"Provider '{provider}' 未在配置中找到")

    ProviderClass = get_provider_class(provider)
    if not ProviderClass:
        raise typer.BadParameter(f"不支持的提供者: {provider}")

    provider_instance = ProviderClass(
        name=provider_config.name,
        api_key=provider_config.api_key,
        base_url=provider_config.base_url,
        models=provider_config.models,
        timeout=provider_config.timeout,
        max_retries=provider_config.max_retries,
    )

    session = _session_manager.current_session if _session_manager else None

    return Agent(
        provider=provider_instance,
        model=model or (provider_config.models[0] if provider_config.models else None),
        session=session,
        config=config,
    )


def ensure_session_manager() -> SessionManager:
    """确保会话管理器已初始化"""
    global _session_manager
    if _session_manager is None:
        config = get_config()
        _session_manager = SessionManager(
            save_path=Path(config.session.save_path).expanduser()
        )
    return _session_manager


@app.command()
def chat(
    prompt: str = typer.Argument(..., help="用户输入/问题"),
    provider: str = typer.Option(None, "--provider", "-p", help="指定模型提供者"),
    model: str = typer.Option(None, "--model", "-m", help="指定模型名称"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="流式输出"),
    system: str = typer.Option(None, "--system", "-s", help="系统提示词"),
):
    """单轮对话模式"""
    try:
        agent = get_agent(provider, model)

        # 显示当前模型信息
        console.print(Panel.fit(f"[bold cyan]🟢 Echo Claude[/bold cyan]\n"
                                f"[dim]模型: {agent.provider.name}/{agent.model}[/dim]"))

        # 如果有系统提示词，先发送系统消息
        if system:
            agent.session.add_message("system", system) if agent.session else None

        # 发送用户消息并获取响应
        with console.status("[bold green]思考中...[/bold green]"):
            response = agent.chat(prompt, stream=stream)

        # 输出响应
        if stream:
            full_response = ""
            for chunk in response:
                console.print(chunk, end="")
                full_response += chunk
            console.print()
            response = full_response
        else:
            console.print(Markdown(str(response)))

        # 消息已由 agent.chat() 内部保存到会话

    except Exception as e:
        console.print(f"[bold red]❌ 错误:[/bold red] {e}")


@app.command()
def tui():
    """启动 TUI 交互界面"""
    try:
        from .ui.tui_ui import EchoClaudeTUI
        tui_app = EchoClaudeTUI()
        tui_app.run()
    except ImportError as e:
        console.print(f"[bold red]无法启动 TUI:[/bold red] {e}")
        console.print("请确保已安装 textual: pip install textual")


@app.command()
def config(
    action: str = typer.Argument("show", help="init/show/reset"),
    provider: str = typer.Option(None, "--provider", "-p", help="配置特定提供者"),
):
    """配置管理"""
    config_path = Path.home() / ".echo-claude" / "config.yaml"

    if action == "init":
        if config_path.exists():
            if not Confirm.ask(f"配置文件已存在，是否覆盖？"):
                return
        config = init_config(config_path)
        console.print(f"[green]✓[/green] 配置文件已创建: {config_path}")
        console.print("\n请编辑配置文件添加 API Key：")
        console.print(f"  {config_path}")

        # 显示可用的提供者
        console.print("\n[bold]可用模型提供者：[/bold]")
        table = Table(show_header=True)
        table.add_column("名称")
        table.add_column("描述")
        table.add_column("环境变量")
        for p in list_available_providers():
            table.add_row(p["name"], p["description"], p["env_var"] or "-")
        console.print(table)

    elif action == "show":
        cfg = get_config()
        console.print(Panel.fit("[bold]当前配置[/bold]"))
        console.print(f"默认提供者: {cfg.default_provider}")
        console.print(f"默认模型: {cfg.default_model or '未设置'}")
        console.print(f"语言: {cfg.language}")
        console.print(f"\n[bold]配置的提供者：[/bold]")
        for name in cfg.providers:
            p = cfg.get_provider(name)
            if p:
                console.print(f"  • {name}: {p.base_url or '未设置'} "
                              f"({len(p.models)} 个模型)")

    elif action == "reset":
        if config_path.exists() and Confirm.ask("确定要重置配置吗？"):
            config_path.unlink()
            console.print("[green]✓[/green] 配置已重置")


@app.command()
def session(
    action: str = typer.Argument("list", help="list/save/load/delete/clear"),
    name: str = typer.Argument(None, help="会话名称（对于 save/load/delete）"),
):
    """会话管理"""
    manager = ensure_session_manager()

    if action == "list":
        sessions = manager.list_sessions()
        if not sessions:
            console.print("[yellow]暂无保存的会话[/yellow]")
            return

        table = Table(show_header=True)
        table.add_column("名称")
        table.add_column("消息数")
        table.add_column("创建时间")
        table.add_column("更新时间")
        for s in sessions:
            table.add_row(
                s.name,
                str(len(s.messages)),
                s.created_at[:19],
                s.updated_at[:19],
            )
        console.print(Panel(table, title="会话列表"))

    elif action == "save":
        if not name:
            name = Prompt.ask("请输入会话名称")
        manager.save_current_session(name)
        console.print(f"[green]✓[/green] 会话已保存: {name}")

    elif action == "load":
        if not name:
            # 显示列表供选择
            sessions = manager.list_sessions()
            if not sessions:
                console.print("[yellow]暂无保存的会话[/yellow]")
                return
            choices = [s.name for s in sessions]
            name = Prompt.ask("选择要加载的会话", choices=choices)
        manager.load_session(name)
        console.print(f"[green]✓[/green] 会话已加载: {name}")

    elif action == "delete":
        if not name:
            sessions = manager.list_sessions()
            if not sessions:
                console.print("[yellow]暂无保存的会话[/yellow]")
                return
            choices = [s.name for s in sessions]
            name = Prompt.ask("选择要删除的会话", choices=choices)
        if Confirm.ask(f"确定删除会话 '{name}'？"):
            manager.delete_session(name)
            console.print(f"[green]✓[/green] 会话已删除: {name}")

    elif action == "clear":
        if Confirm.ask("清空当前会话？"):
            if manager.current_session:
                manager.current_session.clear()
                console.print("[green]✓[/green] 当前会话已清空")


@app.command()
def model(
    action: str = typer.Argument("list", help="list/switch/info"),
    name: str = typer.Argument(None, help="模型名称"),
):
    """模型管理"""
    config = get_config()

    if action == "list":
        table = Table(show_header=True)
        table.add_column("提供者")
        table.add_column("模型")
        table.add_column("状态")
        for provider_name, p in config.providers.items():
            for model in p.models:
                is_default = (provider_name == config.default_provider and
                              model == config.default_model)
                status = "[green]默认[/green]" if is_default else ""
                table.add_row(provider_name, model, status)
        console.print(Panel(table, title="可用模型"))

    elif action == "switch":
        if not name:
            console.print("[red]请指定模型名称[/red]")
            return
        # 查找模型属于哪个提供者
        for provider_name, p in config.providers.items():
            if name in p.models:
                config.default_provider = provider_name
                config.default_model = name
                console.print(f"[green]✓[/green] 已切换到: {provider_name}/{name}")
                return
        console.print(f"[red]模型 '{name}' 未找到[/red]")

    elif action == "info":
        console.print(Panel.fit(f"[bold]当前模型[/bold]\n"
                                f"提供者: {config.default_provider}\n"
                                f"模型: {config.default_model or '自动'}"))


@app.command()
def tool(
    action: str = typer.Argument("list", help="list/test"),
    tool_name: str = typer.Argument(None, help="工具名称"),
    args: List[str] = typer.Argument(None, help="工具参数"),
):
    """工具管理"""
    from .core.tools import ToolRegistry

    if action == "list":
        tools = ToolRegistry.list_tools()
        table = Table(show_header=True)
        table.add_column("名称")
        table.add_column("描述")
        table.add_column("状态")
        for name, info in tools.items():
            enabled = "[green]启用[/green]" if info.get("enabled") else "[red]禁用[/red]"
            table.add_row(name, info.get("description", ""), enabled)
        console.print(Panel(table, title="可用工具"))

    elif action == "test":
        if not tool_name:
            console.print("[red]请指定工具名称[/red]")
            return
        try:
            result = ToolRegistry.execute(tool_name, args or [])
            console.print(Panel.fit(f"[bold]工具执行结果[/bold]\n{result}"))
        except Exception as e:
            console.print(f"[bold red]执行失败:[/bold red] {e}")


@app.command()
def shell(
    command: str = typer.Argument(..., help="要执行的Shell命令"),
):
    """直接执行Shell命令（安全沙箱内）"""
    from .core.tools import ShellTool
    try:
        tool = ShellTool()
        result = tool.execute(command, timeout=30)
        console.print(result)
    except Exception as e:
        console.print(f"[bold red]执行失败:[/bold red] {e}")


@app.command()
def read_file(
    path: str = typer.Argument(..., help="要读取的文件路径"),
):
    """读取文件内容"""
    from .core.tools import FileReadTool
    config = get_config()
    try:
        safe_dirs = config.tool.safe_dirs if config and hasattr(config, 'tool') else None
        tool = FileReadTool(safe_dirs=safe_dirs or ["./", "./tmp"])
        result = tool.execute(path=path)
        if result.success:
            content = result.output
            # 检测语言做语法高亮
            suffix_map = {
                ".py": "python", ".js": "javascript", ".ts": "typescript",
                ".html": "html", ".css": "css", ".json": "json",
                ".yaml": "yaml", ".yml": "yaml", ".md": "markdown",
                ".sh": "bash", ".bat": "batch", ".toml": "toml",
                ".rs": "rust", ".go": "go", ".java": "java",
            }
            lang = suffix_map.get(Path(path).suffix, "text")
            syntax = Syntax(content, lang, line_numbers=True, theme=config.display.theme)
            console.print(Panel(syntax, title=Path(path).name))
        else:
            console.print(f"[bold red]读取失败:[/bold red] {result.error}")
    except Exception as e:
        console.print(f"[bold red]读取失败:[/bold red] {e}")


def main():
    """主入口"""
    # 自动加载配置
    try:
        get_config()
    except Exception as e:
        console.print(f"[yellow]警告: 配置加载失败 - {e}[/yellow]")
        console.print("运行 'ec config init' 创建配置文件")

    app()


if __name__ == "__main__":
    main()