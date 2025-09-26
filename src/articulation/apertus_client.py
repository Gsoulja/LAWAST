#!/usr/bin/env python3
"""
LAWAST Apertus Chat Client - Using HuggingFace Chat Completion API
"""

import os
import json
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from huggingface_hub import InferenceClient
import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Initialize console
console = Console()

# Configuration
API_KEY = os.getenv("HUGGINGFACE_API_KEY")
MODEL = "swiss-ai/Apertus-8B-Instruct-2509"
DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.7


class ApertusChatClient:
    """Client for Apertus model using chat completion API"""

    def __init__(self, model: str = MODEL, api_key: Optional[str] = None):
        """Initialize Apertus chat client"""
        self.model = model
        api_key = api_key or API_KEY
        self.client = InferenceClient(token=api_key)
        console.print(f"[green]✓[/green] Connected to {model}")

    def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = 0.95,
        stream: bool = False
    ) -> str:
        """
        Send a chat message to Apertus

        Args:
            message: User message
            system_prompt: System instructions
            history: Conversation history
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling
            stream: Whether to stream response

        Returns:
            Model response
        """
        # Build messages
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": message})

        try:
            if stream:
                return self._stream_chat(messages, max_tokens, temperature, top_p)
            else:
                response = self.client.chat_completion(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                )
                return response.choices[0].message.content

        except Exception as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            raise

    def _stream_chat(self, messages, max_tokens, temperature, top_p):
        """Stream chat response"""
        console.print("\n[cyan]Assistant:[/cyan]")
        full_response = ""

        for chunk in self.client.chat_completion(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=True,
        ):
            if chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                console.print(text, end="")
                full_response += text

        console.print()
        return full_response


# CLI Interface
@click.group()
@click.option('--model', default=MODEL, help='Model name')
@click.option('--api-key', envvar='HUGGINGFACE_API_KEY', default=API_KEY, help='API key')
@click.pass_context
def cli(ctx, model, api_key):
    """Apertus Chat CLI - Swiss AI Language Model"""
    ctx.ensure_object(dict)
    ctx.obj['client'] = ApertusChatClient(model, api_key)


@cli.command()
@click.argument('message')
@click.option('--system', '-s', help='System prompt')
@click.option('--max-tokens', '-m', default=DEFAULT_MAX_TOKENS, help='Max tokens')
@click.option('--temperature', '-t', default=DEFAULT_TEMPERATURE, help='Temperature')
@click.option('--stream', is_flag=True, help='Stream response')
@click.pass_context
def ask(ctx, message, system, max_tokens, temperature, stream):
    """Send a single message to Apertus"""
    client = ctx.obj['client']

    response = client.chat(
        message=message,
        system_prompt=system,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=stream
    )

    if not stream:
        console.print(Panel(
            Markdown(response),
            title="[bold cyan]Apertus Response[/bold cyan]",
            border_style="cyan"
        ))


