#!/usr/bin/env python3
"""
LAWAST Apertus Client
Basic script to interact with Apertus model via HuggingFace endpoint
"""

import os
import json
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from huggingface_hub import InferenceClient
import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Initialize console for rich output
console = Console()

# Configuration
ENDPOINT_URL = "https://grg8pdp0ndex8j6a.us-east-1.aws.endpoints.huggingface.cloud"
DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.7


@dataclass
class ApertusResponse:
    """Structure for model response"""
    text: str
    tokens_generated: int
    time_taken: float
    parameters: Dict[str, Any]


class ApertusClient:
    """Client for interacting with Apertus model"""

    def __init__(self, endpoint_url: str = ENDPOINT_URL, api_key: Optional[str] = None):
        """
        Initialize Apertus client

        Args:
            endpoint_url: HuggingFace endpoint URL
            api_key: Optional HuggingFace API key
        """
        self.endpoint_url = endpoint_url

        # Use API key from environment or parameter
        api_key = api_key or os.getenv("HUGGINGFACE_API_KEY")

        # Initialize the client
        self.client = InferenceClient(
            model=endpoint_url,
            token=api_key
        )

        console.print(f"[green]✓[/green] Connected to Apertus endpoint")

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = 0.95,
        top_k: int = 50,
        do_sample: bool = True,
        repetition_penalty: float = 1.1,
        stop_sequences: Optional[list] = None,
        stream: bool = False
    ) -> ApertusResponse:
        """
        Generate text using Apertus model

        Args:
            prompt: Input prompt
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            do_sample: Whether to use sampling
            repetition_penalty: Penalty for repetition
            stop_sequences: List of sequences to stop generation
            stream: Whether to stream the response

        Returns:
            ApertusResponse object
        """
        start_time = time.time()

        try:
            if stream:
                # Streaming generation
                return self._stream_generation(
                    prompt=prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    do_sample=do_sample,
                    repetition_penalty=repetition_penalty,
                    stop_sequences=stop_sequences
                )
            else:
                # Standard generation
                response = self.client.text_generation(
                    prompt=prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    do_sample=do_sample,
                    repetition_penalty=repetition_penalty,
                    stop_sequences=stop_sequences,
                    return_full_text=False
                )

                time_taken = time.time() - start_time

                return ApertusResponse(
                    text=response,
                    tokens_generated=len(response.split()),  # Approximate
                    time_taken=time_taken,
                    parameters={
                        "max_new_tokens": max_new_tokens,
                        "temperature": temperature,
                        "top_p": top_p,
                        "top_k": top_k,
                        "do_sample": do_sample,
                        "repetition_penalty": repetition_penalty
                    }
                )

        except Exception as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            raise

    def _stream_generation(self, **kwargs) -> ApertusResponse:
        """Stream generation with live output"""
        start_time = time.time()
        full_response = ""

        console.print("\n[cyan]Assistant:[/cyan]")

        # Stream the response
        for token in self.client.text_generation(**kwargs, stream=True):
            console.print(token, end="")
            full_response += token

        console.print("\n")
        time_taken = time.time() - start_time

        return ApertusResponse(
            text=full_response,
            tokens_generated=len(full_response.split()),
            time_taken=time_taken,
            parameters=kwargs
        )

    def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history: Optional[list] = None,
        **generation_kwargs
    ) -> str:
        """
        Chat-style interaction with proper formatting

        Args:
            message: User message
            system_prompt: Optional system prompt
            history: Optional conversation history
            **generation_kwargs: Additional generation parameters

        Returns:
            Model response
        """
        # Build the prompt
        prompt = self._build_chat_prompt(message, system_prompt, history)

        # Generate response
        response = self.generate(prompt, **generation_kwargs)

        return response.text

    def _build_chat_prompt(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history: Optional[list] = None
    ) -> str:
        """Build formatted chat prompt"""
        prompt_parts = []

        # Add system prompt if provided
        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}\n")

        # Add conversation history
        if history:
            for turn in history:
                if turn.get("user"):
                    prompt_parts.append(f"User: {turn['user']}")
                if turn.get("assistant"):
                    prompt_parts.append(f"Assistant: {turn['assistant']}")

        # Add current message
        prompt_parts.append(f"User: {message}")
        prompt_parts.append("Assistant:")

        return "\n".join(prompt_parts)


# CLI Interface
@click.group()
@click.option('--endpoint', default=ENDPOINT_URL, help='HuggingFace endpoint URL')
@click.option('--api-key', envvar='HUGGINGFACE_API_KEY', help='HuggingFace API key')
@click.pass_context
def cli(ctx, endpoint, api_key):
    """Apertus CLI - Interact with Apertus language model"""
    ctx.ensure_object(dict)
    ctx.obj['client'] = ApertusClient(endpoint, api_key)


