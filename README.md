# Development Artifact Cleanup

An audit-first [Agent Skill](https://agentskills.io/specification) for identifying safe cleanup candidates in local development environments. One canonical package works with Claude Code, GitHub Copilot, Cursor, Codex, and other agents supported by the [skills CLI](https://github.com/vercel-labs/skills).

It is designed for Git repositories and has dedicated guidance for Xcode artifacts. It inventories build outputs, caches, logs, and worktrees, then separates candidates that can be safely acted on from local work, test evidence, archives, simulators, and ambiguous ignored files.

## Install with skills.sh

Run from the project where you want to use the skill. The CLI requires Node.js 22.20 or newer and prompts for the target agents:

```sh
npx skills add rgmez/dev-artifact-cleanup --skill dev-artifact-cleanup
```

Select an agent explicitly:

```sh
npx skills add rgmez/dev-artifact-cleanup --skill dev-artifact-cleanup -a claude-code
npx skills add rgmez/dev-artifact-cleanup --skill dev-artifact-cleanup -a github-copilot
npx skills add rgmez/dev-artifact-cleanup --skill dev-artifact-cleanup -a cursor
npx skills add rgmez/dev-artifact-cleanup --skill dev-artifact-cleanup -a codex
```

The `rgmez/dev-artifact-cleanup@dev-artifact-cleanup` source syntax is also supported, matching the other skills in this collection. Add `-g` only if you want a personal installation across projects. Preview discovery without installation with `npx skills add rgmez/dev-artifact-cleanup --list`.

| Agent | Skills CLI ID | Usage after installation |
| --- | --- | --- |
| Claude Code | `claude-code` | `/dev-artifact-cleanup Audit this repository.` |
| GitHub Copilot | `github-copilot` | Ask Copilot in agent mode to use `dev-artifact-cleanup`. |
| Cursor | `cursor` | Ask the agent to use `dev-artifact-cleanup`. |
| Codex | `codex` | `$dev-artifact-cleanup Audit this repository.` |
| Other agents | Select in the CLI | Use the installed skill through the agent's normal skill discovery. |

All agents receive the same directory under `skills/dev-artifact-cleanup/`, including references, schema, bundled scripts, and license. The optional `agents/openai.yaml` only adds Codex UI metadata. There is no dependency on Codex-specific tools, plugins, or a separate Claude plugin manifest.

For a manual project install, copy that entire directory into a location recognized by your agent, for example `.claude/skills/dev-artifact-cleanup/` for Claude Code or `.github/skills/dev-artifact-cleanup/` for Copilot. Copying only `SKILL.md` omits required references. The CLI chooses the supported destination for each agent and is the recommended path.

## Scope and requirements

Version 0.2 focuses on Git repositories and Xcode/Swift development environments. Web and Android build artifacts are deferred until they have their own evidence rules and validation scenarios.

Filesystem and Git inspection require a macOS or Linux workspace. The optional Xcode adapter needs Python 3.9+ and Git; metadata-only audit is portable, but execution and recovery require macOS. Other Xcode diagnostics need the relevant macOS tools. A cloud agent cannot infer access to your development machine. Native Windows path manifests are outside the scope. See [agent capabilities](skills/dev-artifact-cleanup/references/agent-capabilities.md).

## Safety model

- Audit is the default; it does not delete, commit, fetch, or modify branches.
- Execution requires explicit approval for exact manifest candidates and revalidates every target immediately before action.
- Worktrees use Git lifecycle commands rather than manual deletion.
- Execution supports eligible ordinary secondary Git worktrees, plus four direct dedicated-Xcode-cache directories through a macOS adapter. All other directories, shared caches, archives, test evidence, and simulators remain audit-only.
- Local branches require separate authorization. Remote branches are never in scope by default.

## Usage

Start with an audit request:

> Use dev-artifact-cleanup to audit this repository's artifacts and worktrees. Produce a candidate manifest with evidence and retention reasons.

After reviewing the report, identify the approved worktree candidates:

> For audit audit-123, remove only worktree-feature-a after revalidation.

The instructions guide the agent's decisions; a manifest or metadata field does not technically enforce tool permissions. The host's sandbox and approval system remain responsible for execution access.

For Xcode caches, follow the [adapter contract and CLI examples](skills/dev-artifact-cleanup/references/xcode-cache-adapter.md). It requires matching workspace metadata, ignored/untracked contents, unchanged identity/inventory, no Xcode activity, and a separate approval bound to the exact audit-file SHA-256 and candidate IDs. It stages without overwriting and keeps a recovery journal; restoration cannot undo an already purged file. It assumes a quiescent trusted checkout, not adversarial concurrent writers.

## skills.sh discovery

This public GitHub repository is installable by the skills CLI. [skills.sh indexes skills through CLI installation telemetry](https://skills.sh/docs/faq); there is no separate package upload or approval file required. A successful install does not guarantee immediate search or leaderboard visibility.

The CLI's telemetry is optional. Set `DISABLE_TELEMETRY=1` or `DO_NOT_TRACK=1` if you prefer to opt out. Distribution checks in this repository disable telemetry and install only into temporary projects.

## Development and validation

```sh
python3 -m pip install -r requirements-dev.txt
python3 scripts/validate_distribution.py
ruby tests/validate_fixtures.rb
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

For an isolated CLI discovery/install test:

```sh
python3 scripts/smoke_install.py
```

The smoke test uses `skills@1.7.4` in a temporary project, installs for Claude Code, Copilot, Cursor, and Codex, and verifies the installed package resources. It never installs globally or changes live agent settings. Passing installation checks does not demonstrate full behavioral testing in every agent.

The same checks run in [GitHub Actions](.github/workflows/docs-checks.yml), with native adapter tests on macOS. Tests use disposable fixtures, not user projects. They validate implementation behavior under controlled conditions, not every Xcode layout or host. [Releasing](docs/releasing.md) describes verification and optional versioned releases; [PLAN.md](PLAN.md) tracks scope and remaining work.

The skill source is at [skills/dev-artifact-cleanup](skills/dev-artifact-cleanup).

## License

MIT. See [LICENSE](LICENSE).
