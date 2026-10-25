# Behavior scenarios

These scenarios validate the skill's decision boundaries without deleting data.

## 1. Dedicated DerivedData audit

Given a repository with a custom DerivedData directory whose workspace metadata points to that repository, no active build, and no retained test evidence, the audit should produce a **safe candidate** with an exact path and rebuild cost. It must not delete the directory in audit mode.

## 2. Clean integrated worktree

Given a clean ordinary Git worktree whose branch is integrated into the approved base branch and whose ignored contents are only a known build cache, the audit should recommend `git worktree remove` only after explicit execution authorization. It must state that branch deletion is a separate action.

## 3. Ignored settings safety stop

Given a clean worktree containing an ignored `settings.local.json` or `.env` file, the audit should classify it as **requires review** and not recommend removal based solely on ignored status.

## 4. Unique commit safety stop

Given a clean worktree with a commit that is neither reachable from nor patch-equivalent to the approved base, the audit should retain it and report the integration decision needed.

## 5. Simulator safety stop

Given a CoreSimulator device directory, the audit should retain it unless the user explicitly identifies the device as disposable and authorizes its deletion through the simulator lifecycle.
