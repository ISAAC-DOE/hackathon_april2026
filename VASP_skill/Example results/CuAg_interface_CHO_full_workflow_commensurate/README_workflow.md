# Cu-Ag interface / CHO full workflow (commensurate_1d) using skill v6.2

This workflow was rebuilt against the updated skill, which adds ISAAC intent records and tighter interface/adsorbate validation rules.

## What is fully generated now

### `01_relax/`
Fully runnable from scratch:
- `POSCAR`
- `INCAR`
- `KPOINTS`
- `POTCAR` placeholder
- `submit.sh`
- `run_custodian.py`
- `metadata.json`
- `isaac_intent_record.json`

Resolved slab construction:
- surface: `CuAg_interface`
- adsorbate: `CHO`
- mode: `relax`
- interface match mode: `commensurate_1d`
- commensurate pair: Cu:Ag = `9:8`
- residual mismatch: `0.4692%`
- common matched length along **b**: `23.059813 Å`
- total atoms in relax POSCAR: `275`

CHO placement:
- interface-region bridge site
- chosen bridge pair: cross-boundary `Cu-Ag`
- carbon anchored above the midpoint of that pair
- O tilted away from surface normal
- H placed out of the C–O / surface-normal plane
- bottom metal layer fixed; upper metal layers + adsorbate relaxed

## What is staged but not yet finalized

The updated skill explicitly requires `parent_contcar_path` for:
- `02_static_after_relax/`
- `03_freq_after_relax/`
- `04_solvation_after_relax/`
- `05_cp_after_relax/`

So those folders contain:
- step-specific `INCAR`
- `KPOINTS`
- `POTCAR` placeholder
- `submit.sh`
- `run_custodian.py`
- `metadata.stage.json`
- `README_stage.md`

After `01_relax/CONTCAR` exists, finalize any step with:

```bash
cp ../scripts/prepare_step_from_parent.py .
python prepare_step_from_parent.py --mode MODE --parent ../01_relax/CONTCAR
```

Examples:
```bash
cd 02_static_after_relax
cp ../scripts/prepare_step_from_parent.py .
python prepare_step_from_parent.py --mode static --parent ../01_relax/CONTCAR
```

```bash
cd 03_freq_after_relax
cp ../scripts/prepare_step_from_parent.py .
python prepare_step_from_parent.py --mode freq --parent ../01_relax/CONTCAR
```

```bash
cd 04_solvation_after_relax
cp ../scripts/prepare_step_from_parent.py .
python prepare_step_from_parent.py --mode solvation --parent ../01_relax/CONTCAR
```

For constant-potential:
```bash
cd 05_cp_after_relax
cp ../scripts/prepare_step_from_parent.py .
python prepare_step_from_parent.py --mode cp --parent ../01_relax/CONTCAR --target-mu -0.70
```

That helper will:
- copy `CONTCAR -> POSCAR`
- generate `metadata.json`
- generate `isaac_intent_record.json`
- for `freq`, freeze the slab and leave only the CHO atoms unfrozen
- for `cp`, replace the `TARGETMU` placeholder when provided

## What is only a template

### `06_neb_template/`
NEB is not generated because the updated skill requires **both**:
- reactant endpoint (`parent_contcar_path`)
- product endpoint (`product_contcar_path`)

Only a template INCAR/KPOINTS/job wrapper is included for that stage.
