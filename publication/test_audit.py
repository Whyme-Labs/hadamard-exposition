import gzip
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from audit import Audit, GitHubRead, scan_git


class Tests(unittest.TestCase):
    def secret(self):
        return ('gh' + 'p_' + 'A9b8C7d6E5f4' * 3).encode()

    def zip(self, name, content):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z: z.writestr(name, content)
        return stream.getvalue()

    def test_secret_is_detected_without_disclosure(self):
        audit = Audit(); audit.scan(self.secret(), 'fixture')
        report = json.dumps(audit.report())
        self.assertIn('github_token', report)
        self.assertNotIn(self.secret().decode(), report)
        self.assertFalse(audit.report()['publication_authorized_by_scanner'])

    def test_nested_zip_gzip(self):
        audit = Audit()
        audit.scan(self.zip('nested.gz', gzip.compress(self.secret())), 'outer.zip')
        self.assertEqual(audit.findings[0]['location'], 'outer.zip!nested.gz!gunzip')
        self.assertFalse(audit.gaps)

    def test_tar_member_scanned_without_extraction(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as t:
            entry = tarfile.TarInfo('data.txt'); entry.size = len(self.secret())
            t.addfile(entry, io.BytesIO(self.secret()))
        audit = Audit(); audit.scan(gzip.compress(stream.getvalue()), 'outer.tar.gz')
        self.assertTrue(audit.findings)
        self.assertFalse(audit.gaps)

    def test_archive_traversal_fails_closed(self):
        audit = Audit(); audit.scan(self.zip('../escaped', b'abc'), 'outer.zip')
        self.assertTrue(audit.gaps)
        self.assertEqual(audit.report()['automated_status'], 'incomplete')

    def test_tar_symlink_rejected(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as t:
            entry = tarfile.TarInfo('link'); entry.type = tarfile.SYMTYPE; entry.linkname = '/etc/passwd'; t.addfile(entry)
        audit = Audit(); audit.scan(stream.getvalue(), 'link.tar')
        self.assertTrue(audit.gaps)

    def test_corrupted_zip_is_not_clean(self):
        audit = Audit(); audit.scan(b'PK\x03\x04broken', 'broken.zip')
        self.assertTrue(audit.gaps)

    def test_oversized_member_is_gap(self):
        import audit as module
        old = module.MAX_FILE
        try:
            module.MAX_FILE = 200
            a = Audit(); a.scan(gzip.compress(b'x' * 500), 'large.gz')
            self.assertTrue(a.gaps)
        finally: module.MAX_FILE = old

    def test_recursive_archive_bound(self):
        data = self.secret()
        for _ in range(8): data = gzip.compress(data)
        audit = Audit(); audit.scan(data, 'deep.gz')
        self.assertTrue(audit.gaps)

    def test_lfs_is_gap(self):
        audit = Audit(); audit.scan(b'version https://git-lfs.github.com/spec/v1\noid sha256:abc', 'pointer')
        self.assertTrue(audit.gaps)

    def test_redistribution_inventory(self):
        audit = Audit(); audit.scan(self.zip('model.safetensors', b'opaque'), 'model.zip')
        self.assertEqual(len(audit.redistribution), 1)

    def test_example_doc_does_not_match_private_key(self):
        audit = Audit(); audit.scan(b'Look for BEGIN PRIVATE KEY, api_key, password.', 'doc')
        self.assertFalse(audit.findings)

    def test_literal_password_and_capability_are_flagged(self):
        audit = Audit(); audit.scan(b'password="fixture-value-123" https://example.org/?token=' + b'a' * 25, 'example')
        self.assertEqual({v['rule'] for v in audit.findings}, {'credential_assignment', 'url_capability'})

    def test_git_scans_deleted_file_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*a): return subprocess.check_output(['git','-C',tmp,*a], stderr=subprocess.DEVNULL)
            git('init','-b','main'); git('config','user.name','fixture'); git('config','user.email','fixture@example.org')
            (root/'old.txt').write_bytes(self.secret())
            git('add','.'); git('commit','-m','fixture')
            git('rm','old.txt'); git('commit','-m','remove fixture')
            audit = Audit(); result = scan_git(root, audit)
            self.assertEqual(result['object_types']['commit'], 2)
            self.assertTrue(any(v['rule']=='github_token' for v in audit.findings))

    def test_pagination_does_not_stop_at_first_page(self):
        api = GitHubRead('fake')
        api.get = lambda p: list(range(100)) if p.endswith('page=1') else [999]
        self.assertEqual(len(api.pages('/issues')), 101)

    def test_no_scope_does_not_authorize_publish(self):
        self.assertFalse(Audit().report()['publication_authorized_by_scanner'])

if __name__ == '__main__': unittest.main()
