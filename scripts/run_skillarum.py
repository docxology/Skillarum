#!/usr/bin/env python3
"""Thin project-script wrapper around ``python -m skillarum``."""

from __future__ import annotations

import sys

from skillarum.cli import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
