# src/viewer/cli.py
"""CLI entry point for Claude Codex Viewer"""
import argparse
import os
import sys
import uvicorn


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="claude-codex-viewer",
        description="Web viewer for Claude Code and Codex CLI conversation history"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=6300,
        help="Port to run the server on (default: 6300)"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--claude-path",
        type=str,
        default=None,
        help="Path to Claude projects directory (default: ~/.claude/projects)"
    )

    parser.add_argument(
        "--codex-path",
        type=str,
        default=None,
        help="Path to Codex sessions directory (default: ~/.codex/sessions)"
    )

    args = parser.parse_args()

    # Set environment variables for parsers
    if args.claude_path:
        os.environ["CLAUDE_PROJECTS_PATH"] = args.claude_path

    if args.codex_path:
        os.environ["CODEX_SESSIONS_PATH"] = args.codex_path

    # Run uvicorn
    print(f"Starting Claude Codex Viewer on http://{args.host}:{args.port}")
    uvicorn.run(
        "viewer.main:app",
        host=args.host,
        port=args.port,
        reload=False
    )


if __name__ == "__main__":
    main()