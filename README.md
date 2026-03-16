# History AI Chat

Web application for viewing conversation history from Claude Code and OpenAI Codex CLI.

## Features

- Multi-platform support (Claude Code + Codex CLI)
- Global search across all conversations
- Beautiful chat-style UI with dark/light themes
- Export to Markdown, HTML, or JSON
- Thinking blocks visualization
- Tool use formatting

## Quick Start (Windows)

```cmd
run.bat
```

This will:
1. Create virtual environment if needed
2. Install dependencies
3. Start the server on http://localhost:6300
4. Open browser automatically

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Start with defaults
history-ai-chat

# Custom port
history-ai-chat --port 8080

# Custom paths
history-ai-chat --claude-path /path/to/.claude/projects --codex-path /path/to/.codex/sessions
```

Open http://localhost:6300 in your browser.

## Data Locations

| Platform | Default Path |
|----------|--------------|
| Claude Code | `~/.claude/projects/` |
| Codex CLI | `~/.codex/sessions/` |

## Development

```bash
pip install -e ".[dev]"
pytest tests/
```

## License

MIT