"""Export one SQLite estate as judge-shaped CSV and ZIP demo inputs."""
from __future__ import annotations

import argparse
import csv
import sqlite3
import zipfile
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.estate_ingest import TABLES


def export_inputs(database: Path, output: Path) -> None:
    if not database.is_file():
        raise ValueError('La ruta debe apuntar a una base SQLite existente.')
    output.mkdir(parents=True, exist_ok=True)
    csv_directory = output / 'csv'
    csv_directory.mkdir(exist_ok=True)
    conn = sqlite3.connect(f'file:{database.resolve()}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for table, columns in TABLES.items():
            names = [name for name, _ in columns]
            with (csv_directory / f'{table}.csv').open('w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle, lineterminator='\n')
                writer.writerow(names)
                writer.writerows([row[name] for name in names] for row in conn.execute(f'SELECT * FROM {table}'))
    finally:
        conn.close()

    with zipfile.ZipFile(output / 'forensic-demo-db.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(database, arcname='forensic-demo.db')
    with zipfile.ZipFile(output / 'forensic-demo-csv.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for csv_path in sorted(csv_directory.glob('*.csv')):
            archive.write(csv_path, arcname=csv_path.name)


def main() -> None:
    parser = argparse.ArgumentParser(description='Genera ejemplos ZIP y CSV para la carga forense.')
    parser.add_argument('database', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    export_inputs(args.database.expanduser().resolve(), args.output.expanduser().resolve())
    print(args.output.expanduser().resolve())


if __name__ == '__main__':
    main()
