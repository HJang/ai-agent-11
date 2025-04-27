#!/usr/bin/env python3
"""
AI Agent using Claude 3.7 Sonnet and Anthropic Python SDK
A simple CLI chat interface for interacting with Claude.
"""

import os
import sys
from typing import List, Dict, Any
import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

# Initialize Rich console for better formatting
console = Console()

def load_api_key() -> str:
    """Load the Anthropic API key from environment variables."""
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        console.print("[bold red]Error:[/bold red] ANTHROPIC_API_KEY not found in environment variables.")
        console.print("Please add your API key to the .env file.")
        sys.exit(1)
    
    return api_key

def initialize_client(api_key: str) -> anthropic.Anthropic:
    """Initialize the Anthropic client with the API key."""
    return anthropic.Anthropic(api_key=api_key)

def get_user_input() -> str:
    """Get input from the user."""
    console.print("\n[bold green]You:[/bold green] ", end="")
    return input()

def handle_commands(command: str) -> bool:
    """Handle special commands."""
    if command.lower() in ["/exit", "/quit", "exit", "quit"]:
        console.print("\n[bold yellow]Exiting AI Agent. Goodbye![/bold yellow]")
        return True
    elif command.lower() in ["/help", "help"]:
        show_help()
        return False
    return False

def show_help() -> None:
    """Display help information."""
    help_text = """
    # AI Agent Help
    
    ## Available Commands:
    - `/help` - Show this help message
    - `/exit` or `/quit` - Exit the application
    
    ## Usage:
    Type your message and press Enter to send it to Claude.
    """
    console.print(Markdown(help_text))

def format_messages(history: List[Dict[str, Any]], new_message: str) -> List[Dict[str, Any]]:
    """Format the message history for the API call."""
    history.append({"role": "user", "content": new_message})
    return history

def main() -> None:
    """Main function to run the AI agent."""
    # Display welcome message
    welcome_message = """
    # Claude 3.7 Sonnet AI Agent
    
    Welcome to the Claude AI Agent! Type your message and press Enter to chat with Claude.
    Type `/help` for available commands or `/exit` to quit.
    """
    console.print(Markdown(welcome_message))
    
    # Load API key and initialize client
    api_key = load_api_key()
    client = initialize_client(api_key)
    
    # Initialize message history
    message_history = []
    
    # System prompt
    system_prompt = "You are Claude, an AI assistant by Anthropic. You are helpful, harmless, and honest."
    
    # Main interaction loop
    while True:
        # Get user input
        user_message = get_user_input()
        
        # Check for commands
        if handle_commands(user_message):
            break
        
        try:
            # Update message history
            message_history = format_messages(message_history, user_message)
            
            # Get response from Claude
            with console.status("[bold blue]Claude is thinking...[/bold blue]"):
                response = client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=4096,
                    system=system_prompt,
                    messages=message_history
                )
            
            # Extract and display the response
            assistant_message = response.content[0].text
            message_history.append({"role": "assistant", "content": assistant_message})
            
            console.print("\n[bold purple]Claude:[/bold purple]")
            console.print(Markdown(assistant_message))
            
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {str(e)}")

if __name__ == "__main__":
    main()
