"""Thin entry point for fresh HTML inventory and verified archival."""

import sys

from skillarum.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["snapshot-site", *sys.argv[1:]]))
