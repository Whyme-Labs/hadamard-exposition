"""Fail-closed audit of the complete v2 result, independent of study.py.

Reconstruct every reported numerical summary from raw cells. Hash checks bind
files, not authorship or execution provenance. No claim of mathematical novelty,
model performance, external peer review or award acceptance follows.
"""
from __future__ import annotations
import argparse
import csv
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import numpy as np

ARMS = ('original', 'randomized_hadamard', 'haar_orthogonal', 'signed_permutation')
OUTPUTS = {'cells.csv', 'inputs.json', 'summary.json', 'exact-checks.json'}
PROTOCOL_SHA256 = '1a239984661f3c229225aa4d899fe3960eb2f5f47dc5e7099c49764022f08c29'
REGISTRATION = '7d5e4dabccace930c0de2cc41e7da847486f95a1'
PRIMES = (3, 7, 11, 19, 23, 31, 43)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def checked_file(root: Path, name: str) -> Path:
    require(bool(re.fullmatch(r'[A-Za-z0-9_.-]+', name)) and name not in ('.', '..'), 'unsafe filename')
    path = root / name
    require(path.is_file() and not path.is_symlink(), 'missing, nonregular or symlink file: ' + name)
    require(path.stat().st_size <= 10_000_000, 'file exceeds audit bound')
    return path


def strict_json(path: Path):
    def pairs(values):
        obj = {}
        for key, value in values:
            require(key not in obj, 'duplicate JSON key')
            obj[key] = value
        return obj
    def constant(value):
        raise ValueError('nonfinite JSON number: ' + value)
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=constant)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def close(actual, expected, label: str) -> None:
    require(valid_number(actual) and valid_number(expected), 'invalid number: ' + label)
    require(math.isclose(actual, expected, rel_tol=2e-13, abs_tol=2e-15), 'numerical mismatch: ' + label)


def interval(values: list[float], indices: np.ndarray) -> list[float]:
    ordered = np.sort(np.asarray(values, dtype=np.float64)[indices].mean(axis=1))
    result = []
    for probability in (.025, .975):
        pos = probability * (len(ordered) - 1)
        lo, hi = math.floor(pos), math.ceil(pos)
        result.append(float(ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)))
    return result


def exact_determinant(matrix: list[list[int]]) -> Fraction:
    """Rational Gaussian elimination, separate from the Bareiss producer."""
    a = [list(map(Fraction, row)) for row in matrix]
    result = Fraction(1)
    for k in range(len(a)):
        pivot = next((i for i in range(k, len(a)) if a[i][k]), None)
        if pivot is None:
            return Fraction(0)
        if pivot != k:
            a[k], a[pivot] = a[pivot], a[k]
            result = -result
        value = a[k][k]
        result *= value
        for i in range(k + 1, len(a)):
            factor = a[i][k] / value
            for j in range(k, len(a)):
                a[i][j] -= factor * a[k][j]
    return result


