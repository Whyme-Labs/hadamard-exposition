"""Run the unchanged HTTPS meter and pip in one identity-observed process."""
import json
from pathlib import Path
import resource
import runpy
import sys
import time
import traceback

from benchmarks.campaign_guard import sha256_file, source_hashes, write_json
from benchmarks.qualify import _publish_worker_identity

output, meter = map(Path, sys.argv[1:3])
arguments = sys.argv[3:]
started = time.monotonic()
before = source_hashes()
helpers = {str(p): sha256_file(p) for p in (Path(__file__), meter)}
receipt = {"status": "failed", "worker_identity": _publish_worker_identity(output),
           "source_sha256_before": before, "helper_sha256_before": helpers,
           "model_or_dataset_accessed": False}
exit_code = 1
try:
    sys.argv = [str(meter), str(output / "transfer.json"), *arguments]
    try:
        runpy.run_path(str(meter), run_name="__main__")
        exit_code = 0
    except SystemExit as error:
        exit_code = error.code if isinstance(error.code, int) else (0 if error.code is None else 1)
    transfer = json.loads((output / "transfer.json").read_text())
    if exit_code != 0 or transfer["exit_code"] != 0:
        raise RuntimeError("The metered installer failed; retain the attempt and log")
    receipt["status"] = "passed"
except Exception as error:
    receipt["error"] = {"type": type(error).__name__, "message": str(error)}
    traceback.print_exc()
finally:
    receipt["finalization_errors"] = []
    for key, observe in (("source_sha256_after", source_hashes),
                         ("helper_sha256_after", lambda: {p: sha256_file(Path(p)) for p in helpers})):
        try:
            receipt[key] = observe()
        except Exception as error:
            receipt[key] = None
            receipt["finalization_errors"].append({"observation": key, "type": type(error).__name__,
                                                    "message": str(error)})
    receipt["inputs_unchanged"] = (receipt["source_sha256_after"] == before
                                  and receipt["helper_sha256_after"] == helpers)
    if not receipt["inputs_unchanged"] or receipt["finalization_errors"]:
        receipt["status"] = "failed"
    receipt["installer_exit_code"] = exit_code
    receipt["elapsed_seconds"] = time.monotonic() - started
    receipt["peak_worker_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    write_json(output / "worker-result.json", receipt)
raise SystemExit(0 if receipt["status"] == "passed" else 1)
