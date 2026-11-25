#!/usr/bin/env python3
"""Build small, edition-specific Fabrica247 release ZIPs."""
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

EDITIONS = {
    "windows-lite": ("Windows-Lite", "install-windows-lite.bat", "windows-lite.json", "Windows"),
    "windows-heavy": ("Windows-Heavy", "install-windows-heavy.bat", "windows-heavy.json", "Windows"),
    "linux-lite": ("Linux-Lite", "install-linux-lite.sh", "linux-lite.json", "Linux"),
    "linux-heavy": ("Linux-Heavy", "install-linux-heavy.sh", "linux-heavy.json", "Linux"),
}
COMMON_FILES = (
    "README.md", "requirements.txt", "services.json", "worker.example.json",
    "worker.env.example", "CONTRIBUTING.md", "PROVIDERS.md", "AGENTS.md.example",
)
COMMON_DIRS = ("fabrica", "docs")


def build_package(source_root: Path, edition: str, version: str, output_dir: Path) -> Path:
    if edition not in EDITIONS:
        raise ValueError(f"Edición desconocida: {edition}")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", version):
        raise ValueError(f"Versión inválida: {version!r}; usá formato semver, por ejemplo 3.0.1")
    label, installer, profile, platform_name = EDITIONS[edition]
    root = source_root.resolve()
    required = [root / installer, root / "profiles" / profile, root / "fabrica" / "__main__.py"]
    missing = [str(p.relative_to(root)) for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError("Faltan archivos necesarios para el paquete: " + ", ".join(missing))

    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"Fabrica247-v{version}-{label}.zip"
    package_root = f"Fabrica247-v{version}-{label}"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        selected = [root / installer, root / "profiles" / profile]
        selected.extend(root / name for name in COMMON_FILES if (root / name).is_file())
        for dirname in COMMON_DIRS:
            folder = root / dirname
            if folder.is_dir():
                selected.extend(p for p in folder.rglob("*") if p.is_file())

        seen = set()
        for path in sorted(selected):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if any(part in {"__pycache__", ".git", ".venv", "node_modules"} for part in rel.parts):
                continue
            if path.suffix in {".pyc", ".pyo"} or path.name in {".env", ".worker.env", "worker.token"}:
                continue
            if rel.as_posix().startswith("profiles/") and rel.name != profile:
                continue
            if rel.as_posix() in seen:
                continue
            seen.add(rel.as_posix())
            zf.write(path, f"{package_root}/{rel.as_posix()}")

        edition_text = "\n".join([
            f"Fabrica247 {version}", f"Edition: {label}", f"Platform: {platform_name}", "",
            f"Install: {installer}",
            "Requirements: Python 3.9+; Git and OpenCode are needed for worker execution.",
            "Heavy editions additionally expect Ollama and a model already installed locally.",
            "This archive contains only the selected edition's installer and profile.",
        ]) + "\n"
        zf.writestr(f"{package_root}/EDITION.txt", edition_text)

    with zipfile.ZipFile(archive) as check:
        names = check.namelist()
        if not any(name.endswith(f"/{installer}") for name in names):
            raise RuntimeError("El ZIP no contiene el instalador de la edición.")
        if not any(name.endswith(f"/profiles/{profile}") for name in names):
            raise RuntimeError("El ZIP no contiene el perfil de la edición.")
        other_profiles = [name for name in names if "/profiles/" in name and name.rsplit("/", 1)[-1] != profile]
        if other_profiles:
            raise RuntimeError("El ZIP contiene perfiles de otras ediciones: " + ", ".join(other_profiles))
        if any(name.endswith((".pyc", ".pyo")) or "/__pycache__/" in name for name in names):
            raise RuntimeError("El ZIP contiene cachés de Python.")
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=sorted(EDITIONS), required=True)
    parser.add_argument("--version", required=True, help="Versión sin prefijo v, por ejemplo 3.0.1")
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()
    version = args.version[1:] if args.version.startswith("v") else args.version
    result = build_package(Path(__file__).resolve().parent, args.edition, version, args.output_dir)
    print(f"Paquete creado: {result} ({result.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