def audit(directory: Path, sources: Path) -> dict:
    require(directory.is_dir() and not directory.is_symlink(), 'regular result directory required')
    require({p.name for p in directory.iterdir()} == OUTPUTS | {'receipt.json'}, 'result inventory mismatch')
    receipt = strict_json(checked_file(directory, 'receipt.json'))
    require(receipt.get('schema') == 'hadamard-strengthening-results.v2' and receipt.get('status') == 'passed', 'unsuccessful or wrong study receipt')
    require(receipt.get('registration_commit') == REGISTRATION, 'registration mismatch')
    require(receipt.get('cells') == 7600 and receipt.get('settings') == 19, 'receipt counts mismatch')
    hashes = receipt.get('output_sha256', {})
    require(set(hashes) == OUTPUTS, 'output checksum inventory mismatch')
    for name, expected in hashes.items():
        require(digest(checked_file(directory, name)) == expected, 'output checksum mismatch: ' + name)
    source_hashes = receipt.get('source_sha256', {})
    require({'study.py', 'exact_checks.py', 'protocol-v2.json'} <= set(source_hashes), 'required source binding missing')
    require(source_hashes['protocol-v2.json'] == PROTOCOL_SHA256, 'frozen protocol mismatch')
    for name, expected in source_hashes.items():
        require(digest(checked_file(sources, name)) == expected, 'source checksum mismatch: ' + name)

    seeds = list(range(1000, 1100))
    settings = {('gaussian_outlier', a, g) for a in (1, 2, 4, 8, 16, 32) for g in (128, 32, 16)} | {('quantizer_grid', 0, 128)}
    expected_cells = {(s, c, a, g, arm) for s in seeds for c, a, g in settings for arm in ARMS}
    cells = {}
    with (directory / 'cells.csv').open(newline='') as f:
        reader = csv.DictReader(f)
        require(reader.fieldnames == ['seed', 'case', 'multiplier', 'group', 'arm', 'error'], 'CSV header mismatch')
        for row in reader:
            require(set(row) == set(reader.fieldnames), 'malformed CSV row')
            key = (int(row['seed']), row['case'], int(row['multiplier']), int(row['group']), row['arm'])
            require(key not in cells, 'duplicate raw cell')
            value = float(row['error'])
            require(math.isfinite(value) and value >= 0, 'nonfinite or negative raw error')
            cells[key] = value
    require(set(cells) == expected_cells, 'raw coverage mismatch')
    summaries = strict_json(directory / 'summary.json')
    require(type(summaries) is list and len(summaries) == 19, 'summary count mismatch')
    by_setting = {(x['case'], x['multiplier'], x['group']): x for x in summaries}
    require(set(by_setting) == settings, 'summary coverage or duplicate mismatch')
    indices = np.random.Generator(np.random.PCG64(20261021)).integers(0, 100, size=(10000, 100))
    comparisons = 0
    for key, row in by_setting.items():
        require(type(row.get('seeds')) is int and row['seeds'] == 100, 'summary seed count mismatch')
        require(set(row['arms']) == set(ARMS), 'summary arm mismatch')
        c, a, g = key
        values = {arm: [cells[s, c, a, g, arm] for s in seeds] for arm in ARMS}
        for arm, observations in values.items():
            delta = [x - y for x, y in zip(observations, values['original'])]
            record = row['arms'][arm]
            for field, expected in [('mean_error', math.fsum(observations)/100),
                                    ('mean_delta_vs_original', math.fsum(delta)/100),
                                    ('min_error', min(observations)), ('max_error', max(observations))]:
                close(record[field], expected, field)
                comparisons += 1
            wins = record['wins_vs_original']
            require(type(wins) is int and wins == sum(x < 0 for x in delta), 'win count mismatch')
            comparisons += 1
            bounds = record['paired_95_interval_vs_original']
            require(type(bounds) is list and len(bounds) == 2, 'invalid interval shape')
            for actual, expected in zip(bounds, interval(delta, indices)):
                close(actual, expected, 'paired interval')
                comparisons += 1
        delta = [x - y for x, y in zip(values['randomized_hadamard'], values['haar_orthogonal'])]
        haar = row['hadamard_minus_haar']
        close(haar['mean'], math.fsum(delta)/100, 'Hadamard-minus-Haar mean')
        bounds = haar['descriptive_paired_95_interval']
        require(type(bounds) is list and len(bounds) == 2, 'invalid Haar interval shape')
        for actual, expected in zip(bounds, interval(delta, indices)):
            close(actual, expected, 'Hadamard-minus-Haar interval')
        comparisons += 3
    primary = by_setting['gaussian_outlier', 32, 32]
    require(receipt['primary'] == primary, 'primary receipt differs from audited summary')
    require(receipt.get('directional_confirmation_within_synthetic_family') is (primary['arms']['randomized_hadamard']['paired_95_interval_vs_original'][1] < 0), 'directional decision mismatch')
    controls = receipt['controls']
    for name in ('orthogonality_max_absolute', 'full_precision_max_relative_norm', 'signed_permutation_group128_max_error_difference'):
        require(valid_number(controls.get(name)) and 0 <= controls[name] <= 2e-13, 'numerical control failed: ' + name)
    for seed in seeds:
        for arm in ('original', 'signed_permutation'):
            require(cells[seed, 'quantizer_grid', 0, 128, arm] <= 1e-27, 'grid negative control failed')
        for amp in (1, 2, 4, 8, 16, 32):
            require(abs(cells[seed, 'gaussian_outlier', amp, 128, 'original'] - cells[seed, 'gaussian_outlier', amp, 128, 'signed_permutation']) <= 2e-13, 'permutation raw control failed')

    inputs = strict_json(directory / 'inputs.json')
    require(type(inputs) is list and len(inputs) == 100 and {x['seed'] for x in inputs} == set(seeds), 'input seed coverage mismatch')
    for record in inputs:
        require(set(record['q_sha256']) == set(ARMS) and set(record['q_largest_absolute_entry']) == set(ARMS), 'input transform coverage mismatch')
        for value in [record[k] for k in ('base_x_sha256', 'w_sha256', 'grid_x_sha256', 'grid_w_sha256')] + list(record['q_sha256'].values()):
            require(type(value) is str and bool(re.fullmatch('[0-9a-f]{64}', value)), 'malformed input hash')
        for peak in record['q_largest_absolute_entry'].values():
            require(valid_number(peak) and 0 < peak <= 1 + 2e-13, 'invalid transform peak')
    exact = strict_json(directory / 'exact-checks.json')
    require([x['q'] for x in exact['paley']] == list(PRIMES), 'Paley coverage mismatch')
    for record, q in zip(exact['paley'], PRIMES):
        n = q + 1
        require(record['order'] == n and abs(record['determinant']) == record['absolute_determinant_bound'] == n**(n//2), 'Paley determinant mismatch')
        require(record['integer_gram_pass'] is True and record['corruption_rejected'] is True and record['character_correlations_checked'] == q*q, 'Paley checks missing')
    h = exact['order_12_matrix']
    require(len(h) == 12 and all(len(row) == 12 for row in h), 'order-12 shape mismatch')
    require(all(type(x) is int and x in (-1, 1) for row in h for x in row), 'order-12 entry mismatch')
    require(all(sum(x*y for x, y in zip(h[i], h[j])) == (12 if i == j else 0) for i in range(12) for j in range(12)), 'order-12 Gram mismatch')
    require(abs(exact_determinant(h)) == 2985984, 'independent order-12 determinant mismatch')
    require(exact['rational_counterexample']['relative_squared_error'] == '11/3332' and exact['invalid_inputs_rejected'] is True, 'exact evidence mismatch')
    return {'schema': 'hadamard-complete-audit.v1', 'status': 'passed', 'raw_cells': len(cells),
            'settings': len(settings), 'reconstructed_scalar_summary_fields': comparisons,
            'source_files_bound': len(source_hashes), 'input_seed_records': len(inputs),
            'independent_order_12_determinant': 2985984,
            'scope': 'Integrity, source binding, complete raw coverage, all reported summary statistics and finite controls. Not proof of provenance or committee review.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--sources', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory, args.sources), indent=2))
