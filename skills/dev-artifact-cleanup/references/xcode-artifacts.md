# Xcode artifacts

Classify Xcode storage by ownership and recovery cost.

## Usually audit as project-dedicated build output

- A custom `-derivedDataPath` or project-local DerivedData directory whose workspace metadata matches the approved checkout.
- Build products, indexes, module caches, and resolved packages inside that dedicated directory.
- Test output explicitly generated for the approved task, if no retention requirement applies.

Confirm no build or test is active first. Removing these directories can require a rebuild and dependency resolution.

## Require review

- Global `~/Library/Developer/Xcode/DerivedData` and module caches: these can be shared by unrelated projects.
- `.xcresult` bundles, `.xcarchive` bundles, dSYMs, exported screenshots, and diagnostic logs: they may be release, compliance, or QA evidence.
- XcodeBuildMCP workspaces: verify a concrete checkout association.
- `SourcePackages` outside a dedicated build directory: dependency caches may be shared or intentionally pinned.

## Retain unless explicitly authorized

- CoreSimulator devices and runtimes. They contain installed apps and user data.
- Signing material, provisioning profiles, keychains, and app archives intended for distribution.

Do not infer safety from age or from a path containing `build`. Record the artifact's owner, evidence, and recovery cost in the audit manifest.
