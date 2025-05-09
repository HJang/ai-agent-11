import asyncio
import json
import os
from typing import Optional, Dict, Any
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.settings: Dict[str, Any] = {}
        self.load_settings()

    def load_settings(self, settings_path: str = "mcp_settings.json"):
        """Load MCP server settings from JSON file
        
        Args:
            settings_path: Path to the settings JSON file
        """
        try:
            with open(settings_path, 'r') as f:
                self.settings = json.load(f)
            print(f"Loaded settings from {settings_path}")
        except Exception as e:
            print(f"Error loading settings: {str(e)}")
            self.settings = {"mcpServers": {}}

    def get_available_servers(self) -> list:
        """Get list of available server names from settings"""
        return list(self.settings.get("mcpServers", {}).keys())

    async def connect_to_server(self, server_name: str):
        """Connect to an MCP server using settings from config file
        
        Args:
            server_name: Name of the server in the settings file
        """
        if server_name not in self.settings.get("mcpServers", {}):
            raise ValueError(f"Server '{server_name}' not found in settings")
            
        server_config = self.settings["mcpServers"][server_name]
        
        # Extract server parameters from config
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env")
        
        if not command:
            raise ValueError(f"Missing 'command' for server '{server_name}'")
        
        # Convert env dict to proper environment variables
        env_vars = os.environ.copy()
        if env:
            env_vars.update(env)
        
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
        print(f"\nConnected to server '{server_name}' with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""
        if not self.session:
            return "Error: Not connected to any MCP server"
            
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{ 
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        # Initial Claude API call
        response = self.anthropic.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=1000,
            messages=messages,
            tools=available_tools
        )

        # Process response and handle tool calls
        tool_results = []
        final_text = []

        for content in response.content:
            if content.type == 'text':
                final_text.append(content.text)
            elif content.type == 'tool_use':
                tool_name = content.name
                tool_args = content.input
                
                # Execute tool call
                result = await self.session.call_tool(tool_name, tool_args)
                tool_results.append({"call": tool_name, "result": result})
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # Continue conversation with tool results
                if hasattr(content, 'text') and content.text:
                    messages.append({
                      "role": "assistant",
                      "content": content.text
                    })
                messages.append({
                    "role": "user", 
                    "content": result.content
                })

                # Get next response from Claude
                response = self.anthropic.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=1000,
                    messages=messages,
                )

                final_text.append(response.content[0].text)

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    client = MCPClient()
    
    # Get available servers from settings
    available_servers = client.get_available_servers()
    
    if not available_servers:
        print("Error: No MCP servers defined in mcp_settings.json")
        return
    
    # If there's only one server, use it automatically
    if len(available_servers) == 1:
        server_name = available_servers[0]
    else:
        # Let user choose which server to connect to
        print("\nAvailable MCP servers:")
        for i, name in enumerate(available_servers, 1):
            print(f"{i}. {name}")
        
        while True:
            try:
                choice = input("\nSelect server number: ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(available_servers):
                    server_name = available_servers[idx]
                    break
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a number.")
    
    try:
        await client.connect_to_server(server_name)
        await client.chat_loop()
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())
