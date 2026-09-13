"""Generate a valid submission from the synthetic forensic estate."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.forensic import run_forensic_audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--output', type=Path, default=Path('/tmp/forensic-demo-submission.json'))
    args = parser.parse_args()
    estate = ROOT / 'data' / 'forensic-demo.db'
    if not estate.exists():
        raise SystemExit('Primero ejecuta scripts/create_forensic_demo.py.')
    args.output.write_text(run_forensic_audit(str(estate), args.seed).model_dump_json(by_alias=True, indent=2), encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