@cli.command()
@click.argument('prompt')
@click.option('--max-tokens', '-m', default=DEFAULT_MAX_TOKENS, help='Maximum tokens to generate')
@click.option('--temperature', '-t', default=DEFAULT_TEMPERATURE, help='Sampling temperature')
@click.option('--top-p', default=0.95, help='Nucleus sampling parameter')
@click.option('--top-k', default=50, help='Top-k sampling parameter')
@click.option('--stream', '-s', is_flag=True, help='Stream the response')
@click.option('--json-output', is_flag=True, help='Output as JSON')
@click.pass_context
def generate(ctx, prompt, max_tokens, temperature, top_p, top_k, stream, json_output):
    """Generate text from a prompt"""
    client = ctx.obj['client']

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        if not stream:
            progress.add_task(description="Generating response...", total=None)

        response = client.generate(
            prompt=prompt,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            stream=stream
        )

    if json_output:
        output = {
            "prompt": prompt,
            "response": response.text,
            "tokens_generated": response.tokens_generated,
            "time_taken": response.time_taken,
            "parameters": response.parameters
        }
        console.print_json(json.dumps(output))
    else:
        if not stream:  # Stream already prints during generation
            console.print(Panel(
                Markdown(response.text),
                title="[bold cyan]Apertus Response[/bold cyan]",
                subtitle=f"[dim]{response.tokens_generated} tokens in {response.time_taken:.2f}s[/dim]"
            ))


@cli.command()
@click.option('--system', '-s', help='System prompt')
@click.option('--max-tokens', '-m', default=DEFAULT_MAX_TOKENS, help='Maximum tokens')
@click.option('--temperature', '-t', default=DEFAULT_TEMPERATURE, help='Temperature')
@click.option('--stream', is_flag=True, help='Stream responses')
@click.pass_context
def chat(ctx, system, max_tokens, temperature, stream):
    """Interactive chat mode"""
    client = ctx.obj['client']
    history = []

    console.print(Panel.fit(
        "[bold cyan]Apertus Chat Interface[/bold cyan]\n"
        "Type 'exit' to quit, 'clear' to reset history, 'help' for commands",
        border_style="cyan"
    ))

    if system:
        console.print(f"[dim]System prompt: {system}[/dim]\n")

    while True:
        try:
            # Get user input
            user_input = console.input("\n[bold green]You:[/bold green] ")

            # Handle commands
            if user_input.lower() == 'exit':
                console.print("[yellow]Goodbye![/yellow]")
                break
            elif user_input.lower() == 'clear':
                history = []
                console.print("[yellow]History cleared[/yellow]")
                continue
            elif user_input.lower() == 'help':
                console.print(
                    "[cyan]Commands:[/cyan]\n"
                    "  exit  - Quit the chat\n"
                    "  clear - Clear conversation history\n"
                    "  help  - Show this help message"
                )
                continue

            # Generate response
            response = client.chat(
                message=user_input,
                system_prompt=system,
                history=history,
                max_new_tokens=max_tokens,
                temperature=temperature,
                stream=stream
            )

            if not stream:
                console.print(f"\n[bold cyan]Assistant:[/bold cyan] {response}")

            # Update history
            history.append({
                "user": user_input,
                "assistant": response
            })

        except KeyboardInterrupt:
            console.print("\n[yellow]Use 'exit' to quit[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument('input_file', type=click.File('r'))
@click.argument('output_file', type=click.File('w'))
@click.option('--max-tokens', '-m', default=DEFAULT_MAX_TOKENS)
@click.option('--temperature', '-t', default=DEFAULT_TEMPERATURE)
@click.pass_context
def batch(ctx, input_file, output_file, max_tokens, temperature):
    """Process batch of prompts from file"""
    client = ctx.obj['client']

    # Read prompts (one per line or JSON)
    content = input_file.read()

    try:
        # Try JSON format
        prompts = json.loads(content)
        if isinstance(prompts, str):
            prompts = [prompts]
    except json.JSONDecodeError:
        # Treat as line-separated prompts
        prompts = [line.strip() for line in content.strip().split('\n') if line.strip()]

    results = []

    with Progress() as progress:
        task = progress.add_task("[cyan]Processing prompts...", total=len(prompts))

        for prompt in prompts:
            response = client.generate(
                prompt=prompt,
                max_new_tokens=max_tokens,
                temperature=temperature
            )

            results.append({
                "prompt": prompt,
                "response": response.text,
                "tokens": response.tokens_generated,
                "time": response.time_taken
            })

            progress.update(task, advance=1)

    # Write results
    json.dump(results, output_file, indent=2)
    console.print(f"[green]✓[/green] Processed {len(prompts)} prompts")


@cli.command()
@click.pass_context
def test(ctx):
    """Test connection to endpoint"""
    client = ctx.obj['client']

    console.print("[cyan]Testing Apertus endpoint...[/cyan]")

    test_prompt = "Hello! Please respond with 'Connection successful' if you can read this."

    try:
        response = client.generate(
            prompt=test_prompt,
            max_new_tokens=20,
            temperature=0.1
        )

        console.print(Panel(
            f"[green]✓ Connection successful![/green]\n\n"
            f"Response: {response.text}\n"
            f"Time: {response.time_taken:.2f}s",
            title="[bold green]Test Passed[/bold green]",
            border_style="green"
        ))

    except Exception as e:
        console.print(Panel(
            f"[red]✗ Connection failed![/red]\n\n"
            f"Error: {str(e)}",
            title="[bold red]Test Failed[/bold red]",
            border_style="red"
        ))
        raise


if __name__ == "__main__":
    cli()