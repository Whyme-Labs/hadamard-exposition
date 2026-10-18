"""Verify the published recovery records using only retained files and stdlib."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = args.repo.resolve()
base = root / "validation/2026-10-18-environment-recovery"
sys.path.insert(0, str(root))
from benchmarks.run_model import verify_review_commit


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


payloads, qualifications = {}, {}
result = {"schema_version": "hadamard-recovery-verification.v1", "status": "passed",
    "scope": "Read-only verification of retained qualification, source, archive, task and package identities. No experiment rerun.",
    "verifier_sha256": sha(Path(__file__).read_bytes()), "archives": {}, "tasks": {}, "install_reports": {},
    "campaign_ready": False, "fixture_cleanup_guarantee_established": False}
for phase in ("dependencies", "offline"):
    folder = base / phase
    inventory = json.loads((folder / "inventory.json").read_text())
    archive_path = folder / "raw-evidence.tar.gz"
    data = archive_path.read_bytes()
    require(len(data) == inventory["archive"]["bytes"] and sha(data) == inventory["archive"]["sha256"],
            "Archive bytes differ from inventory")
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        require(len(members) == len(inventory["members"]) == inventory["archive"]["member_count"], "Member counts differ")
        require(len({m.name for m in members}) == len(members) and all(m.isfile() for m in members),
                "Archive has duplicate or nonregular members")
        data_by_name = {m.name: archive.extractfile(m).read() for m in members}
    require(set(data_by_name) == {m["archive_path"] for m in inventory["members"]}, "Member sets differ")
    for member in inventory["members"]:
        data = data_by_name[member["archive_path"]]
        require(len(data) == member["bytes"] and sha(data) == member["sha256"], "A member hash differs")
    for name, original in inventory["separate_copies"].items():
        archive_name = "qualification.json" if name == "qualification.json" else "campaign-preflight/preflight.json"
        require((folder / name).read_bytes() == data_by_name[archive_name], "Standalone copy differs")
    require(inventory["snapshot_script_sha256"] == sha((base / "sources/snapshot-evidence.py").read_bytes()),
            "Snapshot helper changed")
    payloads[phase] = data_by_name
    qualification = json.loads(data_by_name["qualification.json"])
    qualifications[phase] = qualification
    require(qualification["phase"] == ("dependencies" if phase == "dependencies" else "suite")
            and qualification["status"] == "passed" and qualification["inputs_unchanged"], "Qualification did not pass")
    require(qualification["source_sha256_before"] == qualification["source_sha256_after"], "Sources changed")
    require(qualification["helper_sha256_before"] == qualification["helper_sha256_after"], "Helpers changed")
    require(0 < qualification["elapsed_seconds"] < qualification["deadline_seconds"]
            == (600 if phase == "dependencies" else 180), "Qualification deadline differs")
    require(qualification["memory_limit_bytes"] == 1024**3 and qualification["model_calls"] == 0
            and qualification["model_data_download_bytes"] == 0 and qualification["campaign_ready"] is False,
            "Qualification scope differs")
    for name, expected in qualification["helper_sha256_after"].items():
        require(sha((base / "sources" / name).read_bytes()) == expected, "A qualified helper differs")
    for relative, expected in qualification["source_sha256_after"].items():
        require(sha((root / relative).read_bytes()) == expected, "A qualified benchmark source differs")
    for name, summary in qualification["tasks"].items():
        prefix = summary["path"] + "/"
        task = json.loads(data_by_name[prefix + "task-receipt.json"])
        worker = json.loads(data_by_name[prefix + "worker-result.json"])
        identity = json.loads(data_by_name[prefix + "worker-identity.json"])
        require(task["status"] == worker["status"] == summary["status"] == "passed"
                and task["returncode"] == 0 and task["stopped_for"] is None and task["monitor_error"] is None,
                "A task failed or stopped")
        require(task["worker"] == worker and task["worker_identity"] == worker["worker_identity"] == identity,
                "Task/worker identity differs")
        require(task["worker_result_sha256"] == sha(data_by_name[prefix + "worker-result.json"])
                and task["worker_identity_sha256"] == sha(data_by_name[prefix + "worker-identity.json"]),
                "Task evidence hashes differ")
        require(worker["source_sha256_before"] == worker["source_sha256_after"] == qualification["source_sha256_after"]
                and worker["inputs_unchanged"], "Worker source binding differs")
        require(task["valid_rss_samples"] > 0 and 0 < task["sampled_peak_worker_rss_bytes"] <= 1024**3
                and 0 < worker["peak_worker_rss_bytes"] <= 1024**3, "RSS evidence is missing or excessive")
        result["tasks"][phase + "/" + name] = {"status": "passed", "valid_rss_samples": task["valid_rss_samples"]}
    result["archives"][phase] = inventory["archive"]

dep, suite = qualifications["dependencies"], qualifications["offline"]
require(dep["source_sha256_after"] == suite["source_sha256_after"], "Phases used different benchmark sources")
review = json.loads((root / "validation/2026-10-17-model-campaign/review.json").read_text())
verify_review_commit(review, dep["source_sha256_after"])
result["source_review"] = {"status": "passed", "commit": review["reviewed_commit"], "tree": review["reviewed_tree"]}
require(suite["dependency_qualification"]["sha256"] == sha(payloads["dependencies"]["qualification.json"]),
        "Suite is not bound to the retained dependency qualification")
require(suite["tests"] == {"run": 135, "failures": 0, "errors": 0, "skipped": 0}
        and suite["runtime_installed_closure"]["installed_packages"] == 21, "Suite or runtime closure scope differs")
lock_bytes = (root / "benchmarks/model-dependencies-v1.json").read_bytes()
require(sha(lock_bytes) == dep["lock_sha256"] == suite["lock_sha256"], "Wheel lock differs")
lock = json.loads(lock_bytes)
received = 0
for name in ("converter", "runtime"):
    expected = {p["name"]: p for p in lock["environments"][name]["packages"]}
    report = json.loads(payloads["dependencies"][f"{name}-install-report.json"])
    actual = {re.sub(r"[-_.]+", "-", p["metadata"]["name"]).lower(): p for p in report["install"]}
    require(len(actual) == len(report["install"]) and actual.keys() == expected.keys(), "Installed package set differs")
    for package, item in actual.items():
        require(item["metadata"]["version"] == expected[package]["version"]
                and item["download_info"]["url"] == expected[package]["url"]
                and item["download_info"]["archive_info"]["hashes"]["sha256"] == expected[package]["sha256"],
                "Installed package identity differs")
    transfer = json.loads(payloads["dependencies"][f"install-{name}-1/transfer.json"])
    remaining = 1024**3 - dep["prior_observed_https_bytes"] - received
    require(type(transfer["https_received_bytes"]) is int and 0 <= transfer["https_received_bytes"] <= remaining
            and transfer["https_receive_byte_limit"] == remaining
            and transfer["deadline_monotonic"] == dep["deadline_monotonic"] and transfer["exit_code"] == 0
            and transfer["python_executable"] == str(Path(dep["venvs_root"]) / name / "bin/python"),
            "Transfer receipt differs from its intended bounded attempt")
    received += transfer["https_received_bytes"]
    result["install_reports"][name] = {"status": "passed", "packages": len(actual), "exact_versions_urls_and_sha256": True}
require(dep["https_accounting_complete"] and received == dep["known_effort_https_bytes"] == dep["effort_https_received_bytes"]
        and received + dep["prior_observed_https_bytes"] == dep["combined_https_received_bytes"] < 1024**3,
        "Cumulative transfer accounting differs")
result["fresh_effort_https_bytes"] = received
result["combined_https_bytes_including_secondary_prior_observation"] = dep["combined_https_received_bytes"]
preflight = json.loads(payloads["offline"]["campaign-preflight/preflight.json"])
require(preflight == suite["campaign_preflight"] and preflight["inputs_unchanged"]
        and preflight["status"] == "blocked" and preflight["errors"] == [
            "Conservative available memory is below the required 6 GiB or cannot be established"],
        "Campaign preflight outcome or binding differs")
result["campaign_preflight"] = {"status": "blocked", "available_memory_bytes":
    preflight["environment"]["memory_availability_estimate"]["estimated_available_bytes"], "required_memory_bytes": 6 * 1024**3}
with args.output.open("x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps({"status": "passed", "archive_members": sum(v["member_count"] for v in result["archives"].values()),
                  "tasks": len(result["tasks"]), "tests": suite["tests"], "campaign_ready": False}))
