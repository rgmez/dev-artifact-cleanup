# Audit manifest

An audit result must give every candidate a stable identifier and an exact path. It is a review artifact, not an authorization to delete.

For tools that can emit structured data, use [the JSON schema](audit-manifest.schema.json). Otherwise render the same fields in Markdown.

| Field | Required content |
| --- | --- |
| ID | Stable, short identifier used for explicit approval. |
| Path | Absolute, resolved path; never a glob or variable. |
| Class | Build output, test result, worktree, cache, archive, simulator, log, or other. |
| Size | Measured size and measurement caveats. |
| Evidence | Why the location is generated or linked to a worktree. |
| Git / ownership state | Clean, dirty, detached, managed, unknown, or not applicable. |
| Risk | Safe candidate, requires review, or retain. |
| Proposed action | Audit only, remove, archive, or preserve. |
| Approved | `false` during audit; only explicit user authorization may change it to `true`. |

Keep unknown or ambiguous candidates in the report. Do not silently omit them or convert them to safe candidates.

For execution, repeat the path, ID, and evidence before mutating. A changed size, Git state, link target, or running build invalidates the earlier recommendation.
