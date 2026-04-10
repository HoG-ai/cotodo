"""cotodo CLI — entry point and argument routing.

Commands will be implemented incrementally, migrating from SKILL.md rules.
"""

import json
import sys

USAGE = """\
cotodo — Collaborative TODO protocol for human-AI async workflows

Usage:
    cotodo <command> [options]

Commands:
    cotodo scan [FILE] [--clean] [--all]
                        Parse TODO.md and output state (JSON)
                        --clean   Remove @delete topics from file
                        --all     Return all topics (default: highest priority only)
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

    elif cmd == "scan":
        rest = args[1:]
        clean = "--clean" in rest
        all_topics = "--all" in rest
        positional = [a for a in rest if not a.startswith("--")]
        filepath = positional[0] if positional else "TODO.md"

        from .parser import scan
        result = scan(filepath, clean=clean, all_topics=all_topics)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(f"Command '{cmd}' not yet implemented.")
        sys.exit(1)
