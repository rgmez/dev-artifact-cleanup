# Xcode artifacts

Classify Xcode storage by ownership and recovery cost.

## Establish ownership before classifying

Look for a configured `-derivedDataPath`, build scripts, or workspace metadata that links an artifact to the approved checkout. When available, compare the normalized `WorkspacePath` in a DerivedData `info.plist` to the exact checkout path. A missing plist is not evidence that the directory is abandoned.

Check whether Xcode, `xcodebuild`, or a test process is using the target. If activity cannot be checked safely, classify the candidate as requiring review rather than attempting cleanup.

## Usually audit as project-dedicated build output

- A custom `-derivedDataPath` or project-local DerivedData directory whose workspace metadata matches the approved checkout.
- Build products, indexes, module caches, and resolved packages inside that dedicated directory can be inventoried separately; this classification is not blanket permission to remove them.
- Test output is retained by default. It becomes a cleanup candidate only after a documented retention decision and explicit approval for that exact candidate.

Confirm no build or test is active first. Removing these directories can require a rebuild and dependency resolution.

## Narrow execution adapter

The [bundled adapter](xcode-cache-adapter.md) executes only `Index.noindex`, `CompilationCache.noindex`, `ModuleCache.noindex`, or `SDKStatCaches.noindex` directly inside dedicated DerivedData in the primary checkout. It requires matching `WorkspacePath` metadata, physical paths, ignored/untracked contents, an unchanged inventory, no active Xcode processes, and a separate exact approval. Execution and restoration require macOS; metadata-only audit can run on Linux against accessible fixtures or checkout data.

The closed allowlist is only the first gate. Nonempty caches also need the adapter's current content profile, currently a narrow IndexStore v5 layout with recognized binary signatures. Unknown entries and the other nonempty cache formats require review, without an execution override. Filename extensions alone are not a generated-content classifier.

It never removes the DerivedData root, `Build`, `SourcePackages`, logs, test evidence, archives, dSYMs, simulators, or shared caches. Evidence inside an allowlisted cache blocks that candidate. Names and age alone are never enough.

## Require review

- Global `~/Library/Developer/Xcode/DerivedData` and module caches: these can be shared by unrelated projects.
- `.xcresult` bundles, `.xcarchive` bundles, dSYMs, exported screenshots, and diagnostic logs: they may be release, compliance, or QA evidence.
- XcodeBuildMCP workspaces: verify a concrete checkout association.
- `SourcePackages`, including project-local copies: dependency caches may be shared or intentionally pinned; they remain audit-only.
- `DerivedData` directories whose workspace relationship cannot be established.

## Retain unless explicitly authorized

- CoreSimulator devices and runtimes. They contain installed apps and user data.
- Signing material, provisioning profiles, keychains, and app archives intended for distribution.

Do not infer safety from age or from a path containing `build`. Record the artifact's owner, evidence, and recovery cost in the audit manifest.

Never delete a CoreSimulator directory from the filesystem. If a user explicitly identifies a disposable simulator, verify its exact UDID and inactive state, then use the supported simulator lifecycle command rather than directory removal.
