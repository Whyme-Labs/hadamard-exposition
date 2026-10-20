"""Release boundary tests. Tiny Git fixtures never stand in for scientific reproduction."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_bundle as b


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'source'
        self.repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL)
        self.git = git
        git('init', '-q')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'article.md').write_bytes(b'# Fixture\n')
        (self.repo / 'private.txt').write_bytes(b'Not for publication\n')
        git('add', '.')
        git('commit', '-qm', 'fixture')
        self.ref = git('rev-parse', 'HEAD').decode().strip()
        self.spec = {'source_commit': self.ref, 'files': {'article.md': b.blob_id(b'# Fixture\n')}}

    def test_exports_only_allowlisted_bytes(self):
        self.assertEqual(b.collect(self.repo, self.spec), {'article.md': b'# Fixture\n'})

    def test_reads_frozen_git_not_dirty_worktree(self):
        (self.repo / 'article.md').write_text('changed')
        self.assertEqual(b.collect(self.repo, self.spec)['article.md'], b'# Fixture\n')

    def test_changed_expected_blob_fails(self):
        self.spec['files']['article.md'] = '0' * 40
        with self.assertRaises(b.ReleaseError): b.collect(self.repo, self.spec)

    def test_missing_file_fails(self):
        self.spec['files']['missing.md'] = '0' * 40
        with self.assertRaises(b.ReleaseError): b.collect(self.repo, self.spec)

    def test_mutable_ref_fails(self):
        self.spec['source_commit'] = 'main'
        with self.assertRaises(b.ReleaseError): b.collect(self.repo, self.spec)

    def test_unsafe_paths_fail(self):
        for path in ('../x', '/tmp/x', '.git/config', 'a/../b', 'a//b', 'x\\y', 'a\nb', '.', 'a/.GIT/config', 'C:/x'):
            with self.subTest(path=path), self.assertRaises(b.ReleaseError): b.safe_path(path)

    def test_case_collision_fails(self):
        self.spec['files']['ARTICLE.md'] = self.spec['files']['article.md']
        with self.assertRaises(b.ReleaseError): b.collect(self.repo, self.spec)

    def test_symlink_in_git_fails(self):
        (self.repo / 'link.md').symlink_to('article.md')
        self.git('add', 'link.md'); self.git('commit', '-qm', 'link')
        self.spec['source_commit'] = self.git('rev-parse', 'HEAD').decode().strip()
        self.spec['files']['link.md'] = b.blob_id(b'article.md')
        with self.assertRaises(b.ReleaseError): b.collect(self.repo, self.spec)

    def test_manifest_checks_tampering(self):
        files = b.seal({'article.md': b'# Fixture\n'}, self.ref)
        b.verify(files)
        files['article.md'] += b'x'
        with self.assertRaises(b.ReleaseError): b.verify(files)

    def test_manifest_rejects_extra_file(self):
        files = b.seal({'article.md': b'# Fixture\n'}, self.ref)
        files['private.txt'] = b'no'
        with self.assertRaises(b.ReleaseError): b.verify(files)

    def test_manifest_rejects_removed_file(self):
        files = b.seal({'article.md': b'# Fixture\n'}, self.ref)
        del files['article.md']
        with self.assertRaises(b.ReleaseError): b.verify(files)

    def test_checksum_list_is_verified(self):
        files = b.seal({'article.md': b'# Fixture\n'}, self.ref)
        files['SHA256SUMS'] = b'forged\n'
        with self.assertRaises(b.ReleaseError): b.verify(files)

    def test_credential_detection_and_no_value_disclosure(self):
        token = b'ghp_' + b'A' * 36
        with self.assertRaises(b.ReleaseError) as error: b.scan({'leak.txt': token})
        self.assertNotIn(token.decode(), str(error.exception))
        b.scan({'README.md': b'No password or api_key is required.'})

    def test_local_links_are_checked(self):
        b.check_links({'README.md': b'[article](article.md)', 'article.md': b'# Present'})
        with self.assertRaises(b.ReleaseError): b.check_links({'README.md': b'[lost](missing.md)'})

    def test_local_links_with_fragment_and_query(self):
        b.check_links({'README.md': b'[x](article.md?download=1#example)', 'article.md': b'# A'})

    def test_zip_is_byte_identical(self):
        files = b.seal({'article.md': b'# Fixture\n'}, self.ref)
        one, two = Path(self.tmp.name) / 'a.zip', Path(self.tmp.name) / 'b.zip'
        b.write_zip(one, files); b.write_zip(two, dict(reversed(list(files.items()))))
        self.assertEqual(one.read_bytes(), two.read_bytes())

    def test_output_overwrite_refused(self):
        with self.assertRaises(b.ReleaseError): b.require_new_output(self.repo)
        self.assertEqual((self.repo / 'article.md').read_bytes(), b'# Fixture\n')

    def test_cli_preserves_existing_receipt(self):
        output = Path(self.tmp.name) / 'existing'
        output.mkdir()
        receipt = output / 'build-report.json'
        receipt.write_bytes(b'{\"status\": \"passed\"}\n')
        before = receipt.read_bytes()
        result = subprocess.run([sys.executable, str(HERE / 'build_bundle.py'), '--output', str(output)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(receipt.read_bytes(), before)

    def test_real_spec_closes_historical_dependency_gap(self):
        path = HERE / 'spec.json'
        if path.exists():
            spec = json.loads(path.read_text())
            self.assertIn('docs/reference-import.json', spec['files'])
            self.assertNotIn('docs/awards/jsp-000013-public-release-plan.md', spec['files'])
            self.assertFalse(any(p.startswith('benchmarks/') for p in spec['files']))
        else:
            self.fail('Real release specification missing')

if __name__ == '__main__': unittest.main()
