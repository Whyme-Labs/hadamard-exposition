"""Offline controls for immutable acquisition and frozen article selection."""

from copy import deepcopy
from dataclasses import replace
import hashlib
from http.client import IncompleteRead
import io
import json
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest.mock import patch

import model_acquire as acquisition
from contract import ContractError


MANIFEST = json.loads(Path(__file__).with_name("model-benchmark-v1.json").read_text())


class Response(io.BytesIO):
    def __init__(self, content, *, length=None, url="https://huggingface.co/pinned/file", etag=""):
        super().__init__(content)
        self.status = 200
        self.headers = {"ETag": etag}
        if length is not None:
            self.headers["Content-Length"] = str(length)
        self.url = url

    def geturl(self):
        return self.url


class AcquiredInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.spec = replace(acquisition.allowed_artifacts(MANIFEST)[0], expected_bytes=5,
                            expected_sha256=hashlib.sha256(b"abcde").hexdigest())

    def download(self, response, *, spec=None, limit=100):
        record = {}
        budget = acquisition._DownloadBudget(limit)
        acquisition._download_one(spec or self.spec, self.directory, budget,
                                  time.monotonic() + 5, lambda *a, **kw: response, record)
        return record, budget

    def test_allowlist_rejects_unpinned_model_and_extra_files(self):
        specs = acquisition.allowed_artifacts(MANIFEST)
        self.assertEqual(len(specs), 8)
        self.assertEqual(specs[1].expected_bytes, 166029852)
        self.assertEqual(specs[1].expected_sha256,
                         "ebfa4e2f18696ebd83716a0d39fe2c025f2ff8483f72a83ca59c475692fc9d15")
        for edit in (lambda m: m["model"].update(revision="main"),
                     lambda m: m["model"]["files"].append("pytorch_model.bin"),
                     lambda m: m["dataset"]["files"].update(train="../other.parquet")):
            manifest = deepcopy(MANIFEST)
            edit(manifest)
            with self.assertRaises(ContractError):
                acquisition.allowed_artifacts(manifest)

    def test_published_hash_and_git_blob_etag_are_verified(self):
        etag = hashlib.sha1(b"blob 5\0abcde").hexdigest()
        record, budget = self.download(Response(b"abcde", length=5, etag=f'"{etag}"'))
        self.assertEqual((self.directory / self.spec.relative_path).read_bytes(), b"abcde")
        self.assertEqual(record["sha256"], hashlib.sha256(b"abcde").hexdigest())
        self.assertEqual((record["status"], budget.used), ("complete", 5))
        self.assertFalse((self.directory / (self.spec.relative_path + ".partial")).exists())

    def test_wrong_hash_keeps_partial_and_never_publishes_target(self):
        with self.assertRaisesRegex(acquisition.AcquisitionError, "SHA256"):
            self.download(Response(b"ABCDE", length=5))
        self.assertFalse((self.directory / self.spec.relative_path).exists())
        self.assertEqual((self.directory / (self.spec.relative_path + ".partial")).read_bytes(), b"ABCDE")

    def test_truncated_body_keeps_received_bytes(self):
        record, budget = {}, acquisition._DownloadBudget(100)
        with self.assertRaisesRegex(acquisition.AcquisitionError, "truncated"):
            acquisition._download_one(self.spec, self.directory, budget, time.monotonic() + 5,
                                      lambda *a, **kw: Response(b"abc", length=5), record)
        self.assertEqual(record["sha256"], hashlib.sha256(b"abc").hexdigest())
        self.assertEqual((record["bytes"], budget.used), (3, 3))

    def test_http_incomplete_read_payload_is_charged_and_retained(self):
        response = Response(b"", length=5)
        response.read = lambda n: (_ for _ in ()).throw(IncompleteRead(b"abc", 2))
        budget, record = acquisition._DownloadBudget(100), {}
        with self.assertRaisesRegex(acquisition.AcquisitionError, "incomplete body"):
            acquisition._download_one(self.spec, self.directory, budget, time.monotonic() + 5,
                                      lambda *a, **kw: response, record)
        self.assertEqual((record["bytes"], budget.used), (3, 3))
        self.assertEqual((self.directory / (self.spec.relative_path + ".partial")).read_bytes(), b"abc")

    def test_content_length_exceeds_budget_before_body_read(self):
        spec = replace(self.spec, expected_bytes=None, expected_sha256=None)
        response = Response(b"abcde", length=5)
        with self.assertRaisesRegex(acquisition.AcquisitionError, "Content-Length exceeds"):
            self.download(response, spec=spec, limit=4)
        self.assertFalse((self.directory / (self.spec.relative_path + ".partial")).exists())

    def test_unknown_content_length_cannot_overrun_cumulative_budget(self):
        spec = replace(self.spec, expected_bytes=None, expected_sha256=None)
        budget, record = acquisition._DownloadBudget(4, used=1), {}
        with self.assertRaisesRegex(acquisition.AcquisitionError, "exhausted"):
            acquisition._download_one(spec, self.directory, budget, time.monotonic() + 5,
                                      lambda *a, **kw: Response(b"abcde"), record)
        self.assertEqual(budget.used, 4)
        self.assertEqual(record["bytes"], 3)
        self.assertEqual((self.directory / (self.spec.relative_path + ".partial")).read_bytes(), b"abc")

    def test_existing_target_and_partial_are_never_replaced(self):
        path = self.directory / self.spec.relative_path
        path.parent.mkdir()
        path.write_bytes(b"old")
        with self.assertRaisesRegex(acquisition.AcquisitionError, "replace"):
            self.download(Response(b"abcde", length=5))
        self.assertEqual(path.read_bytes(), b"old")
        path.unlink()
        partial = path.with_name(path.name + ".partial")
        partial.write_bytes(b"prior failure")
        with self.assertRaisesRegex(acquisition.AcquisitionError, "replace"):
            self.download(Response(b"abcde", length=5))
        self.assertEqual(partial.read_bytes(), b"prior failure")

    def test_network_error_retains_acquisition_receipt_and_forbids_retry_in_place(self):
        output = self.directory / "attempt"

        def fail(*args, **kwargs):
            raise OSError("connection ended https://example.invalid/?signature=secret")

        with self.assertRaises(acquisition.AcquisitionError):
            acquisition.acquire(MANIFEST, output, opener=fail)
        receipt = json.loads((output / "acquisition.json").read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["downloaded_bytes"], 0)
        self.assertNotIn("secret", json.dumps(receipt))
        with self.assertRaises(FileExistsError):
            acquisition.acquire(MANIFEST, output, opener=fail)

    def test_expired_deadline_retains_failure_receipt_without_opening_network(self):
        output = self.directory / "expired"
        with patch.object(acquisition, "build_opener") as opener:
            with self.assertRaises(acquisition.AcquisitionError):
                acquisition.acquire(MANIFEST, output, deadline_monotonic=time.monotonic() - 1)
            opener.return_value.open.assert_not_called()
        receipt = json.loads((output / "acquisition.json").read_text())
        self.assertIn("deadline", receipt["error"]["message"])

    def test_redirect_allowlist_excludes_http_credentials_and_other_hosts(self):
        for url in ("http://huggingface.co/file", "https://evil.invalid/file",
                    "https://huggingface.co.evil.invalid/file", "https://user@huggingface.co/file",
                    "https://huggingface.co:8443/file"):
            with self.subTest(url=url), self.assertRaises(acquisition.AcquisitionError):
                acquisition._safe_remote_url(url)
        self.assertEqual(acquisition._safe_remote_url("https://cas-bridge.xethub.hf.co/file?signature=secret"),
                         "https://cas-bridge.xethub.hf.co/file")

    def test_verification_rejects_changed_and_unrecorded_local_inputs(self):
        spec = self.spec
        receipt = {"schema_version": "hadamard-model-acquisition.v1", "status": "complete",
                   "manifest_canonical_sha256": hashlib.sha256(acquisition._json_bytes(MANIFEST)).hexdigest(),
                   "downloaded_bytes": 5,
                   "files": [{"path": spec.relative_path, "status": "complete", "url": spec.url,
                              "repo": spec.repo, "revision": spec.revision, "filename": spec.filename,
                              "kind": spec.kind, "bytes": 5, "sha256": spec.expected_sha256}]}
        target = self.directory / spec.relative_path
        target.parent.mkdir()
        target.write_bytes(b"abcde")
        (self.directory / "acquisition.json").write_text(json.dumps(receipt))
        with patch.object(acquisition, "allowed_artifacts", return_value=(spec,)):
            self.assertEqual(acquisition.verify_acquisition(MANIFEST, self.directory)["status"], "complete")
            target.write_bytes(b"ABCDE")
            with self.assertRaisesRegex(acquisition.AcquisitionError, "no longer matches"):
                acquisition.verify_acquisition(MANIFEST, self.directory)
            target.write_bytes(b"abcde")
            (target.parent / "unrecorded.py").write_text("extra input")
            with self.assertRaisesRegex(acquisition.AcquisitionError, "unrecorded"):
                acquisition.verify_acquisition(MANIFEST, self.directory)


