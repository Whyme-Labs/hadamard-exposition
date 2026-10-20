# Final Specification review

Date: 18 October 2026 UTC. Reviewer: `/root/campaign_readiness_audit`.

**PASS for the completed diagnostic milestone.** The evidence meets the reviewed version-2 reproduction and observation contract. The original reference parity failure remains a failure. This review does not qualify a complete pretrained campaign or authorize another experiment.

## Bindings

The execution sources were published at commit `49d787419737f3ab0da3b692549d6bd6c2912e63`. The prospective review SHA256 is `f8b6795138b4fa55c734d470feb0017ce6d753d07d9198863000d36c21871786`. All thirty benchmark files, five diagnostic/procedure files and four unchanged environment helpers match that review and their before/after receipts. The canonical benchmark source-map SHA256 remains `1dd75e9af0736795e4d83c26f866d15d9f7a3fe55003e399ddbd36951ab2d69e`.

| Final document | SHA256 |
|---|---|
| Repository `README.md` | `aa4dc37635648074ae422e64d5d50e493cc52c9be5d85c27f4f14066785ef9bf` |
| Repository `CONTEXT.md` | `6c3cc3f98ffddb0beb3b17abdcf9bd9e3c235d1fd4e80c7e3280542bf0289fca` |
| Milestone `README.md` | `d498b09dffa143650510aa76f3fd086c83dfc8dd8fa22d812ba1ceb3a319f85e` |
| `trace-analysis.json` | `97f3ef9cb52c867d7ac694ed49b32378dcee02cc4d8c23f0c910c6c69e191aac` |
| `diagnostic-input-recovery/omission-clarification.json` | `9282a659e2e42febe29d0f53fc8fb7c298b30fece6b990cbd848828ccedc17a5` |

| Verified raw archive | SHA256 |
|---|---|
| `diagnostic-environment-recovery/raw-evidence.tar.gz` | `52e967a0f4d4b873666065e42084e8544cb113ba4a57fd1f3990c46c93a5f424` |
| `diagnostic-input-recovery/raw-evidence.tar.gz` | `c75a5fbb6ee4cce4506f8e0d75193aa692ccb54da42603898c8138cd15b23e4f` |
| `recovered-cache-maintenance/raw-evidence.tar.gz` | `f598c5343d7321d8278821a76c038f8afe7531d56fd4a5cb89e2ebdfb74b9278` |
| `reference-trace-v2/raw-evidence.tar.gz` | `67d20a6e24f477fcf5e789aa8af6259f07f06ffd83bc407084e24b747e0f683a` |

The trace worker receipt SHA256 is `0a3f346cc8fc3904167cd9bf4d8331e31591117ec30d2e11dfcc57866887965c`; the parent receipt SHA256 is `f0e36fe9a8b950b5887bd2ea012eb914ffed8d6ab5e419ce37e9aaef59b19b8c`.

## Independently verified findings

- **Evidence and inputs:** All 70 regular archive members, their byte counts and hashes, and every separate receipt copy match their inventories. Task receipts bind the corresponding worker results and process identities. The eight new acquisition identities equal the original pinned identities, totaling 175,891,986 response-body bytes. All sixteen consumed input identities, including the five complete model files and reconstruction receipt, also match the maintenance journal and trace bindings.
- **Exact reproduction:** Exactly six reference forwards were attempted and completed. All six whole-array logit identities and all 72 original cache identities match the original reference receipt. Both retained full-last arrays and both complete cached arrays match directly. The full/prefill original arrays remain unavailable; their direct equality and numerical error fields correctly remain null. The reproduced cached errors are 0.016845703125 and 0.001708984375, still above the frozen 0.001 limit.
- **Observed divergence:** Independent inspection of all 960 saved trace events confirms the first numerically unequal event in each article is `gpt_neox.layers.0.attention.query_key_value:output`, after sixteen numerically equal events. Its last-token inputs are byte-identical under full module shapes `[1,513,512]` and `[1,1,512]`. The maximum output difference is exactly 1.430511474609375e-6, with 1,280 and 1,286 unequal entries. The derived boundary table agrees with the retained arrays and worker receipt.
- **Cache and position controls:** All 24 full-prefix/prefill and 24 cached-prefix/prefill comparisons have exact data identity; all 24 supplied prefill arrays remain unchanged. Full/cached token and cache positions are 512, with matching rotary observations. Their last-query masks permit the same 513 positions and mask the extra position in retained shape `[1,1,1,514]`. Mask values are numerically equal, but permitted-position zeros have different signs. Claims about the first divergence correctly refer to numerical inequality, not the first byte difference.
- **Bounds and sequence:** Environment recovery carried the preceding transfer total, finishing at 1,072,634,485 measured HTTPS bytes with 1,107,339 bytes remaining. Recovery precedes the single four-root advisory pass, which precedes the fresh frozen host preflight and worker launch. The journal has 54,519 unique accepted entries totaling 3,565,454,159 logical bytes with unchanged metadata. The host passes at 7,085,432,832 conservative available bytes. Trace elapsed time is 6.120453825 seconds; the worker records 794,464,256-byte OS RSS and the guard observes a separate 794,763,264-byte sampled peak. All retained task/resource observations fit the stated limits. The complete trace archive contains 5,977,560 uncompressed bytes, below the 64 MiB allowance. These observations do not establish instantaneous allocation caps or reclaimed-memory quantities.

## Findings resolved in the report and limits on interpretation

The 152,043,520-byte unreferenced partial is outside the eight acquisition records and the consumed model map. Its identity appears in the maintenance journal; its recorded metadata change follows reconstruction completion. The append-only clarification correctly leaves its origin unresolved, preserves the original inventory and distinguishes historical acquisition verification from the later directory state. The later 497,224,832-byte input snapshot reconciles exactly with the pre-finalization observation, final receipt and extra partial. No pinned-input provenance or cleanup claim is assigned to that partial.

The pinned reference applies the QKV projection before rotary application, cache update and mask addition. Shape-dependent FP32 linear evaluation is a supported leading explanation for the first numerical divergence. This trace does not identify an internal kernel or accumulation order, establish a repair, or show that this boundary alone causes all later error. The first block's parallel MLP projection also differs despite matching last-token inputs.

The final documents preserve the distinction between completed historical host qualification and the still-blocked campaign. They accurately describe the retained validation receipt without claiming a repeated campaign suite. The proposed operator investigation is explicitly a future preregistered milestone. ONNX development parity, cost proof, execution lock, quality and timing acceptance remain outstanding; no Hadamard quality or inference-saving conclusion follows.

This review used source and receipt inspection and calculations on already-retained arrays. It made no model calls, network requests, installations, cache-advice calls or benchmark executions. Its only written file is this review.
