# Dedicated Xcode cache adapter

Use [scripts/xcode_cache.py](../scripts/xcode_cache.py) only after reading [execution rules](execution.md). Python 3.9+ and Git are required. Audit is read-only; execution and restoration require macOS with native exclusive rename support. There is no shell deletion fallback.

## Closed scope

Only `Index.noindex`, `CompilationCache.noindex`, `ModuleCache.noindex`, and `SDKStatCaches.noindex` are supported, as direct children of dedicated DerivedData.

DerivedData and the workspace must be physical absolute paths strictly inside the specified primary Git checkout. The existing `.xcodeproj` or `.xcworkspace` must exactly match `WorkspacePath` in DerivedData's `info.plist`. Shared/global DerivedData, secondary or agent-managed worktrees, symlink components, mounted cache roots, and group/world-writable repository-to-cache paths are rejected.

The cache and every entry must be ignored and untracked. The bounded inventory rejects symlinks, hard-linked files, special files, volume boundaries, foreign ownership, writable-by-others entries, hidden entries, and common source/document/evidence/configuration extensions. Ambiguity blocks the entire candidate. These checks supplement ownership evidence; an ignored name alone never proves disposability. Do not put user data in these caches or override failed checks.

The adapter never removes the DerivedData root, `Build`, `SourcePackages`, logs, `.xcresult`, `.xcarchive`, dSYMs, screenshots, signing material, simulators, or siblings. It never deletes branches or commits work.

## Audit

Resolve the script relative to its installed skill. Use an argument array, or quote literal paths through the host's safe command facility:

```sh
python3 /installed/skill/scripts/xcode_cache.py audit \
  --repository /physical/project \
  --derived-data /physical/project/.derivedData \
  --workspace /physical/project/App.xcodeproj \
  --output /physical/reviews/audit.json
```

The output parent must exist. Existing outputs are never overwritten. The audit manifest keeps `approvedCandidateIds` empty. Missing ownership metadata aborts the audit; candidate-specific uncertainty is reported as `requires-review`, with unknown size represented by `null`. Measured bytes are allocated blocks of inventoried entries, not guaranteed recoverable space.

Eligible candidates bind directory device/inode, DerivedData identity, `info.plist` SHA-256, entry count, and a fingerprint of entry paths and metadata. Inventory is capped at 100,000 entries and 64 directory levels; it does not hash cache contents. A detected change requires a new audit and approval.

## Explicit approval

Present the exact audit ID, candidate IDs, paths, estimated bytes, rebuild cost, and exclusions. Only after the user's explicit approval, record a separate JSON file containing:

| Field | Meaning |
| --- | --- |
| `auditId` | Exact ID from this audit. |
| `manifestSha256` | SHA-256 of the exact saved audit-file bytes, including whitespace. |
| `authorizedCandidateIds` | Unique closed subset of this audit's candidate IDs. |
| `authorizedAt` | Timezone-aware timestamp after the audit and not in the future. |
| `authorizationReference` | Nonempty reference to the actual human authorization in the host's review record. |

Do not modify the audit to add approvals or manufacture approval from `safe-candidate`. This JSON is a record, not a signature, identity proof, or substitute for the host's permissions. An unattended workflow must explicitly adopt this adapter before using it.

Audit, approval, and recovery JSON records must be objects with unique keys at every nesting level and finite numbers. Ambiguous duplicate keys, non-object records, non-finite values, malformed candidate IDs, and inconsistent candidate class/ownership/Git state are blocked before staging. Approved roots must be an array of exact absolute paths; a matching substring in a string is not an approved root. Execution also requires a known integer size matching the revalidated inventory.

## Execute one approved ID

```sh
python3 /installed/skill/scripts/xcode_cache.py execute \
  --manifest /physical/reviews/audit.json \
  --approval /physical/reviews/approval.json \
  --candidate xcode-index-noindex \
  --output /physical/reviews/result.json
```

The script revalidates audit/approval, paths, ownership, ignored/tracked state, metadata, inventory, and visible Xcode/build/test/indexer/simulator activity. A detected process or unavailable/empty process snapshot blocks execution. This conservative check can block an unrelated build. Close Xcode and stop processes yourself; the adapter never terminates them.

Before moving the cache, it creates a private `.cleanup-staging-<random-id>` directory inside DerivedData and fsyncs an immutable `journal.json`. Native exclusive rename moves the cache to `payload` without replacing another entry. Directory descriptors and `O_NOFOLLOW` anchor operations to verified directories. A second activity/inventory check precedes descriptor-relative purge; entry identity is checked during removal.

| Result | Meaning |
| --- | --- |
| `removed` | The staged cache was fully purged. |
| `blocked` | Mutation could not proceed; inspect the reason and any prepared staging directory. |
| `retained` | The staged payload was not purged; inspect it before restoration. |
| `partial` | Purge began but did not complete. Some entries may already be gone. |

The CLI exits nonzero for blocked, retained, partial, or `reportError` outcomes. Preflight errors may emit only a blocked result on stdout; capture stdout/stderr and exit status as well as any saved output. The result file may be incomplete if writes fail. The immutable journal remains the recovery record; its presence does not prove successful removal. Do not auto-delete staging directories in later cleanup runs.

Execution results and new recovery journals record `approvalSha256`, `authorizedAt`, and `authorizationReference` alongside the audit-file digest and candidate ID. Preserve the exact approval bytes and compare these fields when reviewing the outcome. The digest binds the recorded approval, not the identity or authority of whoever wrote it. Earlier journals may lack these new fields; do not invent missing authorization evidence when recovering them.

## Restore retained payload

After explicitly choosing recovery and checking the result/journal:

```sh
python3 /installed/skill/scripts/xcode_cache.py restore \
  --journal /physical/project/.derivedData/.cleanup-staging-ID/journal.json \
  --output /physical/reviews/restore-result.json
```

Restoration rechecks DerivedData identity, workspace metadata, staging ownership/permissions, payload identity, and activity. It exclusively renames the remaining payload back to its original cache name. If a new build recreated that name, it stops without overwriting. It cannot restore purged bytes and is not a backup. Mismatched payloads or changed workspace metadata need human inspection, not forced recovery. Keep the journal and review evidence until the outcome is understood.

## Limits and verification

This assumes a quiescent checkout and trusted local user. Process inspection is a snapshot, not a filesystem lease. Metadata fingerprints and descriptor-relative operations detect many accidental changes and avoid following symlinks; they do not guarantee atomic recursive deletion or protection against an adversarial process running as the same user. Do not use with concurrent writers, untrusted repositories, or incomplete process visibility.

Tests use disposable Git/DerivedData fixtures, real native exclusive rename on macOS, controlled process snapshots, changed inventories, substituted objects, output collisions, interrupted result writes, partial purges, and non-overwriting recovery. They do not demonstrate real-project disk recovery, certify every Xcode layout, or evaluate every agent host. Linux CI tests audit and gates; macOS CI additionally tests native execution and recovery.
