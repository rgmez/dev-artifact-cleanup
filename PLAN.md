# Public skill plan: development artifact cleanup

## Goal

Create a shareable Agent Skill for Claude Code, GitHub Copilot, Cursor, Codex, and other compatible agents that inventories local development artifacts, proposes safe cleanup actions, and executes only explicitly authorized, revalidated removals.

The skill must reduce disk use without treating local work, ignored files, worktrees, test evidence, or release artifacts as disposable by default.

## Audience and boundary

The initial audience is developers working in local Git repositories, including Xcode and Swift projects. The skill supports repositories with other build systems when artifacts can be identified from project configuration.

It is not a general disk cleaner, backup tool, branch-deletion tool, or unattended destructive automation.

## Design principles

- Audit first; execution requires explicit authorization and an exact candidate list.
- Treat ignored files as unknown until classified; ignored does not mean generated.
- Use Git metadata, current worktree state, and integration evidence rather than directory names.
- Resolve the real integration branch and remote rather than hard-coding a branch name.
- Preserve remote branches. Preserve local branches unless the user separately authorizes deletion after integration checks.
- Keep Xcode-specific artifacts, test evidence, archives, simulators, and shared caches as separate categories with different retention rules.

## Repository shape

```text
dev-artifact-cleanup/
├── PLAN.md
├── skills/
│   └── dev-artifact-cleanup/
│       ├── SKILL.md
│       ├── scripts/
│       │   ├── xcode_cache.py
│       │   └── validate_execution.py
│       └── references/
│           ├── git-worktrees.md
│           └── xcode-artifacts.md
└── tests/
    └── fixtures/
```

Add scripts only if they remove repeated, error-prone logic that cannot be expressed safely in the skill instructions.

## Delivery phases

1. **Contract** — Define candidate classes, evidence requirements, authorization boundaries, and a machine-readable audit manifest. **Complete for v1.**
2. **Audit mode** — Implement inventory and classification only; test normal, ambiguous, and safety-stop cases. **Complete:** fixture validation and a real non-destructive audit with no candidates both passed.
3. **Execution mode** — Closed-list worktree execution and contract fixtures are present. Version 0.2 adds a narrow native Xcode cache adapter; generic directory deletion remains excluded.
4. **Xcode specialization** — Guidance covers DerivedData, XcodeBuildMCP, `.xcresult`, archives, dSYMs, packages, and simulators. Version 0.2 adds audit, explicit hash-bound approval, exclusive staging, bounded purge, and non-overwriting recovery for four dedicated cache children inside a primary checkout. Disposable fixtures exercise native macOS behavior; real-project trials and adoption by pinned automations remain separate. No simulator or shared-cache execution is added.
5. **Public-readiness** — Add license, concise repository documentation, validation evidence, and a no-secrets review. **Public repository available:** the package remains a development version; installation validation does not certify execution behavior in each host.
6. **Publication and article** — The GitHub repository is public. Versioned releases and an article remain separate deliverables.
7. **Cross-agent distribution** — Keep one canonical Agent Skills package under `skills/dev-artifact-cleanup`, provide skills.sh installation for Claude Code, Copilot, Cursor, and Codex, and validate discovery, installed resources, and relative links. CI repeats distribution checks with telemetry disabled. Runtime behavior in each host requires separate evaluation.
8. **Execution evidence integration** — Version 0.3 links exact audit/approval/result/journal bytes with a portable read-only checker. Native disposable fixtures cover removed, retained, partial, and blocked receipts. This checks recorded consistency, not human authorization or authentic execution. Adoption by the weekly pinned automation, real-project trials, and unattended Xcode execution remain separate gates.

## Release gates

- The skill validates structurally and is exercised with one ordinary audit, one safe cleanup, and one deliberate stop case.
- No personal paths, secrets, private URLs, screenshots, customer data, or project-specific instructions are present.
- Every destructive path requires explicit authorization and final revalidation.
- The repository owner, visibility, and license are confirmed.
- The public README and article claims are supported by actual validation evidence.
- An Xcode adapter change passes portable audit/schema tests and native macOS execution/recovery tests, including changed paths, links, failed activity checks, output collisions, and partial failures. Keep recovery journals immutable and disclose concurrency/metadata-fingerprint limits.

## Decisions

- License: MIT.
- Initial scope: Git + Xcode/Swift. Web and Android require separate evidence rules before inclusion.
- Manifest format: JSON manifest plus Markdown summary.
- Distribution target: public GitHub source installed through the skills CLI (`skills.sh`). No separate npm package or Claude plugin is required for native skills support.
- Runtime metadata follows the existing public skill repositories: quoted semantic version and a string `supported-runtimes` field, with portable instructions shared by every host.
- `compatibility` follows the Agent Skills specification. A bundled provider validator that rejects that standard field is not the cross-agent distribution contract; the repository validator and real CLI smoke test cover distribution.
