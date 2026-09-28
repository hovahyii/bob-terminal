#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bob Terminal -- A chat interface with live token burn tracking."""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.prompt import Prompt
from rich.table import Table

# -- Config -------------------------------------------------------------------

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

API_BASE           = os.getenv("API_BASE", "https://api.openai.com/v1").rstrip("/")
API_KEY            = os.getenv("API_KEY", "")
MODEL              = os.getenv("MODEL", "gpt-4o-mini")
MAX_TOKENS         = int(os.getenv("MAX_TOKENS", "1024"))
COST_PROMPT_1K     = float(os.getenv("COST_PER_1K_PROMPT", "0.01"))
COST_COMPLETE_1K   = float(os.getenv("COST_PER_1K_COMPLETION", "0.03"))
BURN_METER_WIDTH   = 28
BURN_METER_MAX     = 10_000   # tokens considered "full bar"

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
        self.prompt_total      = 0
        self.completion_total  = 0
        self.total_total       = 0
        self.last_prompt       = 0
        self.last_completion   = 0
        self.last_total        = 0
        self.turn_count        = 0
        self.messages          = []   # conversation history for multi-turn

    @property
    def cost(self) -> float:
        return (
            self.prompt_total    / 1000 * COST_PROMPT_1K
            + self.completion_total / 1000 * COST_COMPLETE_1K
        )

    def record(self, usage: dict):
        self.last_prompt      = usage.get("prompt_tokens", 0)
        self.last_completion  = usage.get("completion_tokens", 0)
        self.last_total       = usage.get("total_tokens", 0)
        self.prompt_total     += self.last_prompt
        self.completion_total += self.last_completion
        self.total_total      += self.last_total
        self.turn_count       += 1

# -- Burn Meter ---------------------------------------------------------------

def burn_meter(tokens: int, width: int = BURN_METER_WIDTH, cap: int = BURN_METER_MAX) -> Text:
    ratio  = min(tokens / cap, 1.0)
    filled = int(ratio * width)
    empty  = width - filled
    pct    = int(ratio * 100)

    color = "green" if ratio < 0.5 else ("yellow" if ratio < 0.8 else "red")

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
    table.add_column("label", style="dim", no_wrap=True, min_width=14)
    table.add_column("value", no_wrap=True)

    table.add_row("Burn",      burn_meter(sess.total_total))
    table.add_row("Session",   Text(f"{sess.total_total:,} tokens", style="bold cyan"))
    table.add_row("Cost",      Text(f"${sess.cost:.4f} USD",        style="bold yellow"))

    if sess.turn_count > 0:
        table.add_row(
            "Last prompt",
            Text(
                f"{sess.last_prompt}p / {sess.last_completion}c = {sess.last_total} total",
                style="bright_white",
            ),
        )

    table.add_row(
        "Breakdown",
        Text(
            f"Prompt: {sess.prompt_total:,}  |  Completion: {sess.completion_total:,}",
            style="dim",
        ),
    )
    table.add_row("Turns",     Text(str(sess.turn_count), style="magenta"))

    return Panel(
        table,
        title="[bold]~~~ TOKEN BURN ~~~[/bold]",
        border_style="bright_black",
        expand=True,
    )

# -- API Call -----------------------------------------------------------------

def chat(sess: Session, user_message: str) -> tuple:
    """Send a message; return (reply_text, usage_dict)."""
    sess.messages.append({"role": "user", "content": user_message})

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    payload = {
        "model":      MODEL,
        "messages":   sess.messages,
        "max_tokens": MAX_TOKENS,
    }

    resp = requests.post(
        f"{API_BASE}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()

    data  = resp.json()
    reply = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage", {})

    sess.messages.append({"role": "assistant", "content": reply})
    return reply, usage

# -- Rendering Helpers --------------------------------------------------------

def print_header():
    console.print(Text(HEADER, style="bold blue"), highlight=False)
    console.print(
        Panel(
            Text(f"  Model: {MODEL}   |   Endpoint: {API_BASE}", style="dim"),
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
            Text(f"🤖 Bob: {text}", style="bright_white"),
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
            "[bold red]Error:[/bold red] No API key found. "
            "Copy [dim].env.template[/dim] to [dim].env[/dim] and set API_KEY."
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
                reply, usage = chat(sess, user_input)
            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else "?"
                console.print(
                    f"[bold red]Bob:[/bold red] Oops, my circuits crossed "
                    f"(HTTP {code}). Check your API key or endpoint and try again?"
                )
                continue
            except requests.exceptions.ConnectionError:
                console.print(
                    "[bold red]Bob:[/bold red] Can't reach the API -- "
                    "is API_BASE correct in your .env?"
                )
                continue
            except requests.exceptions.Timeout:
                console.print(
                    "[bold red]Bob:[/bold red] Request timed out. "
                    "The model might be busy -- try again in a moment."
                )
                continue
            except Exception:
                console.print(
                    "[bold red]Bob:[/bold red] Something unexpected happened. Try again?"
                )
                continue

        sess.record(usage)
        print_user_bubble(user_input)
        print_bob_bubble(reply)
        print_dashboard(sess)


if __name__ == "__main__":
    main()
