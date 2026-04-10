"""cotodo CLI — entry point and argument routing.

Commands will be implemented incrementally, migrating from SKILL.md rules.
"""

import sys

USAGE = """\
cotodo — Collaborative TODO protocol for human-AI async workflows

Usage:
    cotodo <command> [options]

Commands: (to be implemented)
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
    else:
        print(f"Command '{cmd}' not yet implemented.")
        sys.exit(1)
