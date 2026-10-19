# Operator audit: preparation permission correction 001

Status: prospective correction, 19 October 2026. Publish this correction and both independent review axes before the replacement preparation. The arithmetic preregistration remains commit `3a4169b255c6bf9ed64caf49057397a5306cc0b5`, tree `71a1415defd61dcd9507da9d5090f63189a269ec`, with the unchanged 42-source map `18389440bb75da613a20c7e1b7eaf698f8787841ea2ad90c3db64629656cec24`. This document applies the failed-launch correction clause in [operator arithmetic version 1](operator-arithmetic-v1.md).

## Observed failure and diagnosis

The first preparation ended with a sanitized `URLError` before receiving checkpoint response-body bytes. Its outer phase elapsed time was 0.4762331849997281 seconds; the isolated task elapsed time was 0.41303727500053355 seconds. It consumed one acquisition attempt, with zero observed checkpoint body bytes, zero new dependency bytes, zero candidate evaluations and zero model forwards. No complete or partial checkpoint was created. The Intel preflight and resource observations passed. The failed worker imported NumPy and therefore ran its two already disclosed synthetic startup controls.

The parent verified the registration unchanged before and after the failed worker. The worker's own receipt retains `inputs_unchanged: false` and lacks a post-acquisition registration. Both scopes remain intact; a failed worker is not a successful preparation.

The initial standalone diagnosis found direct `huggingface.co` DNS failure. It did not establish the original `URLError`'s cause. The actual HTTPS client uses the environment's configured proxy, which resolves and is not bypassed for this host. A later metadata-only `HEAD https://huggingface.co/` failed with `URLError` / `PermissionError`, errno 1, in the default restricted sandbox. The same HEAD operation with the ordinary `require_escalated` execution permission returned HTTP 200. Neither HEAD read a response body or requested the checkpoint. Proxy configuration and TLS verification were unchanged.

These observations establish that the authorized execution permission supports the configured HTTPS route. They do not guarantee that the immutable resolve URL, its permitted CDN redirects or the full checkpoint body will succeed. They also do not recover the unrecorded underlying reason of the original sanitized worker error. The earlier direct-DNS interpretation is superseded by this more specific connection-path evidence.

Fourteen byte-for-byte retained files, including all nine preparation files, the original publication and claim, and three transport diagnostics, are listed in `validation/2026-10-19-operator-arithmetic/transport-correction-001/evidence-inventory.json`. The first diagnosis has no timestamp or execution-permission field; those fields are not reconstructed. The separate approved direct-DNS tool observation is session evidence only and is not represented as an additional retained receipt.

## Single replacement preparation

Only the preparation shell's execution permission changes to `require_escalated`. Use the existing configured HTTPS proxy and verified TLS, the unchanged `run_audit.py` entry point, unchanged isolated worker, unchanged pinned-download helper and original allowlisted Hugging Face URL. No transport mirror, new package, alternate checkpoint or remote compute service is introduced. All 42 registered source bytes remain unchanged, including the 30 original benchmark files.

Use a fresh publication directory, `build/operator-arithmetic-registration-v2`, and a fresh preparation directory, `build/operator-arithmetic-prepare-002`. Preserve version 1's claim and failed directory. Authorize exactly one replacement download attempt. Any failure remains blocked; another attempt requires another prospective correction.

| Constraint | Retained attempt 1 | Authorized replacement |
| --- | ---: | ---: |
| Checkpoint response-body bytes | 0 | at most 209,715,200 |
| Preparation wall observation | 0.4762331849997281 seconds elapsed | original 600-second phase guard |
| Worker RSS ceiling | original 1 GiB | original 1 GiB |
| Preparation directory ceiling | original 4 GiB | original 4 GiB |
| New dependency bytes | 0 | 0 |
| Explicit candidate evaluations | 0 | 0 |
| Model forwards | 0 | 0 |

The body allowance is cumulative across the two attempts: zero bytes were observed in the retained first attempt, so the unchanged 200 MiB guard enforces the remaining allowance. The replacement gets one prospective 600-second preparation phase allowance. The original elapsed time is carried separately, giving a combined phase allowance of 600.4762331849997281 seconds plus the same guard observation/termination overhead already disclosed in version 1. This is an explicit nonnumerical wall allowance for the corrected launch, not a reset of the elapsed-time history. The 120-second arithmetic phase allowance is unchanged.

The cumulative dependency ledger stays at 1,072,634,485 bytes received against 1,073,741,824, leaving 1,107,339. The source-recovery transfer receipt, known historical model/data acquisition subtotal and checkpoint-body ledger remain separate. An eventual complete checkpoint is still exactly 166,029,852 bytes with SHA256 `ebfa4e2f18696ebd83716a0d39fe2c025f2ff8483f72a83ca59c475692fc9d15` at revision `301b2c9bdf4d6da917d8f02d3c48aac481a60d06`.

## Publication and prelaunch check

The new write-once publication receipt keeps the original arithmetic commit/tree and review/source-map identities. Its `transport_correction` section additionally binds this correction's published commit/tree, the correction input map, both independent correction reviews, the retained evidence inventory, original publication and original consumed preparation claim. It explicitly authorizes only preparation 002 and arithmetic audit 001. Hash the complete new publication file in all existing registration checks.

Before the corrected launch, perform a metadata-only check and retain its receipt. Check every correction-map and inventory entry; both distinct review axes and their report hashes; the correction's published commit/tree; the unchanged 42-source map and original arithmetic reviews; the original failed phase and zero-byte/zero-candidate counters; and the exact retained original publication/claim. Confirm the fresh output paths do not exist, version 2 has no consumed preparation claim, and neither registration has an arithmetic claim. Record the complete new publication identity. This explicit launch check validates the additive correction fields; the unchanged version-1 verifier does not interpret those fields itself.

The preparation command is:

```sh
python -B experiments/operator-audit/run_audit.py prepare \
  --review validation/2026-10-19-operator-arithmetic/prospective-review.json \
  --publication build/operator-arithmetic-registration-v2/publication.json \
  --output build/operator-arithmetic-prepare-002
```

After a valid complete preparation, use the same publication and original review for one audit in `build/operator-arithmetic-audit-001`, with `--preparation build/operator-arithmetic-prepare-002`. The arithmetic worker runs in the default restricted sandbox, retains its socket-event rejection, and rechecks its Intel host, preparation and source identities. No additional candidate is authorized by this correction: the milestone still has exactly eight explicit candidate matrix evaluations, eight bias additions and eight casts, with the same four cases and two row counts. NumPy startup controls remain separately disclosed per importing process.

## Interpretation

This correction changes no arithmetic, array selection, oracle, candidate acceptance rule, historical evidence or scientific claim. A valid local candidate rejection still completes the scientific question. An acquisition failure does not. The original 0.001 absolute logit gate remains failed, the original campaign remains blocked, and issue #5 stays open. The final result must retain both preparation attempts and state the applicable arithmetic and transport publication identities.
