"""Step 2: extract the raw TSE zips into data/raw/extracted/<dataset>/.

The raw zip files in data/raw/ are never modified; only read from and
extracted into a separate directory.

Each zip contains, per dataset: one file per state (27x, covering
Governador/Senador/Deputado Federal/Deputado Estadual only), one
"<name>_BR.csv" file, and one much larger "<name>_BRASIL.csv" file.

Inspection (see README "Scoping decision") showed:
  - The per-state files contain ZERO "Presidente" rows (DS_CARGO never
    equals "Presidente" in them) -- they only carry state/district races.
  - "<name>_BR.csv" contains ONLY "Presidente" rows, for all 26 states +
    DF + ZZ (abroad), both rounds -- i.e. it is already the complete,
    self-contained presidential dataset.
  - "<name>_BRASIL.csv" is the full all-races consolidation (effectively
    BR.csv + every per-state file concatenated), which is not needed
    since this pipeline only wants the presidential race.

So only "<name>_BR.csv" (plus leiame.pdf for documentation) is extracted;
the per-state and *_BRASIL files are redundant for this pipeline's scope
and are left zipped to save time/disk.
"""

from __future__ import annotations

import zipfile

from common import EXTRACTED_DIR, RAW_DIR

DATASETS = ["votacao_candidato_munzona_2026", "detalhe_votacao_munzona_2026"]


def main() -> None:
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    for name in DATASETS:
        zip_path = RAW_DIR / f"{name}.zip"
        out_dir = EXTRACTED_DIR / name
        out_dir.mkdir(parents=True, exist_ok=True)
        wanted = {f"{name}_BR.csv", "leiame.pdf"}
        print(
            f"Extracting {zip_path.name} -> {out_dir} (members: {sorted(wanted)}) ..."
        )
        with zipfile.ZipFile(zip_path) as zf:
            available = set(zf.namelist())
            missing = wanted - available
            if missing:
                raise RuntimeError(
                    f"Expected members not found in {zip_path.name}: {missing}"
                )
            for member in wanted:
                zf.extract(member, out_dir)
        files = sorted(p.name for p in out_dir.rglob("*") if p.is_file())
        print(f"  extracted: {files}")


if __name__ == "__main__":
    main()
