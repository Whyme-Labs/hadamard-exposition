from pathlib import Path
import json
import resource
import sys
import time
import traceback
import unittest

from benchmarks.qualify import _publish_worker_identity
from benchmarks.campaign_guard import ROOT, sha256_file, source_hashes, write_json

output = Path(sys.argv[1])
identity = _publish_worker_identity(output)
sys.path.insert(0, str(ROOT / "benchmarks"))
started = time.monotonic()
before = source_hashes()
wrapper_sha256 = sha256_file(Path(__file__))
receipt = {"status": "failed", "worker_identity": identity,
           "source_sha256_before": before, "wrapper_sha256": wrapper_sha256,
           "model_or_dataset_accessed": False,
           "scope": "Offline tests, including declared child fixtures; no pretrained campaign result."}
try:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "benchmarks"), pattern="test_*.py")
    tests = unittest.TextTestRunner(verbosity=2).run(suite)
    receipt["tests"] = {"run": tests.testsRun, "failures": len(tests.failures),
                        "errors": len(tests.errors), "skipped": len(tests.skipped)}
    receipt["status"] = "passed" if tests.wasSuccessful() and not tests.skipped else "failed"
except Exception as error:
    receipt["error"] = {"type": type(error).__name__, "message": str(error)}
    traceback.print_exc()
receipt["source_sha256_after"] = source_hashes()
receipt["inputs_unchanged"] = before == receipt["source_sha256_after"] and wrapper_sha256 == sha256_file(Path(__file__))
if not receipt["inputs_unchanged"]:
    receipt["status"] = "failed"
receipt["elapsed_seconds"] = time.monotonic() - started
receipt["peak_worker_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
write_json(output / "worker-result.json", receipt)
raise SystemExit(0 if receipt["status"] == "passed" else 1)
