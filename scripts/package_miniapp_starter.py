#!/usr/bin/env python3
"""Build deterministic Mini Program starter distribution archives with provenance."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "apps" / "miniapp" / "starter.manifest.json"
EXTRACTOR = ROOT / "scripts" / "extract_miniapp_starter.py"
ARCHIVE_ROOT = "miniapp-starter"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_revision(explicit: str | None) -> str:
    if explicit:
        return explicit.strip()
    env_revision = os.environ.get("GITHUB_SHA", "").strip()
    if env_revision:
        return env_revision
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def normalized_mode(relative: Path) -> int:
    if relative.parts and relative.parts[0] == "scripts":
        return 0o755
    return 0o644


def collect_files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def write_internal_provenance(root: Path, revision: str, manifest_sha: str) -> None:
    payload = {
        "schemaVersion": 1,
        "sourceRepository": "avaargsh/esports-companion",
        "sourceRevision": revision,
        "starterManifestSha256": manifest_sha,
        "generator": "scripts/package_miniapp_starter.py",
    }
    (root / "STARTER-PROVENANCE.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def create_tar_gz(source: Path, output: Path) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path in collect_files(source):
                    relative = path.relative_to(source)
                    data = path.read_bytes()
                    info = tarfile.TarInfo(
                        name=f"{ARCHIVE_ROOT}/{relative.as_posix()}"
                    )
                    info.size = len(data)
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mode = normalized_mode(relative)
                    tar.addfile(info, fileobj=__import__("io").BytesIO(data))


def create_zip(source: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in collect_files(source):
            relative = path.relative_to(source)
            data = path.read_bytes()
            info = zipfile.ZipInfo(
                filename=f"{ARCHIVE_ROOT}/{relative.as_posix()}",
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = normalized_mode(relative) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_inventory(source: Path) -> list[dict[str, object]]:
    inventory: list[dict[str, object]] = []
    for path in collect_files(source):
        relative = path.relative_to(source).as_posix()
        inventory.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        )
    return inventory


def write_external_provenance(
    output: Path,
    revision: str,
    manifest_sha: str,
    inventory: list[dict[str, object]],
    archives: list[Path],
) -> None:
    payload = {
        "schemaVersion": 1,
        "sourceRepository": "avaargsh/esports-companion",
        "sourceRevision": revision,
        "starterManifestSha256": manifest_sha,
        "archiveRoot": ARCHIVE_ROOT,
        "files": inventory,
        "artifacts": [
            {
                "name": archive.name,
                "sha256": sha256_file(archive),
                "size": archive.stat().st_size,
            }
            for archive in archives
        ],
    }
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_checksums(output: Path, paths: list[Path]) -> None:
    lines = [f"{sha256_file(path)}  {path.name}" for path in paths]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-revision")
    args = parser.parse_args()

    output_dir = args.output.resolve()
    if output_dir == ROOT or ROOT in output_dir.parents:
        raise SystemExit("output must be outside the repository root")

    revision = source_revision(args.source_revision)
    manifest_sha = sha256_file(MANIFEST)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="miniapp-starter-") as temp:
        extracted = Path(temp) / "source"
        subprocess.run(
            [sys.executable, str(EXTRACTOR), str(extracted)],
            check=True,
        )
        write_internal_provenance(extracted, revision, manifest_sha)
        inventory = build_inventory(extracted)

        tar_path = output_dir / "miniapp-starter.tar.gz"
        zip_path = output_dir / "miniapp-starter.zip"
        create_tar_gz(extracted, tar_path)
        create_zip(extracted, zip_path)

    provenance_path = output_dir / "miniapp-starter.provenance.json"
    write_external_provenance(
        provenance_path,
        revision,
        manifest_sha,
        inventory,
        [tar_path, zip_path],
    )

    checksums_path = output_dir / "SHA256SUMS"
    write_checksums(
        checksums_path,
        [tar_path, zip_path, provenance_path],
    )

    print(f"Mini Program starter distribution written to {output_dir}")
    for path in (tar_path, zip_path, provenance_path, checksums_path):
        print(f"{path.name}: {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
