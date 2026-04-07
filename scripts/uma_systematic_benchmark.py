"""
Systematic UMA Benchmark: CO2RR intermediates on Cu-based surfaces
=================================================================
Benchmarks all UMA + eSEN models across multiple surfaces and adsorbates.
Following methodology from ChemRxiv 10.26434/chemrxiv.10001728.

Models:  uma-s-1p2, uma-m-1p1, uma-s-1p1, esen-sm-conserving-all-oc25
Surfaces: Cu(111), Cu(100), Cu(211) step, Cu3Au(111), Cu3Ag(111)
Adsorbates: CO, H, OH, CHO, OCCO, CO2, COOH

Usage: python uma_systematic_benchmark.py --model uma-s-1p2 --surface Cu111
       python uma_systematic_benchmark.py --model all --surface all
"""
import torch
torch.serialization.add_safe_globals([slice])

import argparse
import json
import time
import os
import numpy as np
from ase import Atoms
from ase.build import fcc111, fcc100, fcc211, molecule, add_adsorbate
from ase.optimize import BFGS
from ase.constraints import FixAtoms
from fairchem.core import FAIRChemCalculator, pretrained_mlip

# ── Configuration ──────────────────────────────────────────────────────

MODELS = {
    "uma-s-1p2": {"task_slab": "oc20", "task_mol": "omol"},
    "uma-m-1p1": {"task_slab": "oc20", "task_mol": "omol"},
    "uma-s-1p1": {"task_slab": "oc20", "task_mol": "omol"},
    "esen-sm-conserving-all-oc25": {"task_slab": "oc20", "task_mol": "omol"},
}

# DFT reference values (eV) from literature for validation
# CO on Cu: PBE ~ -0.7 to -1.0, RPBE ~ -0.3 to -0.6
DFT_REFERENCES = {
    "Cu111_CO_ontop":   {"PBE": -0.87, "RPBE": -0.45, "PBE+D3": -1.20, "source": "Hammer 1999, Xu 2023"},
    "Cu100_CO_ontop":   {"PBE": -0.95, "RPBE": -0.55, "source": "Xu 2023"},
    "Cu111_H_fcc":      {"PBE": -0.45, "RPBE": -0.25, "source": "Norskov 2005"},
    "Cu111_OH_fcc":     {"PBE": -3.20, "RPBE": -2.90, "source": "Norskov 2005"},
    "Cu111_CHO_ontop":  {"PBE": -1.60, "source": "Nie 2013"},
}

# ── Surface builders ───────────────────────────────────────────────────

def build_surface(surface_name, size=(3, 3, 4), vacuum=15.0):
    """Build a surface slab with bottom 2 layers fixed."""
    builders = {
        "Cu111": lambda: fcc111("Cu", size=size, vacuum=vacuum, periodic=True),
        "Cu100": lambda: fcc100("Cu", size=size, vacuum=vacuum, periodic=True),
        "Cu211": lambda: fcc211("Cu", size=(3, 3, 4), vacuum=vacuum),
        "Au111": lambda: fcc111("Au", size=size, vacuum=vacuum, periodic=True),
        "Ag111": lambda: fcc111("Ag", size=size, vacuum=vacuum, periodic=True),
        "Cu3Au111": lambda: _build_alloy_surface("Cu", "Au", 0.25, size, vacuum),
        "Cu3Ag111": lambda: _build_alloy_surface("Cu", "Ag", 0.25, size, vacuum),
    }
    if surface_name not in builders:
        raise ValueError(f"Unknown surface: {surface_name}. Available: {list(builders.keys())}")

    slab = builders[surface_name]()
    slab.pbc = [True, True, True]

    # Fix bottom 2 layers
    z = slab.positions[:, 2]
    z_min, z_max = z.min(), z.max()
    fix_mask = z < z_min + (z_max - z_min) * 0.55
    slab.set_constraint(FixAtoms(mask=fix_mask))

    return slab, int(sum(fix_mask))


