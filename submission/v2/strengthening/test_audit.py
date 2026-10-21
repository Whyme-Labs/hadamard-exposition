"""Synthetic audit fixtures. These receipts are not experiment evidence."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from audit_study import audit, ARMS, REGISTRATION
from exact_checks import verify
from study import summarize


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory(prefix='hadamard-audit-fixtures-')
        cls.base = Path(cls.storage.name) / 'fixture'
        cls.base.mkdir()
        cls.sources = cls.base / 'sources'
        cls.sources.mkdir()
        for name in ('study.py', 'exact_checks.py', 'protocol-v2.json'):
            shutil.copyfile(Path(__file__).parent / name, cls.sources / name)
        out = cls.base / 'run'
        out.mkdir()
        cells = []
        seeds = list(range(1000, 1100))
        for seed in seeds:
            for amp in (1, 2, 4, 8, 16, 32):
                for group in (128, 32, 16):
                    baseline = .01 + (seed - 1000)*.00001 + amp*.0001 + group*.000001
                    for arm in ARMS:
                        factor = {'original': 1., 'randomized_hadamard': .6, 'haar_orthogonal': .8,
                                  'signed_permutation': 1. if group == 128 else .99}[arm]
                        cells.append(dict(seed=seed, case='gaussian_outlier', multiplier=amp, group=group, arm=arm, error=baseline*factor))
            for arm in ARMS:
                value = 0. if arm in ('original', 'signed_permutation') else .02
                cells.append(dict(seed=seed, case='quantizer_grid', multiplier=0, group=128, arm=arm, error=value))
        with (out/'cells.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['seed','case','multiplier','group','arm','error'], lineterminator='\n')
            writer.writeheader(); writer.writerows(cells)
        summary = summarize(cells, list(ARMS), seeds, 10000, 20261021)
        inputs = [{'seed': seed, 'base_x_sha256': '0'*64, 'w_sha256': '1'*64,
                   'grid_x_sha256': '2'*64, 'grid_w_sha256': '3'*64,
                   'q_sha256': {arm: '4'*64 for arm in ARMS},
                   'q_largest_absolute_entry': {arm: 1. for arm in ARMS}} for seed in seeds]
        for name, value in [('summary.json', summary), ('inputs.json', inputs), ('exact-checks.json', verify([3,7,11,19,23,31,43]))]:
            (out/name).write_text(json.dumps(value, indent=2)+'\n')
        receipt = {'schema':'hadamard-strengthening-results.v2', 'status':'passed', 'registration_commit':REGISTRATION,
                   'cells':7600, 'settings':19, 'scope':'FABRICATED TEST FIXTURE ONLY',
                   'directional_confirmation_within_synthetic_family':True,
                   'primary':next(x for x in summary if (x['case'],x['multiplier'],x['group']) == ('gaussian_outlier',32,32)),
                   'controls':{'orthogonality_max_absolute':0., 'full_precision_max_relative_norm':0.,
                               'signed_permutation_group128_max_error_difference':0.},
                   'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.sources.iterdir()},
                   'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}}
        (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')

    @classmethod
    def tearDownClass(cls):
        cls.storage.cleanup()

    def setUp(self):
        self.storage_case = tempfile.TemporaryDirectory(prefix='hadamard-audit-case-')
        self.root = Path(self.storage_case.name)/'copy'
        shutil.copytree(self.base, self.root)
        self.run = self.root/'run'
        self.source = self.root/'sources'

    def tearDown(self):
        self.storage_case.cleanup()

    def mutate(self, filename, change):
        path = self.run/filename
        obj = json.loads(path.read_text())
        change(obj)
        path.write_text(json.dumps(obj, indent=2)+'\n')
        if filename != 'receipt.json':
            self.refresh_hash(filename)

    def refresh_hash(self, name):
        receipt = json.loads((self.run/'receipt.json').read_text())
        receipt['output_sha256'][name] = hashlib.sha256((self.run/name).read_bytes()).hexdigest()
        (self.run/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')

    def rejected(self):
        with self.assertRaises(ValueError):
            audit(self.run, self.source)

    def test_complete_fixture(self):
        self.assertEqual(audit(self.run,self.source)['reconstructed_scalar_summary_fields'],589)

    def test_false_delta_with_updated_checksum(self):
        self.mutate('summary.json',lambda x:x[0]['arms']['randomized_hadamard'].__setitem__('mean_delta_vs_original',999.))
        self.rejected()

    def test_false_haar_contrast(self):
        self.mutate('summary.json',lambda x:x[0]['hadamard_minus_haar'].__setitem__('mean',999.))
        self.rejected()

    def test_false_haar_interval(self):
        self.mutate('summary.json',lambda x:x[0]['hadamard_minus_haar'].__setitem__('descriptive_paired_95_interval',[9.,10.]))
        self.rejected()

    def test_false_minimum(self):
        self.mutate('summary.json',lambda x:x[0]['arms']['original'].__setitem__('min_error',0.))
        self.rejected()

    def test_false_maximum(self):
        self.mutate('summary.json',lambda x:x[0]['arms']['original'].__setitem__('max_error',1.))
        self.rejected()

    def test_missing_hash(self):
        self.mutate('receipt.json',lambda x:x['output_sha256'].pop('summary.json'))
        self.rejected()

    def test_false_receipt_count(self):
        self.mutate('receipt.json',lambda x:x.__setitem__('cells',7599))
        self.rejected()

    def test_unbound_source(self):
        self.mutate('receipt.json',lambda x:x['source_sha256'].pop('study.py'))
        self.rejected()

    def test_changed_source(self):
        with (self.source/'study.py').open('a') as f: f.write('\n# changed\n')
        self.rejected()

    def test_changed_protocol(self):
        with (self.source/'protocol-v2.json').open('a') as f: f.write(' ')
        self.rejected()

    def test_false_primary_copy(self):
        self.mutate('receipt.json',lambda x:x['primary']['arms']['original'].__setitem__('mean_error',9.))
        self.rejected()

    def test_false_directional_decision(self):
        self.mutate('receipt.json',lambda x:x.__setitem__('directional_confirmation_within_synthetic_family',False))
        self.rejected()

    def test_duplicate_raw_cell(self):
        path=self.run/'cells.csv'
        rows=path.read_text().splitlines(True)
        path.write_text(''.join(rows+[rows[1]])); self.refresh_hash('cells.csv')
        self.rejected()

    def test_missing_raw_cell(self):
        path=self.run/'cells.csv'; rows=path.read_text().splitlines(True)
        path.write_text(''.join(rows[:-1])); self.refresh_hash('cells.csv')
        self.rejected()

    def test_duplicate_input_seed(self):
        self.mutate('inputs.json',lambda x:x[1].__setitem__('seed',1000))
        self.rejected()

    def test_corrupt_matrix_with_updated_checksum(self):
        self.mutate('exact-checks.json',lambda x:x['order_12_matrix'][0].__setitem__(0,-1))
        self.rejected()

    def test_symlink_output(self):
        path=self.run/'summary.json'; target=self.root/'external.json'
        path.rename(target); path.symlink_to(target)
        self.rejected()

    def test_extra_file(self):
        (self.run/'unexpected.txt').write_text('not allowlisted')
        self.rejected()

    def test_duplicate_json_key(self):
        path=self.run/'receipt.json'
        path.write_text(path.read_text().replace('{','{"status":"passed",',1))
        self.rejected()

    def test_nonfinite_control(self):
        self.mutate('receipt.json',lambda x:x['controls'].__setitem__('orthogonality_max_absolute',float('nan')))
        self.rejected()


if __name__ == '__main__':
    unittest.main()
