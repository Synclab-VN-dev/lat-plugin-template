#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROOT_MANIFEST = ROOT / "manifest.json"
PLUGIN_MANIFEST = ROOT / "plugin" / "manifest.json"
LAT_AGENT = ROOT / "lat-agent.json"
REQUIRED_MANIFEST_FIELDS = ("id", "version", "entry", "args", "timeout")
SKIP_DIR_NAMES = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SKIP_FILE_NAMES = {".DS_Store"}


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        fail(f"JSON root must be an object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize_version(raw: str) -> str:
    version = raw.strip()
    if not version:
        fail("version is required")
    if version.startswith("v"):
        version = version[1:]
    return version


def validate_manifest(manifest: dict[str, Any], label: str) -> None:
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            fail(f"{label} missing required field: {field}")

    if not isinstance(manifest["id"], str) or not manifest["id"].strip():
        fail(f"{label}.id must be a non-empty string")
    if not isinstance(manifest["version"], str) or not manifest["version"].strip():
        fail(f"{label}.version must be a non-empty string")
    if not isinstance(manifest["entry"], str) or not manifest["entry"].strip():
        fail(f"{label}.entry must be a non-empty string")
    if not isinstance(manifest["args"], list):
        fail(f"{label}.args must be an array")
    if not isinstance(manifest["timeout"], int | float):
        fail(f"{label}.timeout must be a number")


def validate_contract(root_manifest: dict[str, Any], plugin_manifest: dict[str, Any], lat_agent: dict[str, Any]) -> tuple[str, str]:
    validate_manifest(root_manifest, "manifest.json")
    validate_manifest(plugin_manifest, "plugin/manifest.json")

    if root_manifest["id"] != plugin_manifest["id"]:
        fail("manifest id mismatch between root manifest.json and plugin/manifest.json")
    if root_manifest["version"] != plugin_manifest["version"]:
        fail("manifest version mismatch between root manifest.json and plugin/manifest.json")

    if lat_agent.get("package_type") != "lat_plugin":
        fail("lat-agent.json package_type must be lat_plugin")

    plugin = lat_agent.get("plugin")
    if not isinstance(plugin, dict):
        fail("lat-agent.json missing plugin object")

    if plugin.get("id") != plugin_manifest["id"]:
        fail("lat-agent.json plugin.id must match plugin/manifest.json id")
    if plugin.get("version") != plugin_manifest["version"]:
        fail("lat-agent.json plugin.version must match plugin/manifest.json version")
    if plugin.get("manifest_path", "plugin/manifest.json") != "plugin/manifest.json":
        fail("lat-agent.json plugin.manifest_path must be plugin/manifest.json")

    install = lat_agent.get("install")
    if not isinstance(install, dict) or install.get("source_dir", "plugin") != "plugin":
        fail("lat-agent.json install.source_dir must be plugin")

    entry_path = ROOT / "plugin" / plugin_manifest["entry"]
    if not entry_path.exists() or not entry_path.is_file():
        fail(f"plugin entry file not found: {entry_path}")

    return plugin_manifest["id"], plugin_manifest["version"]


def apply_version(root_manifest: dict[str, Any], plugin_manifest: dict[str, Any], lat_agent: dict[str, Any], version: str) -> None:
    root_manifest["version"] = version
    plugin_manifest["version"] = version
    lat_agent.setdefault("plugin", {})["version"] = version


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIR_NAMES:
        return True
    return path.name in SKIP_FILE_NAMES


def copy_plugin_tree(staging_plugin_dir: Path) -> None:
    source_plugin_dir = ROOT / "plugin"
    for src in sorted(source_plugin_dir.rglob("*")):
        rel = src.relative_to(source_plugin_dir)
        if should_skip(rel):
            continue
        dst = staging_plugin_dir / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def build_zip(staging_dir: Path, package_path: Path) -> None:
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(staging_dir).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a LAT plugin release package")
    parser.add_argument("--version", help="Release version. Leading v is accepted and stripped.")
    parser.add_argument("--output-dir", default="dist", help="Directory for the generated zip")
    parser.add_argument("--sync-version", action="store_true", help="Update manifest versions in place before packaging")
    parser.add_argument("--metadata-file", help="Write package metadata JSON to this path")
    args = parser.parse_args()

    root_manifest = load_json(ROOT_MANIFEST)
    plugin_manifest = load_json(PLUGIN_MANIFEST)
    lat_agent = load_json(LAT_AGENT)

    if args.version:
        version = normalize_version(args.version)
        apply_version(root_manifest, plugin_manifest, lat_agent, version)
        if args.sync_version:
            write_json(ROOT_MANIFEST, root_manifest)
            write_json(PLUGIN_MANIFEST, plugin_manifest)
            write_json(LAT_AGENT, lat_agent)
    else:
        version = str(plugin_manifest.get("version", "")).strip()

    plugin_id, version = validate_contract(root_manifest, plugin_manifest, lat_agent)

    output_dir = (ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_name = f"{plugin_id}-v{version}.zip"
    package_path = output_dir / package_name

    with tempfile.TemporaryDirectory(prefix="lat_plugin_package_") as tmp:
        staging_dir = Path(tmp)
        write_json(staging_dir / "lat-agent.json", lat_agent)
        staging_plugin_dir = staging_dir / "plugin"
        staging_plugin_dir.mkdir(parents=True, exist_ok=True)
        copy_plugin_tree(staging_plugin_dir)
        write_json(staging_plugin_dir / "manifest.json", plugin_manifest)
        build_zip(staging_dir, package_path)

    metadata = {
        "plugin_id": plugin_id,
        "version": version,
        "package_name": package_name,
        "package_path": str(package_path),
    }

    if args.metadata_file:
        metadata_path = (ROOT / args.metadata_file).resolve()
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(metadata_path, metadata)

    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[package_plugin] ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
