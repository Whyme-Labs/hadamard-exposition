"""Publisher safety tests; these fixture receipts are not scientific evidence."""
import json
import os
from unittest.mock import patch
from pathlib import Path
import subprocess
import tempfile
import unittest
import build_bundle as b
import publish_bundle as p


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.build = self.root / 'build'; self.build.mkdir()
        self.ref = 'a' * 40
        self.spec = {'source_commit': self.ref, 'files': {'article.md': b.blob_id(b'# Fixture\n')}}
        self.files = b.seal({'article.md': b'# Fixture\n', **{name: b'Fixture\n' for name in b.META}}, self.ref)
        b.write_files(self.build / 'payload', self.files)
        receipt = b.json_bytes({'status': 'passed', 'reproduce_requested': True,
            'phases': [{'name': n, 'status': 'passed'} for n in sorted(p.PHASES)]})
        (self.build / 'validation.json').write_bytes(receipt)
        b.write_zip(self.build / 'hadamard-exposition-v1.zip', self.files)
        self.report = {'status': 'passed', 'scientific_source_commit': self.ref,
            'validation_receipt_sha256': b.sha256(receipt), 'manifest_sha256': b.sha256(self.files['MANIFEST.json']),
            'archive_sha256': b.sha256((self.build / 'hadamard-exposition-v1.zip').read_bytes())}
        self.save_report()

    def save_report(self):
        (self.build / 'build-report.json').write_bytes(b.json_bytes(self.report))

    def test_load_verified_fixture(self):
        self.assertEqual(p.load_verified(self.build, self.spec), self.files)

    def test_failed_receipt_blocks_publication(self):
        self.report['status'] = 'failed'; self.save_report()
        with self.assertRaises(b.ReleaseError): p.load_verified(self.build, self.spec)

    def test_receipt_tampering_blocks_publication(self):
        (self.build / 'validation.json').write_text('{}')
        with self.assertRaises(b.ReleaseError): p.load_verified(self.build, self.spec)

    def test_extra_private_file_blocks_publication(self):
        (self.build / 'payload' / 'private.txt').write_text('no')
        with self.assertRaises(b.ReleaseError): p.load_verified(self.build, self.spec)

    def test_source_mismatch_blocks_publication(self):
        self.spec['files']['article.md'] = '0' * 40
        with self.assertRaises(b.ReleaseError): p.load_verified(self.build, self.spec)

    def test_missing_reproduction_phase_blocks_even_with_updated_hash(self):
        receipt = json.loads((self.build / 'validation.json').read_text())
        receipt['phases'] = [x for x in receipt['phases'] if x['name'] != 'group_reproduction']
        data = b.json_bytes(receipt)
        (self.build / 'validation.json').write_bytes(data)
        self.report['validation_receipt_sha256'] = b.sha256(data); self.save_report()
        with self.assertRaises(b.ReleaseError): p.load_verified(self.build, self.spec)

    def test_archive_symlink_blocks_publication(self):
        archive = self.build / 'hadamard-exposition-v1.zip'
        raw = archive.read_bytes(); archive.unlink()
        external = self.root / 'external.zip'; external.write_bytes(raw); archive.symlink_to(external)
        with self.assertRaises(b.ReleaseError): p.load_verified(self.build, self.spec)

    def test_resealed_extra_file_still_blocks_publication(self):
        files = {k: v for k, v in self.files.items() if k not in b.RESERVED}
        files['private.txt'] = b'private history'
        resealed = b.seal(files, self.ref)
        for name, data in resealed.items(): (self.build / 'payload' / name).write_bytes(data)
        self.report['manifest_sha256'] = b.sha256(resealed['MANIFEST.json']); self.save_report()
        with self.assertRaises(b.ReleaseError): p.load_verified(self.build, self.spec)

    def test_new_repository_has_no_source_history(self):
        stage = self.root / 'public'
        sha = p.prepare_root(stage, self.files)
        history = subprocess.check_output(['git', '-C', str(stage), 'rev-list', '--parents', 'HEAD']).decode().split()
        self.assertEqual(history, [sha])
        self.assertFalse((stage / 'private.txt').exists())
        self.assertFalse(subprocess.check_output(['git', '-C', str(stage), 'remote']).strip())

    def test_existing_stage_is_not_modified(self):
        stage = self.root / 'existing'; stage.mkdir(); marker = stage / 'private.txt'; marker.write_text('keep')
        with self.assertRaises(b.ReleaseError): p.prepare_root(stage, self.files)
        self.assertEqual(marker.read_text(), 'keep')

    def test_payload_symlink_blocks_publication(self):
        (self.build / 'payload' / 'link.txt').symlink_to('../validation.json')
        with self.assertRaises(b.ReleaseError): p.load_verified(self.build, self.spec)


    def test_global_clean_filter_cannot_change_frozen_bytes(self):
        attributes = self.root / 'global-attributes'
        attributes.write_text('* filter=replace\n')
        config = self.root / 'gitconfig'
        config.write_text('[core]\n    attributesFile = ' + str(attributes) +
                          '\n[filter "replace"]\n    clean = printf changed\n')
        stage = self.root / 'filtered-public'
        with patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': str(config)}):
            p.prepare_root(stage, self.files)
        original = subprocess.check_output(['git', '-C', str(stage), 'show', 'HEAD:article.md'])
        self.assertEqual(original, self.files['article.md'])

    def test_inherited_git_environment_cannot_redirect_public_commit(self):
        other = self.root / 'unrelated'; other.mkdir()
        subprocess.run(['git', '-C', str(other), 'init', '-q'], check=True)
        stage = self.root / 'isolated-public'
        with patch.dict(os.environ, {'GIT_DIR': str(other / '.git'), 'GIT_WORK_TREE': str(other)}):
            sha = p.prepare_root(stage, self.files)
        self.assertEqual(subprocess.check_output(['git', '-C', str(stage), 'rev-parse', 'HEAD']).decode().strip(), sha)
        self.assertFalse((other / 'article.md').exists())

    def test_gh_cannot_inherit_git_directory_or_alternate_host(self):
        with patch.dict(os.environ, {'GIT_DIR': '/unrelated', 'GH_HOST': 'example.invalid'}):
            with patch('publish_bundle.subprocess.run') as invoked:
                invoked.return_value = subprocess.CompletedProcess(['gh'], 0, b'ok', b'')
                self.assertEqual(p.run(['gh', 'auth', 'status']), b'ok')
        environment = invoked.call_args.kwargs['env']
        self.assertNotIn('GIT_DIR', environment)
        self.assertEqual(environment['GH_HOST'], 'github.com')

if __name__ == '__main__': unittest.main()