@cli.command()
@click.option('--system', '-s', help='System prompt for the conversation')
@click.option('--max-tokens', '-m', default=DEFAULT_MAX_TOKENS, help='Max tokens per response')
@click.option('--temperature', '-t', default=DEFAULT_TEMPERATURE, help='Temperature')
@click.option('--stream', is_flag=True, help='Stream responses')
@click.option('--language', '-l', type=click.Choice(['en', 'de', 'fr', 'it', 'rm']), help='Preferred language')
@click.pass_context
def chat(ctx, system, max_tokens, temperature, stream, language):
    """Interactive chat with Apertus"""
    client = ctx.obj['client']
    history = []

    # Language-specific system prompts
    language_prompts = {
        'de': "Bitte antworte auf Deutsch.",
        'fr': "Veuillez répondre en français.",
        'it': "Per favore rispondi in italiano.",
        'rm': "Respunda per plaschair en rumantsch.",
        'en': "Please respond in English."
    }

    # Combine system prompt with language preference
    if language and language in language_prompts:
        lang_prompt = language_prompts[language]
        system = f"{system}\n\n{lang_prompt}" if system else lang_prompt

    console.print(Panel.fit(
        "[bold cyan]Apertus Chat Interface[/bold cyan]\n"
        "Swiss AI Language Model (Apertus-8B-Instruct)\n\n"
        "Commands: 'exit' to quit, 'clear' to reset, 'help' for help",
        border_style="cyan"
    ))

    if system:
        console.print(f"[dim]System: {system}[/dim]\n")

    while True:
        try:
            # Get user input
            user_input = console.input("\n[bold green]You:[/bold green] ")

            # Handle commands
            if user_input.lower() == 'exit':
                console.print("[yellow]Auf Wiedersehen! Au revoir! Arrivederci! Goodbye![/yellow]")
                break
            elif user_input.lower() == 'clear':
                history = []
                console.print("[yellow]Conversation history cleared[/yellow]")
                continue
            elif user_input.lower() == 'help':
                console.print(
                    "[cyan]Commands:[/cyan]\n"
                    "  exit     - Quit the chat\n"
                    "  clear    - Clear conversation history\n"
                    "  help     - Show this help\n"
                    "  !system  - Change system prompt\n"
                    "  !lang    - Change language (de/fr/it/rm/en)"
                )
                continue
            elif user_input.startswith('!system'):
                new_system = user_input[7:].strip()
                system = new_system
                console.print(f"[yellow]System prompt updated[/yellow]")
                continue
            elif user_input.startswith('!lang'):
                new_lang = user_input[5:].strip().lower()
                if new_lang in language_prompts:
                    lang_prompt = language_prompts[new_lang]
                    system = f"{system}\n\n{lang_prompt}" if system else lang_prompt
                    console.print(f"[yellow]Language set to {new_lang}[/yellow]")
                continue

            # Get response
            response = client.chat(
                message=user_input,
                system_prompt=system,
                history=[{"role": msg["role"], "content": msg["content"]}
                        for msg in history],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream
            )

            if not stream:
                console.print(f"\n[bold cyan]Assistant:[/bold cyan] {response}")

            # Update history
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})

            # Keep history reasonable size
            if len(history) > 20:
                history = history[-20:]

        except KeyboardInterrupt:
            console.print("\n[yellow]Use 'exit' to quit[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.pass_context
def test(ctx):
    """Test connection to Apertus"""
    client = ctx.obj['client']

    console.print("[cyan]Testing Apertus connection...[/cyan]")

    # Test in multiple languages
    tests = [
        ("Hello! Please respond with 'Connection successful'.", "English"),
        ("Bonjour! Répondez avec 'Connexion réussie' s'il vous plaît.", "Français"),
        ("Hallo! Bitte antworten Sie mit 'Verbindung erfolgreich'.", "Deutsch"),
        ("Ciao! Rispondi con 'Connessione riuscita' per favore.", "Italiano"),
    ]

    for prompt, lang in tests:
        console.print(f"\n[cyan]Testing {lang}:[/cyan]")
        try:
            response = client.chat(prompt, max_tokens=50, temperature=0.3)
            console.print(f"[green]✓[/green] {response[:100]}")
        except Exception as e:
            console.print(f"[red]✗[/red] Failed: {str(e)}")


@cli.command()
@click.pass_context
def legal(ctx):
    """Start legal assistant mode with Swiss law context"""
    client = ctx.obj['client']

    system_prompt = """You are a Swiss legal assistant powered by Apertus AI.
You have knowledge of Swiss law including the Code of Obligations (OR/CO),
Civil Code (ZGB/CC), Criminal Code (StGB/CP), and Federal Constitution.

When answering legal questions:
1. Cite specific articles when relevant
2. Consider federal and cantonal differences
3. Provide answers in the user's language (German, French, Italian, or English)
4. Always remind users that this is AI assistance, not legal advice

Be helpful, accurate, and thorough in your responses."""

    console.print(Panel.fit(
        "[bold cyan]Swiss Legal Assistant (LAWAST)[/bold cyan]\n"
        "Powered by Apertus-8B-Instruct\n\n"
        "Ask questions about Swiss law in any language.\n"
        "Type 'exit' to quit.",
        border_style="cyan"
    ))

    history = []

    while True:
        try:
            question = console.input("\n[bold green]Legal Question:[/bold green] ")

            if question.lower() == 'exit':
                break

            with console.status("[bold yellow]Analyzing your legal question...[/bold yellow]"):
                response = client.chat(
                    message=question,
                    system_prompt=system_prompt,
                    history=history,
                    max_tokens=800,
                    temperature=0.5,  # Lower temperature for more factual responses
                )

            console.print(Panel(
                Markdown(response),
                title="[bold cyan]Legal Analysis[/bold cyan]",
                border_style="cyan"
            ))

            # Add disclaimer
            console.print(
                "[dim italic]Note: This is AI-generated information, not legal advice. "
                "Consult a qualified Swiss lawyer for legal matters.[/dim italic]"
            )

            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": response})

        except KeyboardInterrupt:
            console.print("\n[yellow]Use 'exit' to quit[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    cli()