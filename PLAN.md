# Public skill plan: development artifact cleanup

## Goal

Create a shareable Codex skill that inventories local development artifacts, proposes safe cleanup actions, and executes only explicitly authorized, revalidated removals.

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
│       └── references/
│           ├── git-worktrees.md
│           └── xcode-artifacts.md
└── tests/
    └── fixtures/
```

Add scripts only if they remove repeated, error-prone logic that cannot be expressed safely in the skill instructions.

## Delivery phases

1. **Contract** — Define candidate classes, evidence requirements, authorization boundaries, and a machine-readable audit manifest. **In progress:** initial contract and manifest are present in the skill.
2. **Audit mode** — Implement inventory and classification only; test normal, ambiguous, and safety-stop cases. **In progress:** audit-only behavior and scenario cases are being defined.
3. **Execution mode** — Add revalidation and narrowly scoped deletion or Git worktree removal for proven candidates. **In progress:** closed-list execution rules, a versioned manifest schema, and fixtures are present. Version 1 limits execution to verified ordinary secondary Git worktrees; generic directory deletion needs a separately reviewed platform adapter.
4. **Xcode specialization** — Add guidance for custom DerivedData, XcodeBuildMCP, `.xcresult`, archives, dSYMs, package caches, and simulators. **In progress:** ownership and active-build checks, shared DerivedData safety stops, and test-evidence retention are now documented.
5. **Public-readiness** — Add license, concise repository documentation, validation evidence, and a no-secrets review. **In progress:** MIT license and pre-release README are present; independent behavior validation and a no-secrets review remain.
6. **Publication and article** — Make the repository public only after review; write the article from verified behavior and measured examples that contain no private data.

## Release gates

- The skill validates structurally and is exercised with one ordinary audit, one safe cleanup, and one deliberate stop case.
- No personal paths, secrets, private URLs, screenshots, customer data, or project-specific instructions are present.
- Every destructive path requires explicit authorization and final revalidation.
- The repository owner, visibility, and license are confirmed.
- The public README and article claims are supported by actual validation evidence.

## Decisions

- License: MIT.
- Initial scope: Git + Xcode/Swift. Web and Android require separate evidence rules before inclusion.
- Manifest format: JSON manifest plus Markdown summary.
- Distribution target: repository source first; package distribution is deferred until the release workflow is validated.
