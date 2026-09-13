"""Build a portable forensic submission package from one SQLite estate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.forensic import RULESET_VERSION, inspect_forensic_estate, render_case_file, run_forensic_audit


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_output(path: Path, overwrite: bool) -> None:
    artifacts = ('submission.json', 'case_file.md', 'manifest.json', 'validator-output.txt')
    if path.exists() and not path.is_dir():
        raise ValueError('--output debe ser un directorio.')
    if path.exists() and any((path / name).exists() for name in artifacts) and not overwrite:
        raise ValueError('El directorio ya contiene artefactos. Usa --overwrite o un directorio nuevo.')
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description='Genera un paquete reproducible de auditoría forense.')
    parser.add_argument('estate', type=Path, help='Ruta a la SQLite de entrada.')
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--validator', type=Path, help='Ruta al validate_format.py entregado por el reto.')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    estate = args.estate.expanduser().resolve()
    if not estate.is_file():
        raise SystemExit('La ruta estate debe apuntar a un archivo existente.')
    try:
        prepare_output(args.output, args.overwrite)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    preflight = inspect_forensic_estate(str(estate))
    submission = run_forensic_audit(str(estate), args.seed)
    output = args.output.resolve()
    submission_path = output / 'submission.json'
    case_file_path = output / 'case_file.md'
    submission_path.write_text(submission.model_dump_json(by_alias=True, indent=2), encoding='utf-8')
    case_file_path.write_text(render_case_file(submission, str(estate)), encoding='utf-8')

    validation = {'executed': False, 'passed': None, 'command': None}
    if args.validator:
        validator = args.validator.expanduser().resolve()
        if not validator.is_file():
            raise SystemExit('--validator no apunta a un archivo existente.')
        command = [sys.executable, str(validator), '--submission', str(submission_path), '--estate', str(estate)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        (output / 'validator-output.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
        validation = {'executed': True, 'passed': result.returncode == 0, 'command': command}

    manifest = {
        'format_version': 1,
        'ruleset_version': RULESET_VERSION,
        'estate_filename': estate.name,
        'estate_sha256': sha256(estate),
        'estate_bytes': estate.stat().st_size,
        'seed': args.seed,
        'finding_count': len(submission.findings),
        'lead_count': len(submission.leads_not_pursued),
        'preflight': preflight.model_dump(),
        'run_metadata': submission.run_metadata.model_dump(),
        'official_format_validation': validation,
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(output)
    if validation['executed'] and not validation['passed']:
        raise SystemExit('El validador oficial rechazó el paquete; revisa validator-output.txt.')


if __name__ == '__main__':
    main()