def _build_alloy_surface(host, dopant, dopant_frac, size, vacuum):
    """Build alloy surface: replace top-layer atoms with dopant."""
    slab = fcc111(host, size=size, vacuum=vacuum, periodic=True)
    z = slab.positions[:, 2]
    top_layer_z = z.max()
    top_atoms = [i for i, zi in enumerate(z) if abs(zi - top_layer_z) < 0.5]

    n_replace = max(1, int(len(top_atoms) * dopant_frac))
    rng = np.random.default_rng(42)
    replace_idx = rng.choice(top_atoms, n_replace, replace=False)

    symbols = list(slab.get_chemical_symbols())
    for i in replace_idx:
        symbols[i] = dopant
    slab.set_chemical_symbols(symbols)
    return slab


# ── Adsorbate builders ─────────────────────────────────────────────────

def build_adsorbate(name, surface_name="Cu111"):
    """Return ASE Atoms for an adsorbate and its preferred site.
    Site selection depends on the surface type."""
    # Default sites for (111) surfaces
    site_map_111 = {"CO": "ontop", "H": "fcc", "OH": "fcc", "CHO": "ontop",
                    "COH": "ontop", "OCCO": "bridge", "CO2": "ontop", "COOH": "ontop"}
    # (100) surfaces: use "hollow" instead of "fcc"
    site_map_100 = {"CO": "ontop", "H": "hollow", "OH": "hollow", "CHO": "ontop",
                    "COH": "ontop", "OCCO": "bridge", "CO2": "ontop", "COOH": "ontop"}
    # (211) surfaces: use "ontop" for everything (step sites)
    site_map_211 = {k: "ontop" for k in site_map_111}
    site_map_211["OCCO"] = "ontop"

    if "100" in surface_name:
        site_map = site_map_100
    elif "211" in surface_name:
        site_map = site_map_211
    else:
        site_map = site_map_111

    adsorbates = {
        "CO":   {"atoms": molecule("CO"), "height": 1.85},
        "H":    {"atoms": Atoms("H", positions=[[0, 0, 0]]), "height": 1.0},
        "OH":   {"atoms": molecule("OH"), "height": 1.85},
        "CHO":  {"atoms": _build_cho(), "height": 1.90},
        "COH":  {"atoms": _build_coh(), "height": 1.85},
        "OCCO": {"atoms": _build_occo(), "height": 1.90},
        "CO2":  {"atoms": molecule("CO2"), "height": 2.50},
        "COOH": {"atoms": _build_cooh(), "height": 1.90},
    }
    if name not in adsorbates:
        raise ValueError(f"Unknown adsorbate: {name}. Available: {list(adsorbates.keys())}")
    info = adsorbates[name]
    info["site"] = site_map[name]
    return info


def _build_cho():
    """Build CHO (formyl) adsorbate: C at bottom, H and O on top."""
    return Atoms("CHO", positions=[[0, 0, 0], [0.6, 0.6, 0.5], [0, 0, 1.20]])


def _build_coh():
    """Build COH adsorbate: C binds to surface, OH on top."""
    return Atoms("COH", positions=[[0, 0, 0], [0, 0, 1.30], [0, 0.93, 1.67]])


def _build_occo():
    """Build OCCO (CO dimer) adsorbate for C-C coupling."""
    return Atoms("OCCO", positions=[
        [-0.6, 0, 1.20],  # O
        [-0.6, 0, 0.0],   # C
        [0.6, 0, 0.0],    # C
        [0.6, 0, 1.20],   # O
    ])


def _build_cooh():
    """Build COOH (carboxyl) adsorbate."""
    return Atoms("COOH", positions=[
        [0, 0, 0],        # C
        [-0.6, 0.6, 0.8], # O (carbonyl)
        [0.6, -0.6, 0.8], # O (hydroxyl)
        [1.2, -1.2, 1.3], # H
    ])


# ── Calculator ─────────────────────────────────────────────────────────

def make_calc(model_name, task):
    """Create FAIRChemCalculator."""
    pu = pretrained_mlip.get_predict_unit(model_name)
    return FAIRChemCalculator(predict_unit=pu, task_name=task)


# ── Single benchmark run ──────────────────────────────────────────────

