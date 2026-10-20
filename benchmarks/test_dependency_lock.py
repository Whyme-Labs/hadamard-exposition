"""Offline checks for source integrity, active dependency closure and isolation."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

try:
    from . import dependency_lock as dependencies
except ImportError:
    import dependency_lock as dependencies


ENVIRONMENT = {"python_full_version": "3.12.14", "python_version": "3.12", "sys_platform": "linux",
               "platform_machine": "x86_64", "implementation_name": "cpython"}


def distribution(name, version="1.0", *, requires=(), extras=(), hash_value="a" * 64):
    normalized = dependencies.canonicalize_name(name).replace("-", "_")
    return {"metadata": {"name": name, "version": version, "requires_dist": list(requires),
                          "requires_python": ">=3.9"}, "requested": True,
            "requested_extras": list(extras),
            "download_info": {"url": f"https://files.pythonhosted.org/packages/{normalized}-{version}-py3-none-any.whl",
                              "archive_info": {"hashes": {"sha256": hash_value}}}}


def report(*packages):
    return {"version": "1", "pip_version": "26.2.1", "install": list(packages), "environment": ENVIRONMENT.copy()}


class DependencyLockTests(unittest.TestCase):
    def test_rejects_missing_hash_untrusted_source_sdist_and_filename_mismatch(self):
        base = distribution("example")
        mutations = [lambda item: item["download_info"]["archive_info"].clear(),
                     lambda item: item["download_info"].update(url="https://example.invalid/example-1.0-py3-none-any.whl"),
                     lambda item: item["download_info"].update(url="https://files.pythonhosted.org/example-1.0.tar.gz"),
                     lambda item: item["download_info"].update(url="https://files.pythonhosted.org/wrong-1.0-py3-none-any.whl"),
                     lambda item: item["download_info"].update(url="https://user:secret@files.pythonhosted.org/example-1.0-py3-none-any.whl")]
        for mutate in mutations:
            candidate = deepcopy(base)
            mutate(candidate)
            with self.subTest(candidate=candidate), self.assertRaises(dependencies.DependencyLockError):
                dependencies.from_pip_report(report(candidate), "fixture", {"example": "1.0"})

    def test_exact_frozen_versions_and_duplicate_normalized_names(self):
        with self.assertRaisesRegex(dependencies.DependencyLockError, "frozen version"):
            dependencies.from_pip_report(report(distribution("sympy", "1.14.0")), "converter", {"sympy": "1.13.1"})
        with self.assertRaisesRegex(dependencies.DependencyLockError, "duplicate"):
            dependencies.from_pip_report(report(distribution("some_name"), distribution("some-name")), "fixture", {})

    def test_missing_and_incompatible_active_dependencies_fail(self):
        parent = distribution("parent", requires=["child>=2"])
        for packages in ((parent,), (parent, distribution("child", "1.0"))):
            with self.subTest(packages=packages), self.assertRaises(dependencies.DependencyLockError):
                dependencies.from_pip_report(report(*packages), "fixture", {})

    def test_transitive_extras_are_activated_to_a_fixpoint(self):
        packages = [distribution("parent", requires=["child[http]>=1"]),
                    distribution("child", requires=['transport[secure]>=1; extra == "http"']),
                    distribution("transport", requires=['cert>=1; extra == "secure"'])]
        with self.assertRaisesRegex(dependencies.DependencyLockError, "cert"):
            dependencies.from_pip_report(report(*packages), "fixture", {})
        packages.append(distribution("cert"))
        lock = dependencies.from_pip_report(report(*packages), "fixture", {})
        self.assertEqual(lock["dependency_closure"]["activated_extras"], {"child": ["http"], "transport": ["secure"]})
        self.assertEqual(lock["dependency_closure"]["active_requirement_edges"], 3)

    def test_inactive_platform_and_optional_dependencies_are_excluded(self):
        package = distribution("example", requires=['windows-only; sys_platform == "win32"',
                                                    'optional; extra == "test"'])
        lock = dependencies.from_pip_report(report(package), "fixture", {})
        self.assertEqual(lock["dependency_closure"]["active_requirement_edges"], 0)

    def test_requires_python_and_missing_environment_markers_fail(self):
        package = distribution("example")
        package["metadata"]["requires_python"] = "<3.12"
        with self.assertRaisesRegex(dependencies.DependencyLockError, "does not support"):
            dependencies.from_pip_report(report(package), "fixture", {})
        incomplete = report(distribution("example"))
        incomplete["environment"].pop("python_full_version")
        with self.assertRaisesRegex(dependencies.DependencyLockError, "lacks target"):
            dependencies.from_pip_report(incomplete, "fixture", {})

    def test_installed_environment_cannot_hide_missing_extra_or_changed_packages(self):
        lock = dependencies.from_pip_report(report(distribution("example")), "fixture", {})
        self.assertEqual(dependencies.validate_environment(lock, {"example": "1.0"})["status"], "passed")
        for installed in ({}, {"example": "1.1"}, {"example": "1.0", "unrecorded": "1.0"}):
            with self.assertRaisesRegex(dependencies.DependencyLockError, "installed versions differ"):
                dependencies.validate_environment(lock, installed)

    def test_interpreter_and_wheel_abi_tags_must_match_the_installed_environment(self):
        lock = dependencies.from_pip_report(report(distribution("example")), "fixture", {})
        changed = deepcopy(lock)
        changed["python_environment"]["python_full_version"] = "3.11.0"
        with self.assertRaisesRegex(dependencies.DependencyLockError, "interpreter environment"):
            dependencies.validate_environment(changed, {"example": "1.0"})
        changed = deepcopy(lock)
        changed["packages"][0]["filename"] = "example-1.0-cp27-cp27m-win32.whl"
        with self.assertRaisesRegex(dependencies.DependencyLockError, "wheel tags"):
            dependencies.validate_environment(changed, {"example": "1.0"})

    def test_hash_requirements_bind_every_resolved_wheel(self):
        lock = dependencies.from_pip_report(report(distribution("example", requires=["child==1.0"]),
                                                   distribution("child")), "fixture", {})
        output = dependencies.write_hash_requirements(lock)
        self.assertEqual(len(output.splitlines()), 2)
        self.assertEqual(output.count("--hash=sha256:"), 2)
        self.assertTrue(output.startswith("child @ https://files.pythonhosted.org/"))

    def test_measured_wheel_hash_can_fill_missing_report_hash_without_editing_report(self):
        item = distribution("example")
        item["download_info"]["archive_info"].clear()
        original = deepcopy(item)
        with tempfile.TemporaryDirectory() as temporary:
            wheel = Path(temporary) / "example.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("example-1.0.dist-info/METADATA", "Name: example\nVersion: 1.0\n")
                archive.writestr("example/_vendor/other-2.0.dist-info/METADATA", "Name: other\nVersion: 2.0\n")
            lock = dependencies.from_pip_report(report(item), "fixture", {},
                                                wheel_files={item["download_info"]["url"]: wheel})
            entry = lock["packages"][0]
            self.assertEqual(entry["sha256"], hashlib.sha256(wheel.read_bytes()).hexdigest())
            self.assertEqual(entry["wheel_bytes"], wheel.stat().st_size)
            self.assertTrue(entry["wheel_content_verified"])
            self.assertEqual(item, original)
            item["download_info"]["archive_info"] = {"hashes": {"sha256": "0" * 64}}
            with self.assertRaisesRegex(dependencies.DependencyLockError, "differ from pip"):
                dependencies.from_pip_report(report(item), "fixture", {},
                                            wheel_files={item["download_info"]["url"]: wheel})

    def test_nested_requirements_preserve_exact_pins_and_reject_conflicts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "base.txt").write_text("numpy==2.3.5\n")
            (root / "converter.txt").write_text("-r base.txt\nsympy==1.13.1 # pinned for Torch\n")
            self.assertEqual(dependencies.read_exact_pins(root / "converter.txt"),
                             {"numpy": "2.3.5", "sympy": "1.13.1"})
            (root / "converter.txt").write_text("-r base.txt\nnumpy==1.0\n")
            with self.assertRaisesRegex(dependencies.DependencyLockError, "conflicting"):
                dependencies.read_exact_pins(root / "converter.txt")


if __name__ == "__main__":
    unittest.main()
