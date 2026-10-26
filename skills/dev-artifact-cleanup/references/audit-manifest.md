# Audit manifest

An audit result must give every candidate a stable identifier and an exact path. It is a review artifact, not an authorization to delete.

For tools that can emit structured data, use [the JSON schema](audit-manifest.schema.json). Otherwise render the same fields in Markdown.

| Field | Required content |
| --- | --- |
| ID | Stable, short identifier used for explicit approval. |
| Path and resolved path | Absolute requested path plus its resolved physical path; never a glob or variable. |
| Approved root | The resolved root containing the candidate. |
| Class | Build output, test result, worktree, cache, archive, simulator, log, or other. |
| Size | Measured size and caveats; `sizeBytes: null` means unknown, not zero. |
| Evidence | Why the location is generated or linked to a worktree. |
| Git / ownership state | Clean, dirty, detached, managed, unknown, or not applicable. |
| Risk | Safe candidate, requires review, or retain. |
| Audit recommendation | `eligible-for-execution`, `requires-review`, or `retain`. It is not an execution command. |
| Snapshot | Observation time and revalidation facts such as symlink state, worktree role, HEAD, branch tip, and base OID. |
| Adapter (optional) | Xcode cache identity, ownership paths, metadata hash, bounded inventory fingerprint, content profile, and entry count, or `null` if unavailable. |

Keep unknown or ambiguous candidates in the report. Do not silently omit them or convert them to safe candidates.

The audit manifest has an `auditId`, a unique candidate-ID set, and an empty approval list. Execution records the authorized candidate IDs separately. A changed size, Git state, link target, snapshot, or running build invalidates the earlier recommendation.

Audit may retain a symlink or unmeasured candidate as `requires-review`; that does not make it executable. Schema validation is structural, not an execution permission. The [Xcode adapter](xcode-cache-adapter.md) additionally requires a separate approval binding the exact audit-file SHA-256, IDs, authorization timestamp, and human authorization reference. Do not edit an audit to add approvals for that adapter.
