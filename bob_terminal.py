#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bob Terminal -- Chat with IBM Bob in your terminal with live token burn tracking."""

import os
import sys
import json
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.prompt import Prompt
from rich.table import Table

# -- Config -------------------------------------------------------------------

API_KEY   = os.getenv("BOB_API_KEY", "")
TEAM_ID   = os.getenv("BOB_TEAM_ID", "")

def _find_bob() -> str:
    """Return the bob executable path, searching npm global prefix."""
    if os.getenv("BOB_CMD"):
        return os.getenv("BOB_CMD")
    try:
        result = subprocess.run(
            ["cmd", "/c", "npm", "prefix", "-g"],
            capture_output=True, text=True, timeout=5
        )
        prefix = result.stdout.strip()
        for name in ["bob.cmd", "bob"]:
            candidate = os.path.join(prefix, name)
            if os.path.exists(candidate):
                return candidate
    except Exception:
        pass
    return "bob"

BOB_CMD = _find_bob()

BURN_METER_WIDTH = 28
BURN_METER_MAX   = 50_000   # tokens at which bar is "full" (Inference keys: large context)

console = Console()

# -- ASCII Header -------------------------------------------------------------

HEADER = r"""
  ____   ___  ____    _____ _____ ____  __  __ ___ _   _    _    _
 | __ ) / _ \| __ )  |_   _| ____|  _ \|  \/  |_ _| \ | |  / \  | |
 |  _ \| | | |  _ \    | | |  _| | |_) | |\/| || ||  \| | / _ \ | |
 | |_) | |_| | |_) |   | | | |___|  _ <| |  | || || |\  |/ ___ \| |___
 |____/ \___/|____/    |_| |_____|_| \_\_|  |_|___|_| \_/_/   \_\_____|
"""

# -- Session State ------------------------------------------------------------

class Session:
    def __init__(self):
        self.input_total      = 0
        self.output_total     = 0
        self.total_total      = 0
        self.cost_total       = 0.0   # session_costs in Bobcoins
        self.last_input       = 0
        self.last_output      = 0
        self.last_total       = 0
        self.last_cost        = 0.0
        self.last_duration_ms = 0
        self.turn_count       = 0

    def record(self, stats: dict):
        self.last_input       = stats.get("input_tokens", 0)
        self.last_output      = stats.get("output_tokens", 0)
        self.last_total       = stats.get("total_tokens", 0)
        self.last_cost        = stats.get("session_costs", 0.0)
        self.last_duration_ms = stats.get("duration_ms", 0)
        self.input_total      += self.last_input
        self.output_total     += self.last_output
        self.total_total      += self.last_total
        self.cost_total       += self.last_cost
        self.turn_count       += 1

# -- Burn Meter ---------------------------------------------------------------

def burn_meter(tokens: int, width: int = BURN_METER_WIDTH, cap: int = BURN_METER_MAX) -> Text:
    ratio  = min(tokens / cap, 1.0)
    filled = int(ratio * width)
    empty  = width - filled
    pct    = int(ratio * 100)
    color  = "green" if ratio < 0.5 else ("yellow" if ratio < 0.8 else "red")

    bar = Text()
    bar.append("[", style="dim")
    bar.append("#" * filled, style=f"bold {color}")
    bar.append("." * empty,  style="dim")
    bar.append("] ", style="dim")
    bar.append(f"{pct}%", style=f"bold {color}")
    return bar

# -- Token Dashboard ----------------------------------------------------------

def build_dashboard(sess: Session) -> Panel:
    table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
    table.add_column("label", style="dim", no_wrap=True, min_width=16)
    table.add_column("value", no_wrap=True)

    table.add_row("Burn",         burn_meter(sess.total_total))
    table.add_row("Session",      Text(f"{sess.total_total:,} tokens", style="bold cyan"))
    table.add_row("Bobcoin spend",Text(f"{sess.cost_total:.4f} coins", style="bold yellow"))

    if sess.turn_count > 0:
        secs = sess.last_duration_ms / 1000
        table.add_row(
            "Last prompt",
            Text(
                f"{sess.last_input}in / {sess.last_output}out = {sess.last_total} total"
                f"  ({secs:.1f}s)",
                style="bright_white",
            ),
        )
        table.add_row(
            "Last cost",
            Text(f"{sess.last_cost:.4f} Bobcoins", style="yellow"),
        )

    table.add_row(
        "Breakdown",
        Text(
            f"Input: {sess.input_total:,}  |  Output: {sess.output_total:,}",
            style="dim",
        ),
    )
    table.add_row("Turns", Text(str(sess.turn_count), style="magenta"))

    return Panel(
        table,
        title="[bold]~~~ TOKEN BURN ~~~[/bold]",
        border_style="bright_black",
        expand=True,
    )

