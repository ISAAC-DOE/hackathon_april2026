NEB is scaffolded only.

The updated skill requires:
- `parent_contcar_path` for the reactant endpoint
- `product_contcar_path` for the product endpoint
- interpolation into image directories 00 ... 07 for the default 6 images

This workflow therefore includes a template INCAR/KPOINTS/submit script only.
No NEB POSCARs were generated because the product endpoint is not yet available.
