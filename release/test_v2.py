"""Boundary tests for release assembly. Tiny fixtures are not science evidence."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile
from build_v2 import safe_read, write_archive, verify_inventory, reserve_output, blob_sha


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.TemporaryDirectory(prefix='v2-release-test-')
        self.root = Path(self.store.name)

    def tearDown(self):
        self.store.cleanup()

    def test_byte_identity(self):
        self.assertEqual(blob_sha(b''), 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391')

    def test_symlink_rejected(self):
        (self.root/'data').write_text('x')
        (self.root/'link').symlink_to(self.root/'data')
        with self.assertRaises(ValueError): safe_read(self.root, 'link')

    def test_symlink_parent_rejected(self):
        (self.root/'folder').mkdir(); (self.root/'folder/a').write_text('x')
        (self.root/'redirect').symlink_to(self.root/'folder', target_is_directory=True)
        with self.assertRaises(ValueError): safe_read(self.root, 'redirect/a')

    def test_traversal_rejected(self):
        for name in ('../a', '/tmp/a', './a', 'a//b', 'a/../b'):
            with self.subTest(name=name), self.assertRaises(ValueError): safe_read(self.root, name)

    def test_existing_output_preserved(self):
        destination=self.root/'output'; destination.mkdir()
        (destination/'receipt').write_text('prior evidence')
        with self.assertRaises(FileExistsError): reserve_output(destination)
        self.assertEqual((destination/'receipt').read_text(), 'prior evidence')

    def test_broken_symlink_output_rejected(self):
        destination=self.root/'output'; destination.symlink_to(self.root/'missing')
        with self.assertRaises(FileExistsError): reserve_output(destination)

    def test_inventory_tamper_and_extras_rejected(self):
        (self.root/'a').write_text('x')
        inventory={'a':hashlib.sha256(b'x').hexdigest()}
        verify_inventory(self.root,inventory)
        (self.root/'b').write_text('extra')
        with self.assertRaises(ValueError): verify_inventory(self.root,inventory)
        (self.root/'b').unlink(); (self.root/'a').write_text('changed')
        with self.assertRaises(ValueError): verify_inventory(self.root,inventory)

    def test_archive_is_deterministic_for_fixed_payload(self):
        payload=self.root/'payload'; payload.mkdir(); (payload/'a').write_text('same bytes')
        a=self.root/'a.zip'; b=self.root/'b.zip'
        write_archive(payload,a); write_archive(payload,b)
        self.assertEqual(a.read_bytes(),b.read_bytes())
        with zipfile.ZipFile(a) as archive:
            self.assertEqual(archive.namelist(),['hadamard-exposition-v2/a'])
            self.assertEqual(archive.read(archive.namelist()[0]),b'same bytes')


if __name__=='__main__': unittest.main()
