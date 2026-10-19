"""Synthetic input-format controls; never load the checkpoint or saved traces."""

import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from audit_io import (
    ARTICLE_RECORDS, MAX_HEADER_BYTES, MLP, QKV,
    _array_identity, _cases_from_payloads, _read_archive_members,
    load_checkpoint, parse_selected_safetensors, sha256_file, strict_json,
)


def safetensors_bytes(header, data):
    encoded = json.dumps(header, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 8)
    return struct.pack("<Q", len(encoded)) + encoded + data


def basic_header(dtype="F32", shape=None, offsets=None):
    return {"x": {"dtype": dtype, "shape": [2] if shape is None else shape,
                   "data_offsets": [0, 8] if offsets is None else offsets}}


class JsonAndHashTests(unittest.TestCase):
    def test_strict_json_preserves_valid_values_and_rejects_ambiguity(self):
        self.assertEqual(strict_json(b'{"a":[1,-2,0.5],"b":true}'), {"a": [1, -2, 0.5], "b": True})
        for raw in ['{"a":1,"a":2}', '{"a":{"b":1,"b":2}}', '[NaN]', '[Infinity]', '[-Infinity]', '[1e999]']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    strict_json(raw)
        with self.assertRaises(UnicodeDecodeError):
            strict_json(b'"\xff"')

    def test_hash_identity_and_nonregular_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input"
            path.write_bytes(b"abc")
            self.assertEqual(sha256_file(path), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
            path.write_bytes(b"abcd")
            self.assertEqual(sha256_file(path), hashlib.sha256(b"abcd").hexdigest())
            link = Path(directory) / "link"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                sha256_file(link)


class SafetensorsTests(unittest.TestCase):
    def parse(self, content, expected=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.safetensors"
            path.write_bytes(content)
            return parse_selected_safetensors(path, {"x": (2,)} if expected is None else expected)

    def test_exact_f16_bf16_f32_conversions_and_receipt_identities(self):
        half = np.array([[1, -0.0, 2 ** -24], [65504, -3, 2.5]], dtype="<f2").tobytes()
        brain = np.array([0x8000, 0x3F00, 0x0001, 0x7F7F], dtype="<u2").tobytes()
        single = np.array([-0.0, 1.25], dtype="<f4").tobytes()
        unused = np.array([37], dtype="<i8").tobytes()
        entries = [("weight", "F16", [2, 3], half), ("brain", "BF16", [4], brain),
                   ("bias", "F32", [2], single), ("unused", "I64", [1], unused)]
        header, data = {"__metadata__": {"format": "pt"}}, b""
        for name, dtype, shape, raw in entries:
            header[name] = {"dtype": dtype, "shape": shape, "data_offsets": [len(data), len(data) + len(raw)]}
            data += raw
        content = safetensors_bytes(header, data)
        tensors, receipt = self.parse(content, {"weight": (2, 3), "brain": (4,), "bias": (2,)})
        self.assertEqual(set(tensors), {"weight", "brain", "bias"})
        np.testing.assert_array_equal(tensors["weight"], [[1, -0.0, 2 ** -24], [65504, -3, 2.5]])
        np.testing.assert_array_equal(tensors["brain"].view(np.uint32), [0x80000000, 0x3F000000, 0x00010000, 0x7F7F0000])
        np.testing.assert_array_equal(tensors["bias"].view(np.uint32), [0x80000000, 0x3FA00000])
        for name, dtype, shape, raw in entries[:3]:
            self.assertEqual(tensors[name].dtype, np.dtype(np.float32))
            self.assertTrue(tensors[name].flags.c_contiguous)
            self.assertEqual(receipt["selected_tensors"][name]["stored_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(receipt["selected_tensors"][name]["derived_fp32"], _array_identity(tensors[name]))
        self.assertEqual(receipt["file"], {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
        self.assertEqual(receipt["declared_tensor_count"], 4)
        header_size = struct.unpack("<Q", content[:8])[0]
        self.assertEqual(receipt["header_sha256"], hashlib.sha256(content[8:8 + header_size]).hexdigest())

    def test_header_length_duplicate_keys_and_nonobject_rejected(self):
        examples = [b"short", struct.pack("<Q", MAX_HEADER_BYTES + 1), struct.pack("<Q", 100) + b"{}",
                    struct.pack("<Q", 2) + b"[]"]
        duplicate = b'{"x":{"dtype":"F32","dtype":"F16","shape":[2],"data_offsets":[0,8]}}'
        examples.append(struct.pack("<Q", len(duplicate)) + duplicate + bytes(8))
        prefixed = b" " + json.dumps(basic_header(), separators=(",", ":")).encode()
        examples.append(struct.pack("<Q", len(prefixed)) + prefixed + bytes(8))
        for content in examples:
            with self.subTest(content=content[:16]):
                with self.assertRaises(ValueError):
                    self.parse(content)

    def test_offsets_shapes_holes_overlaps_and_trailing_data_rejected(self):
        malformed = [basic_header(offsets=[-1, 7]), basic_header(offsets=[8, 0]),
                     basic_header(offsets=[0, 9]), basic_header(offsets=[True, 8]),
                     basic_header(shape=[3]), basic_header(shape=[True, 2]),
                     basic_header(shape=[-2]), basic_header(dtype="UNKNOWN")]
        overlap = basic_header()
        overlap["y"] = {"dtype": "F32", "shape": [1], "data_offsets": [4, 8]}
        malformed.append(overlap)
        for header in malformed:
            with self.subTest(header=header):
                with self.assertRaises(ValueError):
                    self.parse(safetensors_bytes(header, bytes(8)))
        hole = basic_header(offsets=[4, 12])
        with self.assertRaisesRegex(ValueError, "hole"):
            self.parse(safetensors_bytes(hole, bytes(12)))
        with self.assertRaisesRegex(ValueError, "exact data buffer"):
            self.parse(safetensors_bytes(basic_header(), bytes(9)))
        with self.assertRaisesRegex(ValueError, "shape mismatch"):
            self.parse(safetensors_bytes(basic_header(), bytes(8)), {"x": (1, 2)})
        with self.assertRaisesRegex(ValueError, "absent"):
            self.parse(safetensors_bytes(basic_header(), bytes(8)), {"missing": (2,)})

    def test_empty_tensors_are_permitted_only_at_interval_boundaries(self):
        for boundary in (0, 8):
            header = basic_header()
            header["empty"] = {"dtype": "F32", "shape": [0], "data_offsets": [boundary, boundary]}
            tensors, receipt = self.parse(safetensors_bytes(header, bytes(8)), {"x": (2,), "empty": (0,)})
            self.assertEqual(tensors["empty"].shape, (0,))
            self.assertEqual(receipt["selected_tensors"]["empty"]["stored_bytes"], 0)
        header = basic_header()
        header["empty"] = {"dtype": "F32", "shape": [0], "data_offsets": [4, 4]}
        with self.assertRaisesRegex(ValueError, "overlap or leave a hole"):
            self.parse(safetensors_bytes(header, bytes(8)))
        header["empty"]["data_offsets"] = [12, 12]
        with self.assertRaisesRegex(ValueError, "offsets or byte count mismatch"):
            self.parse(safetensors_bytes(header, bytes(8)))

    def test_selected_dtype_and_nonfinite_values_rejected(self):
        with self.assertRaisesRegex(ValueError, "selected tensor must"):
            self.parse(safetensors_bytes(basic_header(dtype="I32"), bytes(8)))
        for dtype, raw in [("F32", np.array([1, np.inf], dtype="<f4").tobytes()),
                           ("F16", np.array([1, np.nan], dtype="<f2").tobytes()),
                           ("BF16", np.array([0x3F80, 0xFF80], dtype="<u2").tobytes())]:
            with self.subTest(dtype=dtype):
                header = basic_header(dtype=dtype, offsets=[0, len(raw)])
                with self.assertRaisesRegex(ValueError, "nonfinite"):
                    self.parse(safetensors_bytes(header, raw))

    def test_bound_checkpoint_rejects_wrong_identity_before_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.safetensors"
            path.write_bytes(safetensors_bytes(basic_header(), bytes(8)))
            with patch("audit_io.parse_selected_safetensors") as parser:
                with self.assertRaisesRegex(ValueError, "pinned complete input"):
                    load_checkpoint(path)
                parser.assert_not_called()


class ArchiveTests(unittest.TestCase):
    def archive(self, entries):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for name, raw, kind in entries:
                info = tarfile.TarInfo(name)
                info.type = kind
                info.size = len(raw) if kind == tarfile.REGTYPE else 0
                if kind == tarfile.SYMTYPE:
                    info.linkname = "../outside"
                archive.addfile(info, io.BytesIO(raw) if kind == tarfile.REGTYPE else None)
        return buffer.getvalue()

    def read(self, content, inventory):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.tar.gz"
            path.write_bytes(content)
            return _read_archive_members(path, inventory)

    def test_exact_members_content_and_safe_types(self):
        entries = [("a.json", b"{}", tarfile.REGTYPE), ("worker/log", b"ok", tarfile.REGTYPE)]
        inventory = [{"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw, _ in entries]
        self.assertEqual(self.read(self.archive(entries), inventory), {"a.json": b"{}", "worker/log": b"ok"})
        for altered in [entries[:1], entries + [entries[0]],
                        [("a.json", b"[]", tarfile.REGTYPE), entries[1]],
                        [("a.json", b"", tarfile.SYMTYPE), entries[1]]]:
            with self.subTest(entries=altered):
                with self.assertRaises(ValueError):
                    self.read(self.archive(altered), inventory)
        unsafe = [{"path": "../outside", "bytes": 0, "sha256": hashlib.sha256(b"").hexdigest()}]
        with self.assertRaisesRegex(ValueError, "unsafe"):
            self.read(self.archive([("../outside", b"", tarfile.REGTYPE)]), unsafe)


def synthetic_trace(mutate_arrays=None):
    """Use public article metadata and newly generated toy arrays only."""
    worker, payloads = {"records": []}, {}
    for article_index, article in enumerate(ARTICLE_RECORDS):
        all_arrays, cases = {}, {}
        for mode, sequence in (("full", 513), ("cached", 1)):
            events = [{"label": f"toy:{i}", "dtype": "float32", "original_shape": [1, sequence, 1],
                       "retained_shape": [1, 1, 1]} for i in range(160)]
            for module, width, event in ((QKV, 1536, 15), (MLP, 2048, 23)):
                for offset, suffix, features in ((0, ":input", 512), (1, ":output", width)):
                    events[event + offset] = {"label": module + suffix, "dtype": "float32",
                                              "original_shape": [1, sequence, features],
                                              "retained_shape": [1, 1, features]}
            arrays = {event["label"]: np.zeros(event["retained_shape"], dtype=np.float32) for event in events}
            for module in (QKV, MLP):
                arrays[module + ":input"][..., 1] = article_index + 1
                arrays[module + ":output"][..., 0] = 1.0 if mode == "full" else 1.25
            if mutate_arrays is not None:
                mutate_arrays(article_index, mode, arrays)
            stream = io.BytesIO()
            np.savez(stream, **arrays)
            raw = stream.getvalue()
            name = f"article{article_index}.{mode}.trace.npz"
            payloads["worker/" + name] = raw
            cases[mode] = {"trace": {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "events": events}}
            all_arrays[mode] = arrays
        comparisons = [{"label": label, "actual": _array_identity(all_arrays["cached"][label]),
                        "expected": _array_identity(all_arrays["full"][label])} for label in all_arrays["full"]]
        worker["records"].append({"article": dict(article), "cases": cases, "full_last_vs_cached_events": comparisons})
    return worker, payloads


class TraceCaseTests(unittest.TestCase):
    def test_fixed_case_order_vectors_and_provenance(self):
        worker, payloads = synthetic_trace()
        cases = _cases_from_payloads(worker, payloads)
        self.assertEqual([case["id"] for case in cases], ["article0_qkv", "article0_mlp", "article1_qkv", "article1_mlp"])
        for case, width in zip(cases, [1536, 2048, 1536, 2048]):
            self.assertEqual(case["input"].shape, (512,))
            self.assertEqual(case["full_output"].shape, (width,))
            self.assertEqual(case["cached_output"].shape, (width,))
            self.assertEqual(case["input"].dtype, np.dtype(np.float32))
            self.assertEqual(case["provenance"]["events"]["full"][0]["original_shape"], [1, 513, 512])
            self.assertEqual(case["provenance"]["events"]["cached"][0]["original_shape"], [1, 1, 512])

    def test_article_event_shape_and_recorded_array_identity_rejections(self):
        worker, payloads = synthetic_trace()
        mutations = [
            lambda w: w["records"][0]["article"].update(token_sha256="0" * 64),
            lambda w: w["records"][0]["cases"]["full"]["trace"]["events"][15].update(original_shape=[1, 512, 512]),
            lambda w: w["records"][0]["full_last_vs_cached_events"][15]["expected"].update(array_sha256="0" * 64),
            lambda w: w["records"][0]["cases"]["cached"]["trace"].update(path="article1.cached.trace.npz"),
        ]
        for mutation in mutations:
            altered = copy.deepcopy(worker)
            mutation(altered)
            with self.assertRaises(ValueError):
                _cases_from_payloads(altered, payloads)

    def test_nonfinite_wrong_dtype_and_signed_zero_input_difference_rejected(self):
        def nonfinite(article, mode, arrays):
            if article == 0 and mode == "full":
                arrays[QKV + ":output"][0, 0, 0] = np.inf

        def wrong_dtype(article, mode, arrays):
            if article == 0 and mode == "full":
                arrays[QKV + ":output"] = arrays[QKV + ":output"].astype(np.float64)

        def different_zero_sign(article, mode, arrays):
            if article == 0 and mode == "cached":
                arrays[QKV + ":input"][0, 0, 0] = -0.0

        for mutation in (nonfinite, wrong_dtype, different_zero_sign):
            with self.subTest(mutation=mutation.__name__):
                worker, payloads = synthetic_trace(mutation)
                with self.assertRaises(ValueError):
                    _cases_from_payloads(worker, payloads)

    def test_npz_byte_identity_and_complete_key_order_rejected(self):
        worker, payloads = synthetic_trace()
        altered = dict(payloads)
        name = "worker/article0.full.trace.npz"
        altered[name] = altered[name][:-1] + bytes([altered[name][-1] ^ 1])
        with self.assertRaisesRegex(ValueError, "NPZ file identity"):
            _cases_from_payloads(worker, altered)
        worker["records"][0]["cases"]["full"]["trace"]["events"][0]["label"] = "unexpected"
        with self.assertRaisesRegex(ValueError, "key order"):
            _cases_from_payloads(worker, payloads)


if __name__ == "__main__":
    unittest.main()