# -- Bob Shell call -----------------------------------------------------------

def ask_bob(prompt: str) -> tuple:
    """
    Run: BOB_API_KEY=... bob run --format stream-json "<prompt>"
    Parse NDJSON stream, return (reply_text, stats_dict).
    """
    env = os.environ.copy()
    env["BOB_API_KEY"] = API_KEY

    cmd = [BOB_CMD, "run", "--format", "stream-json", "--disable-subagents",
           "--disable-mcp", "--trust", "--accept-license", prompt]

    if TEAM_ID:
        cmd += ["--team-id", TEAM_ID]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=120,
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"'{BOB_CMD}' not found. Install Bob Shell: "
            "powershell -c \"irm https://bob.ibm.com/download/bobshell.ps1 | iex\""
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Bob took too long to respond. Try again.")

    reply = ""
    stats = {}

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type", "")

        if etype == "message" and event.get("role") == "assistant":
            content = event.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        reply += block.get("text", "")
            elif isinstance(content, str):
                reply += content

        elif etype == "result":
            raw = event.get("stats", {})
            # stream-json gives full token counts; json format only gives session_costs
            stats = {
                "input_tokens":  raw.get("input_tokens", 0),
                "output_tokens": raw.get("output_tokens", 0),
                "total_tokens":  raw.get("total_tokens",
                                   raw.get("input_tokens", 0) + raw.get("output_tokens", 0)),
                "session_costs": raw.get("session_costs", 0.0),
                "duration_ms":   raw.get("duration_ms", 0),
            }
            if not reply:
                reply = event.get("last_message", "")

    if proc.returncode != 0 and not reply:
        stderr = proc.stderr.strip()
        raise RuntimeError(stderr or f"bob exited with code {proc.returncode}")

    return reply.strip(), stats

# -- Rendering Helpers --------------------------------------------------------

def print_header():
    console.print(Text(HEADER, style="bold blue"), highlight=False)
    console.print(
        Panel(
            Text("  Powered by IBM Bob Shell  |  BOB_API_KEY loaded", style="dim"),
            border_style="blue",
            title="[bold blue]BOB TERMINAL v1.0[/bold blue]",
        )
    )
    console.print(
        "[dim]Type your message and press Enter.  "
        "Type [bold]exit[/bold] or [bold]quit[/bold] to leave.[/dim]\n"
    )


def print_user_bubble(text: str):
    console.print(
        Panel(
            Text(text, style="bold white"),
            title="[bold green]You[/bold green]",
            border_style="green",
            expand=False,
        )
    )


def print_bob_bubble(text: str):
    console.print(
        Panel(
            Text(f"Bob: {text}", style="bright_white"),
            title="[bold cyan]Bob[/bold cyan]",
            border_style="cyan",
        )
    )


def print_dashboard(sess: Session):
    console.print(build_dashboard(sess))
    console.print(Rule(style="bright_black"))

# -- Main Loop ----------------------------------------------------------------

def main():
    if not API_KEY or API_KEY == "your-api-key-here":
        console.print(
            "[bold red]Error:[/bold red] BOB_API_KEY is not set.\n"
            "Set it before running:\n\n"
            '  [bold]$env:BOB_API_KEY="bob_prod_bob-apikey_..."[/bold]\n\n'
            "Or add it to your shell profile permanently."
        )
        sys.exit(1)

    print_header()
    sess = Session()

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "bye"}:
            console.print("[dim]Goodbye![/dim]")
            break

        with console.status("[cyan]Bob is thinking...[/cyan]", spinner="dots"):
            try:
                reply, stats = ask_bob(user_input)
            except RuntimeError as exc:
                console.print(f"[bold red]Bob:[/bold red] Oops, my circuits crossed. {exc}")
                continue
            except Exception:
                console.print(
                    "[bold red]Bob:[/bold red] Something unexpected happened. Try again?"
                )
                continue

        if not reply:
            reply = "(no response)"

        sess.record(stats)
        print_user_bubble(user_input)
        print_bob_bubble(reply)
        print_dashboard(sess)


if __name__ == "__main__":
    main()
