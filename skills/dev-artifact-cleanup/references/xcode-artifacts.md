# Xcode artifacts

Classify Xcode storage by ownership and recovery cost.

## Establish ownership before classifying

Look for a configured `-derivedDataPath`, build scripts, or workspace metadata that links an artifact to the approved checkout. When available, compare the normalized `WorkspacePath` in a DerivedData `info.plist` to the exact checkout path. A missing plist is not evidence that the directory is abandoned.

Check whether Xcode, `xcodebuild`, or a test process is using the target. If activity cannot be checked safely, classify the candidate as requiring review rather than attempting cleanup.

## Usually audit as project-dedicated build output

- A custom `-derivedDataPath` or project-local DerivedData directory whose workspace metadata matches the approved checkout.
- Build products, indexes, module caches, and resolved packages inside that dedicated directory.
- Test output explicitly generated for the approved task, if no retention requirement applies and it is not the only evidence for a CI, QA, or release decision.

Confirm no build or test is active first. Removing these directories can require a rebuild and dependency resolution.

## Require review

- Global `~/Library/Developer/Xcode/DerivedData` and module caches: these can be shared by unrelated projects.
- `.xcresult` bundles, `.xcarchive` bundles, dSYMs, exported screenshots, and diagnostic logs: they may be release, compliance, or QA evidence.
- XcodeBuildMCP workspaces: verify a concrete checkout association.
- `SourcePackages` outside a dedicated build directory: dependency caches may be shared or intentionally pinned.
- `DerivedData` directories whose workspace relationship cannot be established.

## Retain unless explicitly authorized

- CoreSimulator devices and runtimes. They contain installed apps and user data.
- Signing material, provisioning profiles, keychains, and app archives intended for distribution.

Do not infer safety from age or from a path containing `build`. Record the artifact's owner, evidence, and recovery cost in the audit manifest.
