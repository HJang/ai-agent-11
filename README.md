# Claude 3.7 Sonnet AI Agent

A simple CLI-based AI agent that uses Claude 3.7 Sonnet via the Anthropic Python SDK.

## Features

- Simple Q&A functionality with Claude 3.7 Sonnet
- CLI-based chat interface
- Conversation history tracking
- Markdown rendering of responses
- Basic command handling (`/help`, `/exit`)

## Prerequisites

- Python 3.7 or higher
- Anthropic API key

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd ai-agent-11
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your environment variables:
   - Copy `.env.example` to `.env`
   - Add your Anthropic API key to the `.env` file

## Usage

Run the agent:

```
python agent.py
```

### Commands

- `/help` - Display help information
- `/exit` or `/quit` - Exit the application

## Project Structure

- `agent.py` - Main application file
- `requirements.txt` - Project dependencies
- `.env` - Environment variables (for API key)
- `.env.example` - Example environment file
- `.gitignore` - Git ignore file

## License

This project is open source and available under the [MIT License](LICENSE).