class FixedTokenizer:
    def __init__(self):
        self.calls = []

    def encode(self, text, *, add_special_tokens, truncation):
        self.calls.append((text, add_special_tokens, truncation))
        # Deterministic independent fixture: all non-short articles are long.
        return list(range(3 if "too short" in text else 650))


def source_rows(prefix, count, *, short_first=False):
    rows = ["ignored introduction"]
    if short_first:
        rows += [f"= {prefix} too short =", "too short"]
    for index in range(count):
        rows += [f" = {prefix} article {index} = \n", "body", "== subsection ==", "end\n"]
    return rows


class SelectedInputTests(unittest.TestCase):
    def rows(self):
        return {"validation": source_rows("dev", 3, short_first=True),
                "train": source_rows("timing", 5), "test": source_rows("quality", 33)}

    def test_first_eligible_prefixes_have_independent_content_and_token_identities(self):
        tokenizer = FixedTokenizer()
        roles, counts = acquisition.select_from_rows(MANIFEST, self.rows(), tokenizer)
        self.assertEqual([len(roles[role]) for role in acquisition._ROLES], [2, 4, 32])
        first = roles["development"][0]
        article = "\n".join(source_rows("dev", 3, short_first=True)[3:7])
        self.assertEqual(first["start_row"], 3)
        self.assertEqual(first["text_sha256"], hashlib.sha256(article.encode()).hexdigest())
        self.assertEqual(first["token_sha256"], hashlib.sha256(struct.pack("<513I", *range(513))).hexdigest())
        self.assertEqual(first["article_id"], f"{MANIFEST['dataset']['revision']}/wikitext-2-raw-v1/validation/3")
        self.assertEqual(counts["development"]["tokenized_articles"], 3)
        self.assertEqual(first["full_article_tokens"], 650)
        self.assertTrue(all(not special and not truncation for _, special, truncation in tokenizer.calls))
        self.assertEqual(len(tokenizer.calls), 39)  # one short plus the 38 fixed selections

    def test_insufficient_articles_fail_without_substituting_shorter_prefixes(self):
        rows = self.rows()
        rows["test"] = source_rows("quality", 31)
        with self.assertRaisesRegex(ContractError, "need 32 articles"):
            acquisition.select_from_rows(MANIFEST, rows, FixedTokenizer())

    def test_repeated_full_text_across_roles_is_rejected(self):
        rows = self.rows()
        rows["train"] = source_rows("dev", 5)
        with self.assertRaisesRegex(ContractError, "repeated article identity or exact text"):
            acquisition.select_from_rows(MANIFEST, rows, FixedTokenizer())

    def test_public_receipt_has_no_tokens_and_failed_selection_retains_its_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts, selected = root / "artifacts", root / "selection"
            artifacts.mkdir()
            (artifacts / "acquisition.json").write_text("fixture acquisition\n")
            rows = self.rows()
            fake_acquisition = {"files": [{"path": "model/tokenizer.json", "bytes": 3,
                                          "sha256": "a" * 64, "url": "https://huggingface.co/pinned"}]}
            with patch.object(acquisition, "verify_acquisition", return_value=fake_acquisition):
                receipt = acquisition.select_roles(
                    MANIFEST, artifacts, selected, tokenizer=FixedTokenizer(),
                    row_reader=lambda path: rows[path.name.split("-")[0]])
            self.assertNotIn("token_ids", json.dumps(receipt))
            self.assertEqual(receipt["role_disjointness"], "passed")
            self.assertEqual(receipt["model_calls"], 0)
            for role in acquisition._ROLES:
                record = receipt["local_token_files"][role]
                content = (selected / record["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(content).hexdigest(), record["sha256"])
                private = json.loads(content)
                self.assertEqual(private["records"][0]["token_ids"],
                                 list(range(MANIFEST["dataset"]["roles"][role]["tokens_per_article"])))
            failed = root / "failed-selection"
            with self.assertRaises(acquisition.AcquisitionError):
                acquisition.select_roles(MANIFEST, root / "missing", failed, tokenizer=FixedTokenizer())
            self.assertEqual(json.loads((failed / "selection.json").read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
