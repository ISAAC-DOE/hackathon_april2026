# VASP Workflow Skills

Skill for generating and running multi-step VASP workflows on CO2RR on bimetallic interfaces.

## Overview

This repo separates workflow orchestration from single-step input generation:

- **`vasp_workflow_orchestrator`**: manages multi-step workflows, dependency tracking, file staging, job submission, monitoring, restart, and final summaries.
- **`vasp_input_generator`**: generates VASP inputs for one calculation step at a time, including `POSCAR`, `INCAR`, `KPOINTS`, `submit.sh`, metadata, and ISAAC intent records.

## Supported Workflows

### Single system
For one surface or surface–adsorbate system:
- `relax`
- then `freq`, `solvation`, and `static` in parallel. 

### Reaction pathway
For reactant/product endpoint analysis and barriers:
- `reactant_relax` + `product_relax`
- optional endpoint post-processing
- optional `neb`
- optional `ts_freq` + `ts_solvation` from the highest-energy NEB image.

## Supported Systems

The input generator supports:
- `Cu111`
- `CuAg_interface`
- `CuAu_interface`

with calculation modes:
- `relax`
- `static`
- `freq`
- `solvation`
- `cp`
- `neb`

## Sample Usage

### Generate a full workflow
> “Run the full analysis workflow for CO on Cu(111): relax, then freq + solvation + static in parallel.”

> “Run the reaction pathway for CO to CHO on a Cu-Au interface: relax both endpoints, NEB, then analyze the transition state.”

### Generate a single calculation step
> “Generate VASP inputs for a CHO relaxation on CuAu_interface using Custodian.”

> “Create a NEB setup for CO to CHO on CuAu_interface with 6 images.”

### Resume or retry
> “Resume an interrupted workflow from `workflow_state.json`.”

> “Retry the failed frequency calculation step.”

## How it Works

1. The orchestrator builds a workflow DAG.
2. Ready steps are staged from parent `CONTCAR` files when needed.
3. The input generator creates the VASP input set for each step.
4. Jobs are submitted and tracked until completion.
5. Results are summarized in `workflow_summary.json`. 

## Key Outputs

- Per-step VASP directories
- `workflow_state.json` for restart/resume
- `workflow_summary.json` for energies, frequencies, and NEB barriers
- `metadata.json` and `isaac_intent_record.json` for each generated step.

## Notes

- The orchestrator does **not** generate VASP inputs itself; it calls the input generator for each step.
- NEB generation requires endpoint structures and VTST-enabled VASP support.
- Custodian-based error recovery is supported when enabled.
