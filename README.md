# LAT Plugin Template

Template repository for LAT Agent plugins.

A LAT plugin repo is discoverable when:

- The repository name matches the LAT discovery naming pattern, for example `lat-plugin-my-tool`.
- The default branch contains a valid `manifest.json` at the repository root.

A LAT plugin release is installable when:

- The GitHub Release contains exactly one `.zip` asset that has `lat-agent.json` at the zip root.
- `lat-agent.json` has `package_type: lat_plugin`.
- `lat-agent.json.plugin.id/version` matches `plugin/manifest.json`.
- `lat-agent.json.install.source_dir` points to the plugin source directory, normally `plugin`.

## Repository Layout

```text
manifest.json              # Discovery manifest used by LAT Plugin Discovery
lat-agent.json             # Release package metadata used by LAT install/update
plugin/
  manifest.json            # Installed plugin manifest
  main.py                  # Plugin entrypoint
  requirements.txt         # Optional dependencies
scripts/
  package_plugin.py        # Local package builder and validator
.github/workflows/
  release.yml              # Manual release workflow
```

Keep `manifest.json` and `plugin/manifest.json` aligned. LAT Discovery reads the root manifest, while LAT installs the release package and then loads `plugin/manifest.json` from the installed plugin directory.

## Create A Plugin From This Template

1. Create a new repository from this template. Use a repo name like `lat-plugin-my-tool`.
2. Update `id`, `version`, `entry`, `args`, and `actions` in both `manifest.json` and `plugin/manifest.json`.
3. Update `lat-agent.json.plugin.id` and `lat-agent.json.plugin.version` to match the plugin manifest.
4. Implement the plugin in `plugin/main.py`.
5. Run a local package validation:

```bash
python scripts/package_plugin.py --version 0.1.0 --output-dir dist
```

The generated package will be placed in `dist/<plugin-id>-v<version>.zip`.

## Release

Use the `Release LAT Plugin` workflow from the Actions tab.

Inputs:

- `version`: plugin version, for example `0.1.0`.
- `tag`: optional. Empty defaults to `v<version>`.
- `prerelease`: `true` or `false`.
- `draft`: `true` or `false`.

The workflow validates the plugin contract, syncs the version into the manifest files, commits the version bump when needed, creates the git tag, creates the GitHub Release, and uploads the installable zip asset.

## Install In LAT

1. Open LAT Plugin Manager.
2. Login GitHub.
3. Click `Discover Plugins`.
4. Add source:
   - Type: `GitHub Org` or `GitHub User`.
   - Host: `github.com`.
   - Name: owner/org containing the plugin repo.
5. Click `Discover`.
6. Open `Releases` for the plugin.
7. Click `Install` on the desired release.

## Plugin Result Channel

`plugin/main.py` includes a helper that emits final results through LAT Agent's expected result channel:

- Windows: `LAT_RESULT_CHANNEL=tcp`.
- Linux/macOS: file descriptor `3`.
- Local testing fallback: prints JSON to stdout when no LAT result channel is present.

## Runtime

The template uses the LAT Agent Python runtime by default:

```json
"runtime": {
  "type": "agent"
}
```

If your plugin needs dependencies, switch both manifests to a venv runtime:

```json
"runtime": {
  "type": "venv",
  "path": ".venv",
  "requirements": "requirements.txt",
  "auto_create": true,
  "auto_install": true,
  "clean_pythonpath": true
}
```
