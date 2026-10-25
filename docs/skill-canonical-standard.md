# Canonical skill and distribution

The canonical package is `skills/dev-artifact-cleanup/`. Do not create separate copies of its behavior for Claude Code, Copilot, Cursor, or Codex. The shared [Agent Skills specification](https://agentskills.io/specification) is the distribution contract.

## Metadata

- Keep `name: dev-artifact-cleanup` stable and equal to its directory name.
- Describe what the skill does and when it applies in `description`.
- Use `license: MIT` and ship `LICENSE.txt` inside the package; the validator checks that it matches the repository license.
- Use `compatibility` for actual filesystem, OS, and tooling requirements.
- Keep `metadata.version` a quoted semantic version matching the final Version section.
- Keep `metadata.supported-runtimes` a string describing distribution targets. It records intended runtimes, not a claim that every behavior was tested on each.

## Portable instructions

Use relative references inside the package. Do not depend on absolute local skill paths, global instruction files, proprietary MCP tools, or a particular model. Capability checks belong in [agent capabilities](../skills/dev-artifact-cleanup/references/agent-capabilities.md).

Do not add `allowed-tools`, hooks, or provider-specific command substitutions to the shared frontmatter. Installation must not preapprove destructive commands. Optional `agents/openai.yaml` stays separate from the portable contract.

## Distribution checks

The validator checks metadata, the bundled license, version consistency, and local Markdown links, including whether package links escape the installed skill directory. The CLI smoke test independently verifies discovery and installation of the entire package for four agent IDs.

Keep behavioral evidence separate: fixture validation and CLI installation do not prove that a model will execute the workflow safely in each host.
