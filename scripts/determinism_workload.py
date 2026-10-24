"""Deterministic spec-to-tree workload sampled by the determinism matrix."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECTS: dict[str, dict[str, Any]] = {
    "library": {
        "name": "determinism-library",
        "package": "determinism_library",
        "description": "A library rendered by the determinism matrix.",
        "type": "library",
        "license": "MIT",
        "author": "Determinism Author",
    },
    "cli": {
        "name": "determinism-cli",
        "package": "determinism_cli",
        "description": "A CLI rendered by the determinism matrix.",
        "type": "cli",
        "license": "Apache-2.0",
        "author": "Determinism Author",
        "version": "1.2.3",
        "python": ">=3.11",
        "cli": {"command": "determinism-cli"},
        "repository": {
            "owner": "example-owner",
            "name": "determinism-cli",
            "private": False,
        },
    },
}


def _tree_records(root: Path) -> list[dict[str, Any]]:
    records = []
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in files:
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return records


def _tree_digest(records: list[dict[str, Any]]) -> str:
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from repocraft.render import render_project
    from repocraft.spec import validate_spec

    payload: dict[str, Any] = {"projects": {}}
    with tempfile.TemporaryDirectory(prefix="repocraft-workload-") as tmp:
        base = Path(tmp)
        for name, project in PROJECTS.items():
            spec = validate_spec({"schema_version": 1, "project": dict(project)})
            out = base / name
            planned = [
                path.relative_to(out).as_posix() for path in render_project(spec, out, dry_run=True)
            ]
            written = [path.relative_to(out).as_posix() for path in render_project(spec, out)]
            records = _tree_records(out)
            payload["projects"][name] = {
                "spec_sha256": hashlib.sha256(
                    json.dumps(spec, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "planned": sorted(planned),
                "files": records,
                "tree_sha256": _tree_digest(records),
            }
            if sorted(planned) != sorted(written) or not records:
                raise SystemExit(f"{name}: render plan and output disagree; workload is vacuous")
    if not payload["projects"]:
        raise SystemExit("no project was rendered; the workload is vacuous")
    artifact_dir = os.environ.get("DETERMINISM_ARTIFACT_DIR")
    if artifact_dir:
        Path(artifact_dir, "payload.json").write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
