#!/usr/bin/env python3
"""
AI Agent using Claude 3.7 Sonnet and Anthropic Python SDK
A simple CLI chat interface for interacting with Claude.
Supports MCP (Model Context Protocol) servers for extended functionality.
"""

import os
import sys
import json
import asyncio
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# MCP imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Initialize Rich console for better formatting
console = Console()

class MCPClient:
    """MCP Client for handling Model Context Protocol server interactions."""
    
    def __init__(self):
        """Initialize the MCP client."""
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.settings: Dict[str, Any] = {}
        self.connected_server: Optional[str] = None
        self.load_settings()
    
    def load_settings(self, settings_path: str = "mcp_settings.json") -> None:
        """Load MCP server settings from JSON file."""
        try:
            with open(settings_path, 'r') as f:
                self.settings = json.load(f)
            console.print(f"[bold green]Loaded MCP settings from {settings_path}[/bold green]")
        except Exception as e:
            console.print(f"[bold yellow]Warning:[/bold yellow] Error loading MCP settings: {str(e)}")
            self.settings = {"mcpServers": {}}
    
    def get_available_servers(self) -> List[str]:
        """Get list of available server names from settings."""
        return list(self.settings.get("mcpServers", {}).keys())
    
    async def connect_to_server(self, server_name: str) -> bool:
        """Connect to an MCP server using settings from config file."""
        if server_name not in self.settings.get("mcpServers", {}):
            console.print(f"[bold red]Error:[/bold red] Server '{server_name}' not found in settings")
            return False
            
        server_config = self.settings["mcpServers"][server_name]
        
        # Extract server parameters from config
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env")
        
        if not command:
            console.print(f"[bold red]Error:[/bold red] Missing 'command' for server '{server_name}'")
            return False
        
        # Convert env dict to proper environment variables
        env_vars = os.environ.copy()
        if env:
            env_vars.update(env)
        
        try:
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env_vars
            )
            
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
            
            await self.session.initialize()
            
            # List available tools
            response = await self.session.list_tools()
            tools = response.tools
            console.print(f"\n[bold green]Connected to MCP server '{server_name}'[/bold green]")
            console.print(f"[bold green]Available tools:[/bold green] {', '.join([tool.name for tool in tools])}")
            
            self.connected_server = server_name
            return True
            
        except Exception as e:
            console.print(f"[bold red]Error connecting to MCP server:[/bold red] {str(e)}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the current MCP server."""
        if self.session:
            await self.exit_stack.aclose()
            self.session = None
            self.connected_server = None
            console.print("[bold green]Disconnected from MCP server[/bold green]")
    
    async def process_query(self, query: str, message_history: List[Dict[str, Any]], client: anthropic.Anthropic) -> Dict[str, Any]:
        """Process a query using Claude and available MCP tools."""
        if not self.session:
            return {"text": "Error: Not connected to any MCP server. Use /connect <server> to connect.", "tool_calls": []}
        
        try:
            # Get available tools from the MCP server
            response = await self.session.list_tools()
            available_tools = [{ 
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            } for tool in response.tools]
            
            # Create messages for Claude API
            messages = message_history.copy()
            
            # Call Claude with tools
            claude_response = client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=4000,
                messages=messages,
                tools=available_tools
            )
            
            # Process response and handle tool calls
            tool_calls = []
            final_text = ""
            
            for content in claude_response.content:
                if content.type == 'text':
                    final_text = content.text
                elif content.type == 'tool_use':
                    tool_name = content.name
                    tool_args = content.input
                    
                    # Execute tool call
                    console.print(f"[bold blue]Calling MCP tool:[/bold blue] {tool_name}")
                    result = await self.session.call_tool(tool_name, tool_args)
                    tool_result = result.content
                    
                    tool_calls.append({
                        "name": tool_name,
                        "args": tool_args,
                        "result": tool_result
                    })
                    
                    # Add tool call and result to message history for context
                    messages.append({"role": "assistant", "content": f"I'll use the {tool_name} tool."})
                    messages.append({"role": "user", "content": f"Tool result: {tool_result}"})
                    
                    # Get follow-up response from Claude
                    follow_up = client.messages.create(
                        model="claude-3-7-sonnet-20250219",
                        max_tokens=4000,
                        messages=messages
                    )
                    
                    final_text = follow_up.content[0].text
            
            return {"text": final_text, "tool_calls": tool_calls}
            
        except Exception as e:
            console.print(f"[bold red]Error processing MCP query:[/bold red] {str(e)}")
            return {"text": f"Error processing query: {str(e)}", "tool_calls": []}

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

