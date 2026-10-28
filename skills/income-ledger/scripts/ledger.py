#!/usr/bin/env python3
"""Thin entry point for the shared ledger in lib/ledger.py (same commands; run with --help)."""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import ledger  # noqa: E402

if __name__ == "__main__":
    ledger.main()
