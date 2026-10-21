# V2 release acceptance, 21 October 2026

The local submission candidate is complete. The public publication and authorized review gates remain open in issue 11.

## Completed scope

The original v2 manuscript and registered experiment are unchanged. A separate all-Hadamard addendum generalizes the counterexample from the Sylvester construction to every real Hadamard matrix of a given order. Its proof uses the exact sign-pair count n/4 from three mutually orthogonal rows. It also preserves the linear-layer corollary with both operands quantized. It is conditional on the existence of H, does not solve the conjecture and makes no literature-priority claim.

The complete package contains 49 files, a 10-page main article, a 3-page addendum, standalone HTML, the exact calculator, all 7,600 raw measurements, source code, licenses and submission metadata. Its ZIP SHA-256 is `6074fcc3745e756765bd676be051d04b72c3c29314dd6094b64ef555af29b044`. The exact archive and full build receipt are delivered as conversation attachments. The source code here rebuilds a separately labeled candidate; timestamps and PDF metadata mean a new execution need not have the same ZIP hash.

`milestone.json` records the executed environment, source identities, archive identity, test scope, raw-data digest and public-state boundaries.

## Standards self-review

All computation in this continuation ran in the assistant environment. No home or Blacksmith runner was used. Publication is not conflated with execution. The builder copies an explicit allowlist, rejects symlinks and unsafe source paths, preserves existing output directories, checks frozen scientific inputs, runs the unmodified study in the isolated payload and emits no accepted ZIP on failed validation. Extraction checks bind the delivered archive back to every payload byte. Eight boundary tests pass.

The prior result verifier accepted a deliberately false mean-delta field after its checksum was updated. The new separate auditor reconstructs all 589 scalar summary fields, including deltas, extrema and Hadamard-versus-Haar intervals. Its negative controls cover malformed/duplicate records, source changes, missing hashes, false primary copies and corrupted exact matrices. Old evidence and the old verifier remain unchanged.

## Specification self-review

The v2 package meets the local release requirement. All 47 mathematical, numerical and audit tests pass. The original 672 Sylvester witnesses and 1,280 all-Hadamard witnesses pass. The unmodified 100-seed study returns all 7,600 measurements and reproduces the recorded primary result. This rerun is not a third independent dataset.

The extracted ZIP independently passes all 47 tests, all 48 listed checksums, the raw-data audit and the actual embedded JavaScript verification. Desktop and mobile checks pass without document overflow or page errors. The main PDF and addendum were rendered and visually inspected. These are assistant self-review and automated checks, not external peer review, learner testing or committee selection.

## Rebuild

With Python, NumPy 2.3.5, Node.js, Pandoc, Playwright and Chromium available:

```bash
python -m unittest discover -s release -p 'test_v2.py' -v
python release/build_v2.py --output build/v2-candidate-new
```

Use a new output path. Reading the delivered HTML/PDF and running numerical tests does not require Pandoc, Playwright or Chromium. The numerical dependency is only `requirements-v2.txt`.

## Remaining gate

A separately authorized public mirror still needs to be created and its fixed commit and independently observed publication time recorded. The current connector exposes file/branch/PR operations but no repository-creation operation; the connected browser surface is read-only. The current private research repository must not be made public as a workaround. After publication, submit the exact candidate for authorized content review. No additional license approval is needed.