def handle_commands(command: str, mcp_client: Optional[MCPClient] = None) -> Dict[str, Any]:
    """Handle special commands.
    
    Returns:
        Dict with keys:
        - exit: True if the application should exit
        - handled: True if the command was handled
        - mcp_command: True if it was an MCP-related command
    """
    result = {"exit": False, "handled": False, "mcp_command": False}
    
    if command.lower() in ["/exit", "/quit", "exit", "quit"]:
        console.print("\n[bold yellow]Exiting AI Agent. Goodbye![/bold yellow]")
        result["exit"] = True
        result["handled"] = True
    elif command.lower() in ["/help", "help"]:
        show_help()
        result["handled"] = True
    elif command.lower().startswith("/servers") and mcp_client:
        servers = mcp_client.get_available_servers()
        if servers:
            console.print("\n[bold blue]Available MCP Servers:[/bold blue]")
            for i, server in enumerate(servers, 1):
                console.print(f"  {i}. {server}")
        else:
            console.print("\n[bold yellow]No MCP servers configured in mcp_settings.json[/bold yellow]")
        result["handled"] = True
        result["mcp_command"] = True
    elif command.lower().startswith("/connect ") and mcp_client:
        server_name = command[9:].strip()
        result["server_name"] = server_name
        result["handled"] = True
        result["mcp_command"] = True
        result["connect"] = True
    elif command.lower() == "/disconnect" and mcp_client:
        result["handled"] = True
        result["mcp_command"] = True
        result["disconnect"] = True
    
    return result

def show_help() -> None:
    """Display help information."""
    help_text = """
    # AI Agent Help
    
    ## Basic Commands:
    - `/help` - Show this help message
    - `/exit` or `/quit` - Exit the application
    
    ## MCP Commands:
    - `/servers` - List available MCP servers
    - `/connect <server>` - Connect to an MCP server
    - `/disconnect` - Disconnect from the current MCP server
    
    ## Usage:
    Type your message and press Enter to send it to Claude.
    When connected to an MCP server, Claude can use the server's tools.
    """
    console.print(Markdown(help_text))

def format_messages(history: List[Dict[str, Any]], new_message: str) -> List[Dict[str, Any]]:
    """Format the message history for the API call."""
    history.append({"role": "user", "content": new_message})
    return history

async def run_mcp_command(command_result: Dict[str, Any], mcp_client: MCPClient) -> None:
    """Run an MCP command based on the command result."""
    if command_result.get("connect"):
        server_name = command_result.get("server_name", "")
        console.print(f"\n[bold blue]Connecting to MCP server:[/bold blue] {server_name}")
        success = await mcp_client.connect_to_server(server_name)
        if not success:
            console.print(f"[bold red]Failed to connect to server:[/bold red] {server_name}")
    elif command_result.get("disconnect"):
        if mcp_client.connected_server:
            console.print(f"\n[bold blue]Disconnecting from MCP server:[/bold blue] {mcp_client.connected_server}")
            await mcp_client.disconnect()
        else:
            console.print("\n[bold yellow]Not connected to any MCP server[/bold yellow]")

async def main_async() -> None:
    """Async main function to run the AI agent."""
    # Display welcome message
    welcome_message = """
    # Claude 3.7 Sonnet AI Agent with MCP Support
    
    Welcome to the Claude AI Agent! Type your message and press Enter to chat with Claude.
    Type `/help` for available commands or `/exit` to quit.
    
    MCP support is enabled. Use `/servers` to list available MCP servers and
    `/connect <server>` to connect to a server.
    """
    console.print(Markdown(welcome_message))
    
    # Load API key and initialize client
    api_key = load_api_key()
    client = initialize_client(api_key)
    
    # Initialize MCP client
    mcp_client = MCPClient()
    
    # Initialize message history
    message_history = []
    
    # System prompt
    system_prompt = "You are Claude, an AI assistant by Anthropic. You are helpful, harmless, and honest."
    
    # Main interaction loop
    while True:
        # Get user input
        user_message = get_user_input()
        
        # Check for commands
        command_result = handle_commands(user_message, mcp_client)
        
        if command_result["exit"]:
            # Clean up MCP resources before exiting
            if mcp_client.session:
                await mcp_client.disconnect()
            break
            
        if command_result["handled"]:
            if command_result["mcp_command"]:
                await run_mcp_command(command_result, mcp_client)
            continue
        
        try:
            # Update message history
            message_history = format_messages(message_history, user_message)
            
            # Process with MCP if connected, otherwise use standard Claude
            if mcp_client.session:
                console.print(f"\n[bold blue]Using MCP server:[/bold blue] {mcp_client.connected_server}")
                with console.status("[bold blue]Claude is thinking with MCP tools...[/bold blue]"):
                    result = await mcp_client.process_query(user_message, message_history, client)
                
                # Extract and display the response
                assistant_message = result["text"]
                
                # Add tool calls info if any
                tool_calls = result["tool_calls"]
                if tool_calls:
                    tool_info = "\n\n[Tool calls used: " + ", ".join([call["name"] for call in tool_calls]) + "]"
                    assistant_message += tool_info
                
                message_history.append({"role": "assistant", "content": assistant_message})
                
                console.print("\n[bold purple]Claude (with MCP):[/bold purple]")
                console.print(Markdown(assistant_message))
            else:
                # Standard Claude response without MCP
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

def main() -> None:
    """Main function to run the AI agent."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Keyboard interrupt detected. Exiting...[/bold yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Unhandled error:[/bold red] {str(e)}")

if __name__ == "__main__":
    main()
