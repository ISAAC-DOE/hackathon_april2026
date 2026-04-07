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

## Progress (Day 1 — April 7)

### Completed
- [x] ISAAC API access verified — 79 records in database, API healthy
- [x] FairCHEM/UMA v2.19.0 installed on S3DF (`fairchem` conda env)
- [x] UMA validated on both **ada (L40S)** and **ampere (A100)** GPU partitions
- [x] **Systematic UMA benchmark: 56 calculations completed** (7 surfaces × 8 adsorbates)
  - Surfaces: Cu(111), Cu(100), Cu(211), Au(111), Ag(111), Cu₃Au(111), Cu₃Ag(111)
  - Adsorbates: CO, H, OH, CHO, COH, OCCO, COOH, CO₂
  - E_ads(CO/Cu111) = -0.42 eV vs DFT RPBE = -0.45 eV (0.03 eV error)
  - Full relaxation in ~3 seconds per system on GPU
- [x] ISAAC database queried — 37 Cu-Au CO₂RR performance records analyzed
- [x] Discord bot running for team communication
- [x] Hypothesis schema reviewed from autoCatalysisAgent proof-of-concept

### Key Finding from Database Analysis
The Cu-Au CO₂RR data shows clear **geometry-dependent C₂H₄ selectivity**:
- 80μm Cu / 20μm Au stripes → **25.8% FE(C₂H₄)** (best)
- 160μm Cu / 20μm Au → 15.4% FE(C₂H₄)
- 20μm Cu / 80μm Au → only 2% FE(C₂H₄)
- Pure Cu → <1% FE(C₂H₄)

This supports the CO spillover / tandem catalysis hypothesis.

## 3-Day Plan (Detailed)

### Day 1 (April 7): Setup + Data Ingestion ← TODAY

#### Step 1.1: Infrastructure (DONE)
- [x] Git repo: `ISAAC-DOE/hackathon_april2026`
- [x] ISAAC API + Edison API tokens in `.env`
- [x] FairCHEM/UMA working on S3DF (ada + ampere)
- [x] Discord bot for team coordination

#### Step 1.2: System Selection (IN PROGRESS)
- [ ] **Decision**: Which catalysis system for the hackathon demo?
  - Option A: **Continue Cu-Au CO₂RR** — 37 records already in ISAAC, hypothesis schema proven
  - Option B: **New system** from someone in the room with fresh data
  - Option C: **Cu-Ag CO₂RR** — extend existing work to second alloy
- [ ] Identify 5-7 key experimental observations (OBS-1 through OBS-N) to score hypotheses against

#### Step 1.3: Literature Ingestion
- [ ] Run Edison queries for the chosen system's mechanisms
  - Query 1: `"{system} CO2 reduction mechanism selectivity"`
  - Query 2: `"{system} C-C coupling pathway DFT"`
  - Query 3: `"{system} faradaic efficiency composition dependence"`
- [ ] Extract competing mechanisms from top papers
- [ ] Create **literature-type records** in ISAAC (or `evidence` with `record_domain: literature`)

#### Step 1.4: Hypothesis Generation
- [ ] Generate 5-8 hypotheses using the structured schema (`hypothesis_schema.json`)
- [ ] Each hypothesis must have:
  - Falsifiable statement
  - Origin (literature/DFT/data pattern) with reasoning chain
  - Mechanism with species, elementary steps, length scale
  - Quantitative predictions with falsification criteria
- [ ] Create observation scoring matrix (OBS-1 through OBS-N vs H-001 through H-00M)

### Day 2 (April 8): The Agent Loop

#### Step 2.1: Hypothesis → Intent Records (Morning)
- [ ] For each hypothesis, identify what DFT calculation would test it
- [ ] Create **intent records** in ISAAC for the top 3-5 hypotheses
  - Include: computation method, slab model, output quantity, success criteria
  - Link to the hypothesis that motivated the calculation
- [ ] Submit intent records to ISAAC via API

#### Step 2.2: Fast Screening with UMA (Morning)
- [ ] Run UMA calculations for all intent records
  - Use `scripts/uma_systematic_benchmark.py` as template
  - Compare UMA adsorption energies across hypothesized active sites
- [ ] Create **evidence records** in ISAAC with UMA results
  - Mark as `method.family: "MLIP"`, `method.functional_name: "UMA-s-1p2"`
  - Link to intent via `derived_from` + `matched_computational_method`

#### Step 2.3: DFT Validation (Afternoon)
- [ ] For the top 2-3 discriminating calculations, submit VASP jobs
  - Use existing VASP setup from `~/claudeS3DF`
  - PBE+D3 + VASPsol on 4×4 slabs (matching prior work)
- [ ] Create evidence records when complete

#### Step 2.4: Hypothesis Ranking Engine (Afternoon)
- [ ] Build ranking script: `scripts/rank_hypotheses.py`
  - Input: hypothesis JSON files + ISAAC evidence records
  - Scoring: +1 (supports), 0 (neutral), -1 (contradicts) per observation
  - Output: ranked table with status (supported/eliminated/needs_more_data)
- [ ] First ranking pass with existing data
- [ ] Second pass after UMA results arrive

#### Step 2.5: Monitoring Agent (Evening)
- [ ] Build `scripts/monitor_isaac.py` — polls ISAAC API every 5 minutes
  - Watches for new evidence records
  - When new evidence arrives: re-runs ranking, reports changes
  - Suggests next highest-value calculation
- [ ] Connect to Discord for notifications

### Day 3 (April 9): Demo + Integration

#### Step 3.1: End-to-End Demo (Morning)
- [ ] Live demo: submit intent → UMA computes → evidence posted → hypothesis re-ranked
- [ ] Show the full chain: literature → hypothesis → prediction → test → evidence → update
- [ ] Highlight: what would have taken weeks manually, done in minutes

#### Step 3.2: Results Analysis (Morning)
- [ ] Compile final hypothesis ranking table
- [ ] Document which hypotheses were supported/eliminated and why
- [ ] Compare UMA vs DFT where both are available

#### Step 3.3: Presentation + Writeup (Afternoon)
- [ ] Prepare slides for ModCon demo
- [ ] Document architecture: ISAAC schema + agent workflow
- [ ] List lessons learned and schema improvements
- [ ] Push all code and results to GitHub

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
