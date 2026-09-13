"""Build the checked-in synthetic forensic estate without external services."""
from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / 'data' / 'forensic-demo.sql'
OUTPUT = ROOT / 'data' / 'forensic-demo.db'


def main() -> None:
    if OUTPUT.exists():
        OUTPUT.unlink()
    conn = sqlite3.connect(OUTPUT)
    try:
        conn.executescript(SQL.read_text(encoding='utf-8'))
    finally:
        conn.close()
    print(OUTPUT)


if __name__ == '__main__':
    main()
