#!/usr/bin/env python3
import argparse, json, hashlib, shutil, datetime, random, math
from pathlib import Path

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

def ulid_like():
    import time
    now_ms = int(time.time() * 1000)
    ts = []
    x = now_ms
    for _ in range(10):
        ts.append(ALPHABET[x % 32]); x//=32
    ts = ''.join(reversed(ts))
    rand = ''.join(random.choice(ALPHABET) for _ in range(16))
    return ts + rand

def sha256_file(path: Path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def apply_freq_selective_dynamics(poscar_path: Path, unfrozen_last_n: int):
    lines = poscar_path.read_text().splitlines()
    if len(lines) < 9:
        raise ValueError("POSCAR too short")
    counts = [int(x) for x in lines[6].split()]
    n_atoms = sum(counts)
    coord_start = 8
    # insert Selective dynamics if absent
    if lines[7].strip().lower().startswith("selective"):
        coord_start = 9
    else:
        mode_line = lines[7]
        lines = lines[:7] + ["Selective dynamics", mode_line] + lines[8:]
        coord_start = 9
    if len(lines) < coord_start + n_atoms:
        raise ValueError("POSCAR atom count does not match coordinate lines")
    start_unfrozen = n_atoms - unfrozen_last_n
    new_coords = []
    for idx in range(n_atoms):
        toks = lines[coord_start + idx].split()
        xyz = toks[:3]
        flags = ["T","T","T"] if idx >= start_unfrozen else ["F","F","F"]
        new_coords.append("  " + "  ".join(xyz) + "   " + " ".join(flags))
    lines = lines[:coord_start] + new_coords
    poscar_path.write_text("\n".join(lines) + "\n")

def build_isaac(mode: str, outrel: str, target_mu):
    rec = {
        "isaac_record_version": "1.05",
        "record_id": f"{ulid_like()}_intent_CuAg_CHO_{mode}",
        "record_type": "intent",
        "record_domain": "simulation",
        "source_type": "computation",
        "timestamps": {"created_utc": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"},
        "sample": {
            "material": {"name": "Cu-Ag(111) interface slab with CHO adsorbate", "formula": "CuAg", "provenance": "theoretical"},
            "sample_form": "slab_model"
        },
        "system": {
            "domain": "computational",
            "technique": "DFT",
            "instrument": {"instrument_type": "simulation_engine", "instrument_name": "VASP_Standard", "vendor_or_project": "VASP"},
            "configuration": {"code_version": "6.4.3", "compute_architecture": "CPU"}
        },
        "context": {
            "environment": "in_silico",
            "temperature_K": 0,
            "electrochemistry": {"reaction": "CORR"}
        },
        "computation": {
            "method": {
                "family": "DFT", "functional_class": "GGA", "functional_name": "PBE", "basis_type": "planewave", "pseudopotential": "PAW",
                "cutoff_eV": 400, "spin_treatment": "collinear", "dispersion": "D3", "kpoints": "1x1x1 Monkhorst-Pack"
            },
            "slab_model": {"surface_facet": "111", "layers": 4, "fixed_layers": 1, "vacuum_A": 15.0},
            "potential_method": {"type": "vacuum" if mode in ["static", "freq"] else "implicit_solvent_PZC" if mode == "solvation" else "grand_canonical"},
            "output_quantity": {"quantity": "E_DFT"}
        },
        "assets": [],
        "links": [{"rel": "requires_parent_geometry", "path": "../01_relax/CONTCAR"}]
    }
    if mode == "cp":
        rec["context"]["electrochemistry"]["potential_scale"] = "SHE"
        rec["context"]["electrochemistry"]["potential_setpoint_V"] = None if target_mu is None else -float(target_mu) - 4.6
    for name, aid, role, media in [
        ("INCAR","vasp_incar","workflow_recipe","text/plain"),
        ("POSCAR","vasp_poscar","workflow_recipe","text/plain"),
        ("KPOINTS","vasp_kpoints","workflow_recipe","text/plain"),
        ("metadata.json","skill_metadata","auxiliary_metadata","application/json"),
    ]:
        p = Path(name)
        entry = {"asset_id": aid, "content_role": role, "uri": f"repo://{outrel}/{name}", "media_type": media}
        if p.exists():
            entry["sha256"] = sha256_file(p)
        rec["assets"].append(entry)
    return rec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["static","freq","solvation","cp"])
    ap.add_argument("--parent", required=True, help="Path to parent CONTCAR")
    ap.add_argument("--target-mu", default=None, help="Needed for cp to replace placeholder")
    args = ap.parse_args()

    parent = Path(args.parent)
    if not parent.exists():
        raise FileNotFoundError(parent)
    shutil.copy2(parent, "POSCAR")
    if args.mode == "freq":
        apply_freq_selective_dynamics(Path("POSCAR"), unfrozen_last_n=3)

    meta = json.loads(Path("metadata.stage.json").read_text())
    meta["status"] = "finalized_from_parent"
    meta["parent_contcar_used"] = str(parent)
    if args.mode == "cp" and args.target_mu is not None:
        meta["target_mu"] = float(args.target_mu)
        incar = Path("INCAR").read_text()
        Path("INCAR").write_text(incar.replace("# TARGETMU = <set_this>", f"TARGETMU = {args.target_mu}") + ("\n" if not incar.endswith("\n") else ""))
    Path("metadata.json").write_text(json.dumps(meta, indent=2) + "\n")

    record = build_isaac(args.mode, Path.cwd().name, None if args.target_mu is None else float(args.target_mu))
    Path("isaac_intent_record.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Prepared {args.mode} in {Path.cwd()} from {parent}")

if __name__ == "__main__":
    main()
