"""CLI entry for the local editor host."""

from __future__ import annotations

import argparse
from pathlib import Path

from apps.editor.host import bind_existing_workspace


def main() -> int:
    parser = argparse.ArgumentParser(description="Movie Muse local screenplay editor")
    parser.add_argument("--workspace", required=True, help="Local workspace directory")
    parser.add_argument("--actor-id", required=True, help="Authorized actor id")
    parser.add_argument("command", choices=("outline", "history", "recover", "accessibility"))
    args = parser.parse_args()
    session = bind_existing_workspace(Path(args.workspace), actor_id=args.actor_id)
    if args.command == "outline":
        for entry in session.outline():
            print(f"{entry.scene_number}\t{entry.heading}")
        return 0
    if args.command == "history":
        print(session.history_text())
        return 0
    if args.command == "recover":
        print(session.recover())
        return 0
    contract = session.accessibility()
    print(contract.label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
