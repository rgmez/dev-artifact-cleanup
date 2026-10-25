# Releasing

## Verify the package

1. Review the current diff and ensure no personal paths, credentials, private logs, or customer data are shipped.
2. Run `python3 scripts/validate_distribution.py` and `ruby tests/validate_fixtures.rb`.
3. Run `python3 scripts/smoke_install.py` to check the local package with the pinned skills CLI. This installs only in a temporary project with telemetry disabled.
4. Update the version in `SKILL.md` metadata and its Version section together when preparing a versioned release. Do not claim a Git tag or GitHub Release until it exists.
5. Check the Docs Checks workflow after pushing to the already authorized public repository.

## Verify public discovery

After pushing, run `npx skills add rgmez/dev-artifact-cleanup --list`. A read-only discovery test confirms the remote package is available without installing into a real project.

The standard install command is:

```sh
npx skills add rgmez/dev-artifact-cleanup --skill dev-artifact-cleanup
```

skills.sh listing is driven by real CLI installations with telemetry enabled, as described in [its FAQ](https://skills.sh/docs/faq). There is no separate registration file required. Do not generate repeated test installs to inflate counts or claim immediate indexing. CI and smoke tests disable telemetry.

Native Claude Code plugins, an npm package, and `skills.sh.json` page groupings are optional and unnecessary for this single-skill repository. Use the canonical Agent Skills package first.

## Optional versioned release

Only when a release is requested, prepare release notes from verified changes, tag the intended commit, and publish through the repository's normal release workflow. Publishing an article is a separate deliverable.
