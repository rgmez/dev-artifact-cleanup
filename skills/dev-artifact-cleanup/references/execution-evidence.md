# Review Xcode execution evidence

Use [scripts/validate_execution.py](../scripts/validate_execution.py) after an explicitly authorized removal through the [Xcode adapter](xcode-cache-adapter.md), or to inspect its preserved evidence later. Python 3.9+ and a macOS or Linux filesystem are required. This checker does not require Git or access to the recorded project. It never runs removal, restoration, process inspection, or Git commands.

Preserve the exact bytes of the audit, separate approval, removal result, and immutable journal. Obtain the journal from the reviewed execution record; do not discover it by following an untrusted result pointer. A preserved archive copy is accepted even when the original project or staging directory no longer exists.

```sh
python3 -B /installed/skill/scripts/validate_execution.py \
  --audit /physical/reviews/audit.json \
  --approval /physical/reviews/approval.json \
  --result /physical/reviews/result.json \
  --journal /physical/reviews/archived-journal.json \
  --output /physical/reviews/evidence-validation.json
```

Inputs must be explicit physical absolute paths to bounded regular files, with no symbolic-link components. The optional output requires an existing parent and never overwrites a file. Without `--output`, only stdout is written. Use `-B` to avoid bytecode in a pinned skill package.

## What is checked

- Strict JSON objects, unique keys, finite numbers, the selected adapter metadata contract, and the recorded approval's exact audit-byte digest and candidate ID.
- Result bindings to audit ID, candidate ID, exact audit and approval byte digests, authorization timestamp/reference, operation, and target path.
- A unique 32-hex `executionId` matching the journal and original staging-directory name, plus the result's SHA-256 of the exact supplied journal bytes. Journals from separate retries are not interchangeable, even under the same audit and approval.
- The original journal pointer's lexical relationship to the audited dedicated DerivedData staging path. The pointer is never opened automatically.
- The explicitly supplied journal's matching identifiers, digests, adapter metadata, payload identity, and a timezone-aware creation time following approval and not in the future.

Only the selected removal evidence is checked, not every field of an audit/report schema. Whitespace changes alter file digests. Earlier or incomplete records may not contain enough evidence; do not invent missing bindings to make them pass.

Version 0.3.1 requires the current `contentProfile` audit metadata and attempt-specific result/journal bindings. Older 0.3.0 receipts lack those guarantees and are invalid/incomplete under this checker, even when an older checker accepted them. Preserve those originals and their previous validation rather than rewriting or backfilling them. This change does not authorize another removal; a new action needs a new audit and approval. Legacy recovery remains a separate manually reviewed workflow.

## Interpret results

| Evidence | `valid` | `reportedSuccess` | Recommended review status |
| --- | --- | --- | --- |
| Consistent `removed`, journal present, no report error | `true` | `true` | `completed` |
| Consistent `retained` or `partial`, reason and journal present | `true` | `false` | `partial` |
| Consistent `blocked`, reason and any recorded journal present | `true` | `false` | `blocked` |
| Intermediate `prepared` or `purging` | `false` | `false` | `partial` |
| Incomplete, malformed, mismatched, or unsupported evidence | `false` | `false` | `partial` or `blocked` |

A `reportError` prevents reported success even if the remaining evidence is consistent. A preflight stdout receipt containing only `status` and `reason` remains blocked and lacks enough bindings to validate. Missing outputs or unavailable checks must remain explicit in the surrounding execution review.

Exit `0` means consistent evidence, **not successful cleanup**: inspect `reportedSuccess`, `outcome`, and findings. Exit `1` means invalid/incomplete evidence; exit `2` means the requested validation output could not be created or saved. Capture stdout, stderr, and exit status separately.

## Authorization and trust limits

`permissionGranted` and `humanAuthorizationVerified` are always `false`. Anyone able to write all four documents can fabricate a consistent bundle. Digests prove correspondence between supplied bytes, not human identity, actual execution, elapsed time, current process safety, or current filesystem state. Recorded success is not a disk-space measurement or a certificate for a real project or agent host.

The surrounding workflow must independently verify the actual human approval, trusted runner and exit status, current scope, host permissions, and observed outcome. This tool never upgrades an audit-only automation or authorizes a later removal. Restoration is outside this remove-only checker: inspect recovery evidence and obtain separately scoped recovery authorization rather than reusing cleanup approval.
