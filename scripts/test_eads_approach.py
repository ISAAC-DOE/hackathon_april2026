"""Quick test: which approach gives correct E_ads for CO on Cu(111)?"""
import torch
torch.serialization.add_safe_globals([slice])
from fairchem.core import FAIRChemCalculator, pretrained_mlip
from ase.build import fcc111, molecule, add_adsorbate
from ase.optimize import LBFGS
from ase.constraints import FixAtoms
import numpy as np

pu = pretrained_mlip.get_predict_unit("uma-s-1p2")

# 1. Slab+CO with oc20
slab = fcc111("Cu", size=(3,3,4), vacuum=15.0, periodic=True)
slab.pbc = [True,True,True]
z = slab.positions[:,2]; fix = z < z.min() + (z.max()-z.min())*0.55
slab.set_constraint(FixAtoms(mask=fix))
add_adsorbate(slab, molecule("CO"), height=1.85, position="ontop")
slab.calc = FAIRChemCalculator(predict_unit=pu, task_name="oc20")
LBFGS(slab, logfile=None).run(fmax=0.05, steps=200)
e_slab_co = slab.get_potential_energy()
print(f"E(slab+CO, oc20) = {e_slab_co:.4f}")

# 2. Clean slab with oc20
clean = fcc111("Cu", size=(3,3,4), vacuum=15.0, periodic=True)
clean.pbc = [True,True,True]
z = clean.positions[:,2]; fix = z < z.min() + (z.max()-z.min())*0.55
clean.set_constraint(FixAtoms(mask=fix))
clean.calc = FAIRChemCalculator(predict_unit=pu, task_name="oc20")
LBFGS(clean, logfile=None).run(fmax=0.05, steps=200)
e_slab = clean.get_potential_energy()
print(f"E(slab, oc20) = {e_slab:.4f}")

# 3. CO gas with oc20 (molecule in periodic box)
co = molecule("CO"); co.center(vacuum=10.0); co.pbc=[True,True,True]
co.calc = FAIRChemCalculator(predict_unit=pu, task_name="oc20")
LBFGS(co, logfile=None).run(fmax=0.01, steps=100)
e_co_oc20 = co.get_potential_energy()
print(f"E(CO gas, oc20) = {e_co_oc20:.4f}")

# 4. CO gas with omol
co2 = molecule("CO"); co2.center(vacuum=10.0); co2.pbc=[True,True,True]
co2.calc = FAIRChemCalculator(predict_unit=pretrained_mlip.get_predict_unit("uma-s-1p2"), task_name="omol")
LBFGS(co2, logfile=None).run(fmax=0.01, steps=100)
e_co_omol = co2.get_potential_energy()
print(f"E(CO gas, omol) = {e_co_omol:.4f}")

# 5. OC20 atomic refs
refs = pretrained_mlip.get_reference_energies("uma-s-1p2", "atom_refs")
oc20_refs = refs["oc20_elem_refs"]
e_co_atomref = float(oc20_refs[6]) + float(oc20_refs[8])  # C + O
print(f"E(CO, oc20 atomic refs) = {e_co_atomref:.4f}")

print(f"\n--- Adsorption energies ---")
print(f"Method 1: all oc20           E_ads = {e_slab_co - e_slab - e_co_oc20:.4f} eV")
print(f"Method 2: slab oc20 + gas omol E_ads = {e_slab_co - e_slab - e_co_omol:.4f} eV")
print(f"Method 3: oc20 atomic refs    E_ads = {e_slab_co - e_slab - e_co_atomref:.4f} eV")
print(f"\nExpected: ~ -0.5 eV (RPBE, no dispersion)")
print(f"DFT ref:  -0.45 eV (RPBE), -0.87 eV (PBE)")
