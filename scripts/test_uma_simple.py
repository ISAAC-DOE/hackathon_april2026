"""
UMA benchmark: CO adsorption on Cu(111).
Following the methodology from the ChemRxiv paper
"Benchmarking Machine-Learned Potentials for Water-Splitting Catalysts"
(DOI: 10.26434/chemrxiv.10001728/v2).

Key insight from the paper and FairCHEM docs:
- Use task="oc20" for slab+adsorbate (heterogeneous catalysis)
- Use task="omol" for gas-phase molecules
- OC20 task uses atomic reference energies, NOT molecular energies
- For adsorption energy: E_ads = E(slab+ads) - E(slab) - E(ads_gas)
  where slab energies use oc20 task and gas molecule uses omol task
  OR use oc20 for everything with atomic reference corrections
"""
import torch
torch.serialization.add_safe_globals([slice])

from fairchem.core import FAIRChemCalculator
from fairchem.core import pretrained_mlip
from ase.build import fcc111, molecule, add_adsorbate
from ase.optimize import BFGS
from ase.constraints import FixAtoms
import json
import time
import numpy as np

def make_calc(task="oc20"):
    """Create a FAIRChemCalculator with UMA-s-1p2."""
    pu = pretrained_mlip.get_predict_unit("uma-s-1p2")
    return FAIRChemCalculator(predict_unit=pu, task_name=task)

print("=== UMA Benchmark: CO on Cu(111) ===")
print("Following ChemRxiv 10.26434/chemrxiv.10001728 methodology\n")

# ---- 1. Slab + CO (task=oc20) ----
print("--- 1. Slab + CO relaxation (task=oc20) ---")
slab = fcc111("Cu", size=(3, 3, 4), vacuum=15.0, periodic=True)
slab.pbc = [True, True, True]

# Fix bottom 2 layers
z_positions = slab.positions[:, 2]
z_min = z_positions.min()
z_range = z_positions.max() - z_min
fix_mask = z_positions < z_min + z_range * 0.55
slab.set_constraint(FixAtoms(mask=fix_mask))

# Add CO at ontop site
co = molecule("CO")
add_adsorbate(slab, co, height=1.85, position="ontop")
print(f"System: {len(slab)} atoms, {sum(fix_mask)} fixed")

t0 = time.time()
slab.calc = make_calc("oc20")

# Single point
e_sp = slab.get_potential_energy()
f_max = np.abs(slab.get_forces()).max()
print(f"Single point: E={e_sp:.4f} eV, fmax={f_max:.4f} eV/A")

# Relax
opt = BFGS(slab, logfile="-")
opt.run(fmax=0.05, steps=200)
e_slab_co = slab.get_potential_energy()
t_slab_co = time.time() - t0
print(f"Relaxed E(slab+CO) = {e_slab_co:.4f} eV ({t_slab_co:.1f}s)\n")

# ---- 2. Clean slab (task=oc20) ----
print("--- 2. Clean slab relaxation (task=oc20) ---")
clean_slab = fcc111("Cu", size=(3, 3, 4), vacuum=15.0, periodic=True)
clean_slab.pbc = [True, True, True]
z_positions = clean_slab.positions[:, 2]
z_min = z_positions.min()
z_range = z_positions.max() - z_min
fix_mask = z_positions < z_min + z_range * 0.55
clean_slab.set_constraint(FixAtoms(mask=fix_mask))

t0 = time.time()
clean_slab.calc = make_calc("oc20")
opt_clean = BFGS(clean_slab, logfile="-")
opt_clean.run(fmax=0.05, steps=200)
e_slab = clean_slab.get_potential_energy()
t_slab = time.time() - t0
print(f"Relaxed E(slab) = {e_slab:.4f} eV ({t_slab:.1f}s)\n")

# ---- 3. CO gas molecule (task=omol) ----
print("--- 3. CO gas molecule (task=omol) ---")
co_gas = molecule("CO")
co_gas.center(vacuum=10.0)
co_gas.pbc = [True, True, True]
co_gas.info.update({"charge": 0, "spin": 1})

t0 = time.time()
co_gas.calc = make_calc("omol")
opt_co = BFGS(co_gas, logfile="-")
opt_co.run(fmax=0.01, steps=100)
e_co = co_gas.get_potential_energy()
t_co = time.time() - t0
print(f"Relaxed E(CO) = {e_co:.4f} eV ({t_co:.1f}s)\n")

# ---- 4. Adsorption energy ----
# Method A: direct subtraction (may have task mismatch)
e_ads_direct = e_slab_co - e_slab - e_co

# Method B: oc20 atomic reference energies for CO
# From FairCHEM docs: C = -7.282 eV, O = -7.204 eV (oc20 linref)
e_co_oc20_ref = -7.282 + (-7.204)  # = -14.486 eV
e_ads_oc20 = e_slab_co - e_slab - e_co_oc20_ref

print(f"=== RESULTS ===")
print(f"E(slab+CO)  = {e_slab_co:.4f} eV  (task=oc20)")
print(f"E(slab)     = {e_slab:.4f} eV  (task=oc20)")
print(f"E(CO_gas)   = {e_co:.4f} eV  (task=omol)")
print(f"E(CO_ref)   = {e_co_oc20_ref:.4f} eV  (oc20 atomic refs)")
print(f"")
print(f"E_ads(CO) [direct: oc20 - oc20 - omol]  = {e_ads_direct:.4f} eV")
print(f"E_ads(CO) [oc20 refs: oc20 - oc20 - ref] = {e_ads_oc20:.4f} eV")
print(f"")
print(f"DFT reference: ~ -0.5 to -1.0 eV (PBE, no dispersion)")
print(f"DFT+D3 reference: ~ -1.0 to -1.5 eV")
print(f"(Negative = exothermic adsorption)")
print(f"")
print(f"Total time: {t_slab_co + t_slab + t_co:.1f}s")

results = {
    "model": "uma-s-1p2",
    "fairchem_version": "2.19.0",
    "system": "CO on Cu(111) 3x3x4",
    "task_slab": "oc20",
    "task_molecule": "omol",
    "E_slab_CO_eV": round(e_slab_co, 4),
    "E_slab_eV": round(e_slab, 4),
    "E_CO_gas_omol_eV": round(e_co, 4),
    "E_CO_oc20_ref_eV": round(e_co_oc20_ref, 4),
    "E_ads_direct_eV": round(e_ads_direct, 4),
    "E_ads_oc20_ref_eV": round(e_ads_oc20, 4),
    "DFT_reference_range_eV": "-0.5 to -1.5",
    "time_total_s": round(t_slab_co + t_slab + t_co, 1),
}
with open("uma_co_cu111_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Results saved to uma_co_cu111_results.json")
