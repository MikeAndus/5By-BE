from __future__ import annotations

import argparse
import sys

from app.cli import seed_grids


def main() -> int:
    parser = argparse.ArgumentParser(description="Five-By backend CLI")
    parser.add_argument("command", choices=["seed-grids"], help="Command to execute")
    args, remaining = parser.parse_known_args()

    if args.command == "seed-grids":
        sys.argv = ["seed-grids", *remaining]
        return seed_grids.main()

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
