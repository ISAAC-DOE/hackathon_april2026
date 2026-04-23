This step is staged but not yet fully materialized.

Reason:
- The updated skill requires `parent_contcar_path` for `static`.
- Therefore POSCAR, metadata.json, and isaac_intent_record.json are finalized only after `01_relax/CONTCAR` exists.

To finalize after relaxation:

```bash
cp ../scripts/prepare_step_from_parent.py .
python prepare_step_from_parent.py --mode static --parent ../01_relax/CONTCAR
```

For `freq`, the helper freezes the slab and leaves only the last three adsorbate atoms (C, O, H) unfrozen.
