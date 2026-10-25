# Agent capabilities

The same `SKILL.md` and references are used by Claude Code, GitHub Copilot, Cursor, Codex, and other agents that load the Agent Skills format. Installation support is distinct from permission to inspect the user's development machine.

## Select tools by capability

- Use the host's filesystem and command tools to inspect the workspace that the user placed in scope. Resolve this skill's relative references from its installed directory, not the workspace working directory.
- A GitHub-only or cloud session can inspect its own checkout. It cannot audit the user's Mac storage, Xcode, or local processes unless access is actually provided.
- If the host cannot verify a required check, retain the affected candidate and identify the missing capability. Continue independent audit checks that are available.
- Use the host's normal approval mechanism for operations outside its sandbox. Installing a skill never grants additional permissions.
- Invoke Git with an argument array where supported. If only a shell is available, use its platform-appropriate quoting with literal validated paths; never interpolate untrusted manifest text or assume that JSON escaping is shell escaping. Stop execution if safe argument passing is unavailable.

## Host guidance

| Host | How to use the skill | Execution limits |
| --- | --- | --- |
| Claude Code | Native skill discovery or `/dev-artifact-cleanup`; use filesystem and Bash tools when provided. | Keep normal tool approvals. Do not preapprove deletion through skill metadata. |
| GitHub Copilot | Ask Copilot in agent mode to use `dev-artifact-cleanup` in its current workspace. | A cloud agent or code-review session may lack local process or disk inspection; retain candidates when those checks are unavailable. |
| Cursor | Ask the agent to use `dev-artifact-cleanup` after installation. | Follow the active terminal and filesystem permissions. |
| Codex | Native skill discovery or `$dev-artifact-cleanup`; use available local tools. | Managed worktrees require their supported host lifecycle. The optional `agents/openai.yaml` is UI metadata only. |
| Other agents | Load `SKILL.md` together with its linked relative references. | Apply the same capability checks; do not assume a tool name or local machine access. |

Git inspection targets macOS and Linux. The bundled Xcode cache script requires Python 3.9+ and Git; its metadata-only audit is portable, but execution and restoration require macOS and native exclusive rename support. Other Xcode diagnostics require the relevant macOS tools. Native Windows path manifests are unsupported; a Linux/WSL workspace cannot infer access to a macOS host. Installation never enables an adapter in an existing pinned automation automatically.
