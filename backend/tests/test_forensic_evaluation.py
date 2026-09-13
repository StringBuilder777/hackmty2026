import ast
import csv
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from evaluation.benchmark import (
    HELD_OUT_SCENARIOS,
    HELD_OUT_SEEDS,
    TUNING_SEEDS,
    SchemeLabel,
    create_held_out_estate,
    expected_decoys,
    expected_schemes,
)
from evaluation.run_benchmark import FIELDNAMES, match_one_to_one, run_benchmark


def test_held_out_matrix_varies_scheme_and_decoy_counts():
    assert set(TUNING_SEEDS).isdisjoint(HELD_OUT_SEEDS)
    assert [len(expected_schemes(seed)) for seed in HELD_OUT_SEEDS] == [0, 1, 3, 4, 5]
    assert [len(expected_decoys(seed)) for seed in HELD_OUT_SEEDS] == [0, 2, 4, 6, 10]
    assert HELD_OUT_SCENARIOS[HELD_OUT_SEEDS[0]].schemes == ()
    assert HELD_OUT_SCENARIOS[HELD_OUT_SEEDS[-1]].entangle_kickback is True


def test_boundary_and_adversarial_decoys_are_physically_planted(tmp_path):
    seed = HELD_OUT_SEEDS[-1]
    estate = tmp_path / 'boundaries.db'
    create_held_out_estate(estate, seed)
    conn = sqlite3.connect(estate)
    try:
        split = conn.execute(
            "SELECT issue_date, total FROM invoices WHERE issuer_rfc=? ORDER BY issue_date",
            (f'SPLIT{seed}',),
        ).fetchall()
        reversal = conn.execute(
            "SELECT debit, credit FROM ledger WHERE invoice_uuid=? ORDER BY entry_id",
            (f'REVSAFE-{seed}',),
        ).fetchall()
        boundary_cycle = conn.execute(
            "SELECT date, amount FROM bank_txns WHERE txn_id LIKE ? ORDER BY txn_id",
            (f'ROUND-{seed}-%',),
        ).fetchall()
        amount_decoy = conn.execute(
            "SELECT amount FROM bank_txns WHERE txn_id LIKE ? ORDER BY txn_id",
            (f'VAR-{seed}-%',),
        ).fetchall()
        non_chronological = conn.execute(
            "SELECT date FROM bank_txns WHERE txn_id LIKE ? ORDER BY txn_id",
            (f'ORDER-{seed}-%',),
        ).fetchall()
    finally:
        conn.close()
    assert split == [('2026-03-01', 45_000.0), ('2026-03-07', 45_000.0), ('2026-03-15', 45_000.0)]
    assert sum(row[1] - row[0] for row in reversal) == 0
    assert boundary_cycle[2][0] == '2026-02-15'
    assert (max(row[1] for row in boundary_cycle) - min(row[1] for row in boundary_cycle)) / max(row[1] for row in boundary_cycle) == 0.02
    assert (max(row[0] for row in amount_decoy) - min(row[0] for row in amount_decoy)) / max(row[0] for row in amount_decoy) > 0.02
    assert [row[0] for row in non_chronological] == ['2026-10-10', '2026-10-05', '2026-10-12']


def test_one_to_one_matching_does_not_hide_duplicate_predictions():
    label = SchemeLabel('S1', 'phantom_vendor', ('RFC:ONE',), 100.0)
    first = SimpleNamespace(scheme_type='phantom_vendor', entities=['RFC:ONE'])
    duplicate = SimpleNamespace(scheme_type='phantom_vendor', entities=['RFC:ONE'])
    matched = match_one_to_one((first, duplicate), (label,))
    assert len(matched.matches) == 1
    assert matched.unmatched_predictions == (duplicate,)
    assert matched.unmatched_labels == ()


def test_results_csv_uses_exact_official_columns_and_total(tmp_path):
    output = tmp_path / 'results.csv'
    rows = run_benchmark(output)
    with output.open(newline='', encoding='utf-8') as handle:
        parsed = list(csv.DictReader(handle))
        assert handle.closed is False
    assert list(parsed[0]) == FIELDNAMES
    assert len(parsed) == len(HELD_OUT_SEEDS) + 1
    assert parsed[-1]['seed'] == 'TOTAL'
    assert parsed[-1]['schemes_planted'] == str(sum(len(expected_schemes(seed)) for seed in HELD_OUT_SEEDS))
    assert parsed[-1]['decoys_planted'] == str(sum(len(expected_decoys(seed)) for seed in HELD_OUT_SEEDS))
    assert all(row['peso_reconciles'] == 'YES' for row in parsed)
    assert rows[-1]['seed'] == 'TOTAL'


def test_production_package_never_imports_evaluation_labels():
    app_root = Path(__file__).resolve().parents[1] / 'app'
    for source in app_root.rglob('*.py'):
        tree = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        assert not any(name == 'evaluation' or name.startswith('evaluation.') for name in imported), source