def run_benchmark(model_name, surface_name, adsorbate_name, fmax=0.05, max_steps=300):
    """Run a complete adsorption energy benchmark."""
    tasks = MODELS[model_name]
    result = {
        "model": model_name,
        "surface": surface_name,
        "adsorbate": adsorbate_name,
        "fmax": fmax,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    try:
        # 1. Build and relax slab + adsorbate
        print(f"\n{'='*60}")
        print(f"  {model_name} | {surface_name} + {adsorbate_name}")
        print(f"{'='*60}")

        slab, n_fixed = build_surface(surface_name)
        ads_info = build_adsorbate(adsorbate_name, surface_name)

        if "211" in surface_name:
            # Cu(211) doesn't support named sites — place above the step edge atom
            z = slab.positions[:, 2]
            top_idx = int(np.argmax(z))
            pos_xy = slab.positions[top_idx, :2]
            add_adsorbate(slab, ads_info["atoms"], height=ads_info["height"], position=pos_xy)
        else:
            add_adsorbate(slab, ads_info["atoms"], height=ads_info["height"], position=ads_info["site"])

        n_atoms = len(slab)
        print(f"  Slab+ads: {n_atoms} atoms ({n_fixed} fixed)")

        slab.calc = make_calc(model_name, tasks["task_slab"])

        t0 = time.time()
        opt = BFGS(slab, logfile=None)
        converged = opt.run(fmax=fmax, steps=max_steps)
        t_slab_ads = time.time() - t0

        e_slab_ads = slab.get_potential_energy()
        forces = slab.get_forces()
        final_fmax = float(np.abs(forces).max())
        n_steps_ads = opt.nsteps

        print(f"  E(slab+ads) = {e_slab_ads:.4f} eV  ({n_steps_ads} steps, {t_slab_ads:.1f}s, fmax={final_fmax:.4f})")

        result["E_slab_ads_eV"] = round(e_slab_ads, 6)
        result["n_steps_ads"] = n_steps_ads
        result["time_slab_ads_s"] = round(t_slab_ads, 2)
        result["converged_ads"] = final_fmax < fmax
        result["final_fmax_ads"] = round(final_fmax, 6)
        result["n_atoms"] = n_atoms

        # 2. Clean slab
        clean_slab, _ = build_surface(surface_name)
        clean_slab.calc = make_calc(model_name, tasks["task_slab"])

        t0 = time.time()
        opt_clean = BFGS(clean_slab, logfile=None)
        opt_clean.run(fmax=fmax, steps=max_steps)
        t_slab = time.time() - t0

        e_slab = clean_slab.get_potential_energy()
        n_steps_slab = opt_clean.nsteps
        print(f"  E(slab)     = {e_slab:.4f} eV  ({n_steps_slab} steps, {t_slab:.1f}s)")

        result["E_slab_eV"] = round(e_slab, 6)
        result["time_slab_s"] = round(t_slab, 2)

        # 3. Gas-phase reference using oc20 task (same energy scale as slab)
        # CRITICAL: all energies must use the same task to be on the same scale.
        # Using omol or atomic refs gives wrong results due to different energy zeros.
        if adsorbate_name == "H":
            gas = molecule("H2")
            gas.center(vacuum=10.0)
            gas.pbc = [True, True, True]
            gas.calc = make_calc(model_name, tasks["task_slab"])
            BFGS(gas, logfile=None).run(fmax=0.01, steps=100)
            e_gas = gas.get_potential_energy() / 2.0
            gas_label = "0.5*H2 (oc20)"
        elif adsorbate_name == "OH":
            h2o = molecule("H2O")
            h2o.center(vacuum=10.0)
            h2o.pbc = [True, True, True]
            h2o.calc = make_calc(model_name, tasks["task_slab"])
            BFGS(h2o, logfile=None).run(fmax=0.01, steps=100)
            e_h2o = h2o.get_potential_energy()
            h2 = molecule("H2")
            h2.center(vacuum=10.0)
            h2.pbc = [True, True, True]
            h2.calc = make_calc(model_name, tasks["task_slab"])
            BFGS(h2, logfile=None).run(fmax=0.01, steps=100)
            e_h2 = h2.get_potential_energy()
            e_gas = e_h2o - 0.5 * e_h2
            gas_label = "H2O - 0.5*H2 (oc20)"
        else:
            gas_mol = build_adsorbate(adsorbate_name, surface_name)["atoms"].copy()
            gas_mol.center(vacuum=10.0)
            gas_mol.pbc = [True, True, True]
            gas_mol.calc = make_calc(model_name, tasks["task_slab"])
            BFGS(gas_mol, logfile=None).run(fmax=0.01, steps=100)
            e_gas = gas_mol.get_potential_energy()
            gas_label = f"{adsorbate_name}(g) (oc20)"

        print(f"  E(gas)      = {e_gas:.4f} eV  [{gas_label}]")
        result["E_gas_eV"] = round(e_gas, 6)
        result["gas_reference"] = gas_label

        # 4. Adsorption energy: E_ads = E(slab+ads) - E(slab) - E(gas), all oc20
        e_ads = e_slab_ads - e_slab - e_gas
        print(f"  ──────────────────────────────────")
        print(f"  E_ads       = {e_ads:.4f} eV")

        # Compare with DFT reference if available
        ref_key = f"{surface_name}_{adsorbate_name}_{ads_info['site']}"
        if ref_key in DFT_REFERENCES:
            ref = DFT_REFERENCES[ref_key]
            for functional, ref_val in ref.items():
                if functional in ("source",):
                    continue
                diff = e_ads - ref_val
                print(f"  vs {functional}: {ref_val:.2f} eV (Δ = {diff:+.2f} eV)")
            result["dft_references"] = ref

        result["E_ads_eV"] = round(e_ads, 6)
        result["status"] = "completed"

        total_time = t_slab_ads + t_slab
        print(f"  Total time: {total_time:.1f}s")
        result["total_time_s"] = round(total_time, 2)

    except Exception as e:
        print(f"  ERROR: {e}")
        result["status"] = "failed"
        result["error"] = str(e)

    return result


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Systematic UMA benchmark for CO2RR")
    parser.add_argument("--model", default="uma-s-1p2",
                        help="Model name or 'all'")
    parser.add_argument("--surface", default="Cu111",
                        help="Surface name or 'all'")
    parser.add_argument("--adsorbate", default="CO",
                        help="Adsorbate name or 'all'")
    parser.add_argument("--outdir", default="results/uma_benchmark",
                        help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    all_surfaces = ["Cu111", "Cu100", "Cu211", "Cu3Au111", "Cu3Ag111", "Au111", "Ag111"]
    all_adsorbates = ["CO", "H", "OH", "CHO", "COH", "OCCO", "COOH", "CO2"]
    all_models = list(MODELS.keys())

    models = all_models if args.model == "all" else [args.model]
    surfaces = all_surfaces if args.surface == "all" else [args.surface]
    adsorbates = all_adsorbates if args.adsorbate == "all" else [args.adsorbate]

    n_total = len(models) * len(surfaces) * len(adsorbates)
    print(f"UMA Systematic Benchmark")
    print(f"Models: {models}")
    print(f"Surfaces: {surfaces}")
    print(f"Adsorbates: {adsorbates}")
    print(f"Total calculations: {n_total}")
    print(f"Output: {args.outdir}")

    all_results = []
    t_start = time.time()

    for model in models:
        for surface in surfaces:
            for adsorbate in adsorbates:
                result = run_benchmark(model, surface, adsorbate)
                all_results.append(result)

                # Save incrementally
                outfile = os.path.join(args.outdir, f"{model}_{surface}_{adsorbate}.json")
                with open(outfile, "w") as f:
                    json.dump(result, f, indent=2)

    # Save combined results
    combined_file = os.path.join(args.outdir, "all_results.json")
    with open(combined_file, "w") as f:
        json.dump(all_results, f, indent=2)

    # Print summary table
    print(f"\n{'='*80}")
    print(f"  SUMMARY — {len(all_results)} calculations in {time.time() - t_start:.1f}s")
    print(f"{'='*80}")
    print(f"{'Model':<30} {'Surface':<12} {'Adsorbate':<10} {'E_ads(eV)':>10} {'Time(s)':>8} {'Status'}")
    print(f"{'-'*80}")
    for r in all_results:
        e_ads = r.get("E_ads_eV", "N/A")
        t = r.get("total_time_s", "N/A")
        e_str = f"{e_ads:>10.4f}" if isinstance(e_ads, (int, float)) else f"{e_ads:>10}"
        t_str = f"{t:>8.1f}" if isinstance(t, (int, float)) else f"{t:>8}"
        print(f"{r['model']:<30} {r['surface']:<12} {r['adsorbate']:<10} {e_str} {t_str} {r['status']}")

    print(f"\nResults saved to {combined_file}")


if __name__ == "__main__":
    main()
