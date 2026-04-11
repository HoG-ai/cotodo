"""cotodo CLI — entry point and argument routing."""

import json
import os
import sys

USAGE = """\
cotodo — Collaborative TODO protocol for human-AI async workflows

Usage:
    cotodo <command> [options]

Commands:
    cotodo init [FILE]  Create a TODO.md template (and add to .gitignore)
                        --no-gitignore  Skip .gitignore update

    cotodo scan [FILE] [--all]
                        Parse TODO.md and output state (JSON)
                        Default: auto-init + clean @delete + mark [processing]
                        --all     Return all topics (read-only, for debugging)

    cotodo reply <id>   Write a reply to a topic by ID (reads JSON from stdin)
                        stdin: {"context": "...", "summary": "...", "pending": true, "compress": true}

    cotodo --version    Show version
"""


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        sys.exit(0)

    cmd = args[0]

    if cmd == "--version":
        from . import __version__
        print(f"cotodo {__version__}")

    elif cmd == "init":
        rest = args[1:]
        no_gitignore = "--no-gitignore" in rest
        positional = [a for a in rest if not a.startswith("--")]
        filepath = positional[0] if positional else "TODO.md"

        from .parser import init
        result = init(filepath, gitignore=not no_gitignore)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result.get("ok"):
            sys.exit(1)

    elif cmd == "scan":
        rest = args[1:]
        all_topics = "--all" in rest
        positional = [a for a in rest if not a.startswith("--")]
        filepath = positional[0] if positional else "TODO.md"

        # Auto-init if file doesn't exist
        if not all_topics and not os.path.exists(filepath):
            from .parser import init
            init(filepath)

        from .parser import scan
        if all_topics:
            # --all: read-only mode for debugging
            result = scan(filepath, clean=False, all_topics=True, take=False)
        else:
            # Default: clean + take
            result = scan(filepath, clean=True, all_topics=False, take=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "reply":
        rest = args[1:]
        positional = [a for a in rest if not a.startswith("--")]
        if not positional:
            print('{"ok": false, "error": "missing topic id"}')
            sys.exit(1)
        topic_id = positional[0]
        filepath = positional[1] if len(positional) > 1 else "TODO.md"

        # Read JSON from stdin
        try:
            data = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError) as e:
            print(json.dumps({"ok": False, "error": f"invalid JSON input: {e}"}))
            sys.exit(1)

        from .parser import reply
        result = reply(
            filepath=filepath,
            topic_id=topic_id,
            context=data.get("context", data.get("message")),
            summary=data.get("summary"),
            pending=bool(data.get("pending", False)),
            compress=bool(data.get("compress", False)),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result.get("ok"):
            sys.exit(1)

    else:
        print(f"Unknown command: {cmd}")
        print("Run 'cotodo --help' for usage.")
        sys.exit(1)
