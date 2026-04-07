# ISAAC ModCon Hackathon — April 2026

## Ontology-Driven Scientific Hypothesis Discovery for Catalysis

**Location**: Argonne National Laboratory
**Dates**: April 7-9, 2026
**Team**: 4-5 ISAAC project members

## Goal

Demonstrate that AI agents can discover and rank scientific hypotheses for catalysis using a structured ontology (ISAAC AI-ready records) as the shared knowledge layer — connecting experimental data, DFT calculations, and literature into a machine-readable reasoning chain.

**In 48 hours**: go from raw data to ranked, testable hypotheses with structured evidence.

## Background: What We Already Proved

In a recent proof-of-concept on Cu-Au/Cu-Ag CO₂ electroreduction ([autoCatalysisAgent repo](https://github.com/dimosthenisSLAC/autoCatalysisAgent)), we demonstrated:

- **37 scientific discoveries** from automated hypothesis generation, ranking, and testing
- **140+ DFT calculations** on S3DF, driven by structured hypothesis testing
- **Ontology-driven DFT workflow**: intent records in ISAAC → agent reads → executes VASP → evidence records back to ISAAC
- **Key innovation**: `computation.output_quantity` prevents comparing incompatible quantities (e.g., raw DFT energy ΔE vs grand canonical free energy ΔG — a mistake that cost us days)
- **Three mechanisms identified**: CO concentration (Cu-Au), galvanic coupling (Cu-Ag), faceting (nanostructures)

## 3-Day Plan

### Day 1: Setup + Data Ingestion

| Person | Task | Deliverable |
|--------|------|-------------|
| **Schema Lead** | Set up ISAAC API access for everyone, walk through schema blocks | Everyone can POST records |
| **Literature Agent** | Run Edison queries on chosen system, extract mechanisms | 5-10 literature records in ISAAC |
| **Computation** | Set up FairCHEM/UMA or prepare DFT intent records | Working intent→evidence demo |
| **Hypothesis Team** | Choose catalysis system, identify key experimental observations | System selected, 5-10 experimental records in ISAAC |

**System selection criteria**: Pick something where (1) someone has experimental data, (2) competing hypotheses exist in literature, (3) simple DFT can discriminate hypotheses.

### Day 2: The Agent Loop

**Morning**: Connect the pieces
- Literature agent finds competing mechanisms
- Create intent records for calculations that TEST the hypotheses
- Submit to compute (FairCHEM for fast screening, DFT for validation)
- Update hypothesis rankings with new evidence

**Afternoon**: The always-on component
- Set up monitoring agent that watches ISAAC for new evidence
- When evidence arrives → re-rank hypotheses → suggest next experiment
- Minimal version: Python script polling API every 5 minutes

### Day 3: Demo + Writeup

**Morning**: Polish, prepare presentation
**Afternoon**: Demo to broader group, document lessons learned

## Resources

### ISAAC Platform

| Resource | URL |
|----------|-----|
| **API** | `https://isaac.slac.stanford.edu/portal/api` |
| **Health check** | `GET /portal/api/health` |
| **List records** | `GET /portal/api/records?limit=20` |
| **Fetch record** | `GET /portal/api/records/<record_id>` |
| **Validate (dry-run)** | `POST /portal/api/validate` |
| **Submit record** | `POST /portal/api/records` |
| **Wiki** | [ISAAC-DOE/isaac-ai-ready-record/wiki](https://github.com/ISAAC-DOE/isaac-ai-ready-record/wiki) |
| **Schema repo** | [ISAAC-DOE/isaac-ai-ready-record](https://github.com/ISAAC-DOE/isaac-ai-ready-record) |
| **Example records** | [examples/](https://github.com/ISAAC-DOE/isaac-ai-ready-record/tree/main/examples) |

Authentication: Bearer token in `Authorization` header. Token in `.env` file.

### Literature Search

| Resource | Details |
|----------|---------|
| **Edison Scientific** | `POST https://api.edisonsci.com/api/search` with `{"query": "...", "max_results": 5}` |
| Authentication | Bearer token (EDISON_API_KEY in `.env`) |

### Computation

| Resource | Details |
|----------|---------|
| **FairCHEM/UMA** | `pip install fairchem-core`, model `uma-s-1p2`, [docs](https://fair-chem.github.io/) |
| **VASP on S3DF** | Available for SLAC users, GPU (ampere) + CPU (milano) |
| **CatalysisHub** | `api.catalysis-hub.org/graphql` — DFT adsorption energies |

### Proof-of-Concept Reference

| Resource | Details |
|----------|---------|
| **autoCatalysisAgent** | [github.com/dimosthenisSLAC/autoCatalysisAgent](https://github.com/dimosthenisSLAC/autoCatalysisAgent) (branch: scientific-method) |
| **Hypothesis schema** | `hypothesis_schema.json` in that repo |
| **DFT intent/evidence examples** | `data/dft_calc_records/` in that repo |

## ISAAC Record Schema (Quick Reference)

Every record has these blocks:

```
Record
├── sample          # What material (name, formula, form, composition)
├── system          # What instrument/code (domain, technique, version)
├── context         # What conditions (environment, temperature, potential)
├── computation     # How computed (method, slab, potential_method, output_quantity)
├── measurement     # What was observed (series of data channels)
├── descriptors     # What was concluded (named, typed, with uncertainty)
├── assets          # Where is the raw data (URIs with checksums)
└── links           # How records relate (derived_from, validates, etc.)
```

**Record types**:
- `evidence` — completed measurement/calculation with descriptors (must have descriptors)
- `intent` — planned experiment/calculation (no descriptors needed)
- `synthesis` — aggregation of multiple records

**Key vocabulary** (see wiki for full lists):
- `system.technique`: DFT, XAS, chronoamperometry, HPLC, ...
- `context.environment`: operando, in_situ, ex_situ, in_silico
- `descriptors.kind`: absolute, differential, theoretical_metric, ...
- `computation.potential_method.type`: vacuum, CHE, implicit_solvent_PZC, grand_canonical, ...
- `computation.output_quantity.quantity`: delta_E, delta_G_CHE, activation_energy_raw, ...

## Key Principles (Learned the Hard Way)

1. **Always extract the EXACT reported quantity** (ΔE vs ΔG vs ΔG_GC) from papers before comparing to calculations. A schema field (`output_quantity`) now enforces this.

2. **Intent and evidence are SEPARATE records** — intent before computation, evidence after. Linked via `derived_from`.

3. **Vocabulary must be strict** — use controlled vocabulary from the wiki. Free-text in enum fields is rejected.

4. **The ISAAC database is the single source of truth** — everything else (conversations, markdown files, git commits) is ephemeral.

5. **Hypotheses must be falsifiable** — each hypothesis needs specific predictions and criteria for what would disprove it.

6. **Scan product configurations BEFORE running NEB** — find the global minimum of the product state first. A NEB to a metastable state gives a meaningless barrier.

7. **DFT model representativeness matters** — computing correct barriers on the wrong model leads to wrong conclusions. Always ask: does this slab represent the real electrode?

## Quick Start

```bash
# Check API health
curl -s https://isaac.slac.stanford.edu/portal/api/health

# List recent records
curl -s https://isaac.slac.stanford.edu/portal/api/records?limit=5 \
  -H "Authorization: Bearer $ISAAC_API_TOKEN"

# Validate a record (dry-run)
curl -s -X POST https://isaac.slac.stanford.edu/portal/api/validate \
  -H "Authorization: Bearer $ISAAC_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @my_record.json

# Submit a record
curl -s -X POST https://isaac.slac.stanford.edu/portal/api/records \
  -H "Authorization: Bearer $ISAAC_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @my_record.json
```
