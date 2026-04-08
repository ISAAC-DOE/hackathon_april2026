# ISAAC Hypothesis Record — Schema Extension Proposal

**Version**: 0.1-draft
**Date**: 2026-04-07
**Authors**: Dimosthenis Sokaras, ISAAC team
**Status**: Under review — NOT merged into schema

---

## 1. Motivation

The ISAAC AI-ready record schema (v1.05) captures three record types: **evidence** (completed measurements/computations), **intent** (planned work), and **synthesis** (sample preparation). The scientific method also requires a structured representation of **hypotheses** — falsifiable claims that connect observations, predict outcomes, and are updated as evidence arrives.

The existing `autoCatalysisAgent` hypothesis schema demonstrated the value of structured hypotheses (37 discoveries, 140+ DFT calculations), but it was a standalone JSON format disconnected from the ISAAC record framework. This proposal embeds hypothesis records natively into the ISAAC schema so they:

1. Use the **same blocks** (sample, system, context, descriptors, links, assets)
2. Use the **same controlled vocabulary** (descriptor names, units, link relations)
3. Follow the **same validation pipeline** (JSON Schema + vocabulary + semantic integrity)
4. Participate in the **same knowledge graph** (linked to evidence and intent records via `links`)

---

## 2. Summary of Schema Changes

| Change | Type | Location |
|--------|------|----------|
| Add `"hypothesis"` to `record_type` enum | Vocabulary extension | `record_type` |
| Add `"hypothesis"` to `record_domain` enum | Vocabulary extension | `record_domain` |
| Add new top-level `hypothesis` block | Schema extension | Root properties |
| Add `hypothesis` to conditional validation | Schema extension | `allOf` |
| Add 3 new `links.rel` values | Vocabulary extension | `links.rel` |
| Add 3 new `links.basis` values | Vocabulary extension | `links.basis` |
| Add 2 new `system.technique` values | Vocabulary extension | `system.technique` |
| Add 1 new `system.domain` value | Vocabulary extension | `system.domain` |
| Add new descriptor name vocabulary | Vocabulary extension | `descriptors` |

---

## 3. New `record_type`: `"hypothesis"`

A **hypothesis record** declares a falsifiable scientific claim about a material system. It specifies:

- **What** is claimed (the statement)
- **Why** it was proposed (origin and reasoning chain)
- **How** it could be tested (predictions with falsification criteria)
- **What** the current evidence says (via links to evidence records and scoring in descriptors)

### Lifecycle

```
Evidence/Literature Records          Hypothesis Record          Intent Records
(observations that motivate)         (the claim)                (planned tests)
         │                                │                          │
         │     derived_from               │      motivates           │
         └────────────────────────────────┤                          │
                                          │                          │
                                          └──────────────────────────┘
                                                                     │
                                          ┌──────────────────────────┘
                                          │
                                    Evidence Records
                                    (test results)
                                          │
                                          │  validates / invalidates
                                          │
                                    Hypothesis Record
                                    (status updated via new descriptor output)
```

**Key lifecycle rules:**
- A hypothesis record is **immutable** once created (like all ISAAC records)
- Status changes are recorded as **new descriptor outputs** (the `descriptors.outputs` array grows)
- If the hypothesis needs revision (not just status update), create a **new hypothesis record** linked via `supersedes`
- Agents must **never treat hypothesis predictions as established facts** — they are claims to be tested

---

## 4. The `hypothesis` Block

This is a new top-level block (parallel to `computation`, `measurement`, etc.) that contains hypothesis-specific content.

### 4.1 Block Structure

```
hypothesis
├── statement           # (required) One-sentence falsifiable claim
├── hypothesis_type     # (required) Controlled vocabulary
├── scope               # (required) What system/conditions this applies to
│   ├── material_system     # Free text label
│   ├── reaction            # Reuses context.electrochemistry.reaction vocab
│   └── conditions_summary  # Free text
├── origin              # (required) How this hypothesis was generated
│   ├── source_type         # Controlled vocabulary
│   ├── source_details      # Tool, query, output reference
│   │   ├── tool
│   │   ├── query
│   │   └── output_ref
│   └── reasoning_chain     # (required) Step-by-step reasoning
│       └── [] { step, statement, basis, reference }
├── mechanism           # (optional) Proposed physical/chemical mechanism
│   ├── description
│   ├── species_involved    # Array of adsorbate/species labels
│   ├── elementary_steps    # Array of reaction steps
│   │   └── [] { reaction, role, reference_record_id }
│   ├── rate_limiting_step
│   └── length_scale        # { value_m, description, determined_by }
├── predictions         # (required, minItems: 1) Testable predictions
│   └── [] {
│       prediction_id,
│       descriptor_name,    # MUST match ISAAC descriptor vocabulary
│       direction,          # Controlled vocabulary
│       reference_condition,
│       magnitude,
│       conditions,
│       falsification_criterion
│   }
└── confidence          # (optional) Prior and current confidence
    ├── prior               # Number [0, 1]
    ├── current             # Number [0, 1]
    └── basis               # Free text explanation
```

### 4.2 Field Definitions

#### `hypothesis.statement` (string, required)

One-sentence hypothesis in testable form. Must be falsifiable — it must be possible to imagine evidence that would disprove it.

**Good**: "CO spillover from Au domains to Cu domains is the primary mechanism driving C₂H₄ selectivity enhancement in Cu-Au patterned electrodes, with selectivity scaling inversely with Au-to-Cu domain spacing at spacings below the CO diffusion length (~80 μm)."

**Bad**: "Cu-Au is a good catalyst for CO₂ reduction." (not falsifiable — no specific prediction)

#### `hypothesis.hypothesis_type` (string, required)

Controlled vocabulary:

| Value | Description |
|-------|-------------|
| `mechanistic` | Proposes a specific reaction mechanism or pathway |
| `selectivity` | Claims about product selectivity dependence on a variable |
| `activity` | Claims about catalytic activity (rate, overpotential) |
| `stability` | Claims about catalyst stability or degradation mechanism |
| `scaling` | Claims about scaling relations between descriptors |
| `structural` | Claims about structure-property relationships |
| `transport` | Claims about mass transport or diffusion effects |

#### `hypothesis.scope` (object, required)

Defines the domain of applicability.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `material_system` | string | Yes | Short label: `"Cu-Au"`, `"Cu-Ag"`, `"Pt-Ni"` |
| `reaction` | string | No | Reuses `context.electrochemistry.reaction` vocabulary |
| `conditions_summary` | string | No | Free-text summary of applicable conditions |

#### `hypothesis.origin` (object, required)

Full provenance — how was this hypothesis generated?

##### `hypothesis.origin.source_type` (string, required)

Controlled vocabulary:

| Value | Description |
|-------|-------------|
| `literature_synthesis` | Synthesized from multiple literature sources |
| `data_pattern` | Inferred from patterns in experimental/computed data |
| `computational_screening` | Generated from computational screening (UMA, DFT, ML) |
| `expert_reasoning` | Domain expert knowledge and intuition |
| `analogy` | Transferred from a related material system |
| `mechanistic_analysis` | Derived from reaction mechanism analysis (microkinetic, DFT pathways) |

##### `hypothesis.origin.source_details` (object, optional)

| Property | Type | Description |
|----------|------|-------------|
| `tool` | string | Tool used: `"Edison"`, `"CatMAP"`, `"UMA"`, `"VASP"`, `"Claude"` |
| `query` | string | Query or input that produced this hypothesis |
| `output_ref` | string | File path or URI to the analysis output |

##### `hypothesis.origin.reasoning_chain` (array, required, minItems: 1)

Step-by-step reasoning that led to this hypothesis. Each step is:

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `step` | integer | Yes | Step number (1-indexed) |
| `statement` | string | Yes | What was concluded in this step |
| `basis` | string | Yes | Controlled vocabulary (see below) |
| `reference` | string | No | Record ID, DOI, or description supporting this step |

**`reasoning_chain[].basis` vocabulary:**

| Value | Description |
|-------|-------------|
| `observation` | Based on experimental observation (references evidence record) |
| `computation` | Based on DFT/simulation result (references evidence record) |
| `literature` | Based on published finding (references DOI or literature record) |
| `inference` | Logical deduction from prior steps |
| `analogy` | Transferred from analogous system |
| `mechanism_analysis` | Based on reaction pathway analysis |

#### `hypothesis.mechanism` (object, optional)

The proposed physical/chemical mechanism. Required when `hypothesis_type` is `mechanistic`.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `description` | string | Yes | Prose description of the mechanism |
| `species_involved` | array[string] | Yes | Chemical species: `["CO*", "OCCO*", "H*"]` |
| `elementary_steps` | array[object] | No | Reaction steps (see below) |
| `rate_limiting_step` | string | No | Which step is rate-limiting |
| `length_scale` | object | No | Characteristic length scale (see below) |

##### `hypothesis.mechanism.elementary_steps[]`

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `reaction` | string | Yes | e.g., `"CO* + CO* → OCCO*"` |
| `role` | string | Yes | Enum: `rate_limiting`, `equilibrated`, `irreversible`, `unknown` |
| `reference_record_id` | string | No | ULID of ISAAC evidence/intent record with DFT data for this step |

##### `hypothesis.mechanism.length_scale`

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `value_m` | number | Yes | In meters (e.g., 80e-6 for 80 μm) |
| `description` | string | Yes | What this length scale represents |
| `determined_by` | string | Yes | What sets this scale: `"diffusion"`, `"electronic"`, `"grain_size"`, `"patterning"` |

#### `hypothesis.predictions[]` (array, required, minItems: 1)

Each prediction is a specific, testable claim that maps to an ISAAC descriptor.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `prediction_id` | string | Yes | Short ID: `"P-001"`, `"P-002"` |
| `descriptor_name` | string | Yes | **Must** match ISAAC descriptor vocabulary (e.g., `"faradaic_efficiency.C2H4"`, `"adsorption_energy.CO"`, `"activation_barrier.OCCO_coupling"`) |
| `direction` | string | Yes | Controlled vocabulary (see below) |
| `reference_condition` | string | Yes | What the direction is relative to (e.g., `"pure Cu(111)"`, `"random alloy"`) |
| `magnitude` | string | No | Expected magnitude: `"2-5x increase"`, `">0.2 eV difference"` |
| `conditions` | object | No | Conditions under which prediction holds (free-form, but should use ISAAC vocabulary where applicable) |
| `falsification_criterion` | string | Yes | What observation would **disprove** this prediction |

**`predictions[].direction` vocabulary:**

| Value | Description |
|-------|-------------|
| `increase` | Predicted to increase relative to reference condition |
| `decrease` | Predicted to decrease |
| `no_change` | Predicted to remain unchanged (null hypothesis) |
| `non_monotonic` | Predicted to show a maximum or minimum |
| `threshold` | Predicted to change above/below a critical value |
| `correlation` | Predicted to correlate with another variable |

#### `hypothesis.confidence` (object, optional)

| Property | Type | Description |
|----------|------|-------------|
| `prior` | number [0,1] | Initial confidence before testing |
| `current` | number [0,1] | Current confidence after available evidence |
| `basis` | string | What the confidence assessment is based on |

---

## 5. How Existing Blocks Are Used in Hypothesis Records

### 5.1 `sample`

Describes the material system the hypothesis is about. Uses existing vocabulary.

- `material.name`: The material system (e.g., `"Cu-Au patterned electrode"`)
- `material.formula`: Chemical formula (e.g., `"CuAu"`)
- `material.provenance`: Typically `"theoretical"` or `"literature"`
- `sample_form`: Typically `"film"`, `"nanoparticle"`, or `"slab_model"` depending on what the hypothesis targets

### 5.2 `system`

What generated this hypothesis record.

- `domain`: New value `"analytical"` (see Section 6.2)
- `technique`: New values `"hypothesis_generation"` or `"systematic_review"` (see Section 6.3)
- `instrument`: The agent/tool that generated the hypothesis
  - `instrument_type`: `"reasoning_engine"` (new, see Section 6.4)
  - `instrument_name`: e.g., `"claude_hypothesis_agent"`, `"expert_panel"`
- `configuration`: Flat key-value pairs for agent configuration
  - e.g., `"model_version": "claude-opus-4-6"`, `"literature_search_tool": "Edison"`

### 5.3 `context`

The conditions under which the hypothesis applies. Uses existing vocabulary.

- `environment`: Typically `"in_silico"` (for computationally-generated hypotheses) or `"operando"` / `"in_situ"` if the hypothesis is about specific experimental conditions
- `temperature_K`: The temperature the hypothesis applies to
- `electrochemistry`: Full electrochemistry context (reaction, potential range, electrolyte) — describing the **target conditions** of the hypothesis, not the conditions under which it was generated

### 5.4 `descriptors`

Used for two purposes in hypothesis records:

**Purpose 1: Predicted values** — Quantitative predictions that can be compared against evidence records.

```json
{
  "label": "hypothesis_predictions_v1",
  "generated_utc": "2026-04-07T14:00:00Z",
  "generated_by": { "agent": "hypothesis_generator", "version": "1.0" },
  "descriptors": [
    {
      "name": "faradaic_efficiency.C2H4",
      "kind": "theoretical_metric",
      "source": "auto",
      "value": 0.26,
      "unit": "fraction",
      "definition": "Predicted peak C2H4 selectivity for 80μm Cu / 20μm Au striped electrode at -1.0V RHE",
      "uncertainty": { "sigma": 0.05, "unit": "fraction" }
    }
  ]
}
```

**Purpose 2: Hypothesis status tracking** — Each re-evaluation adds a new output (the array grows over time, providing full history).

```json
{
  "label": "hypothesis_evaluation_v1",
  "generated_utc": "2026-04-07T14:00:00Z",
  "generated_by": { "agent": "ranking_engine", "version": "1.0" },
  "descriptors": [
    {
      "name": "hypothesis_status",
      "kind": "categorical",
      "source": "auto",
      "value": "proposed",
      "unit": "dimensionless",
      "definition": "Current hypothesis status. Vocabulary: proposed, supported, contradicted, eliminated, needs_more_data, superseded",
      "uncertainty": { "confidence": 0.5 }
    },
    {
      "name": "hypothesis_score",
      "kind": "absolute",
      "source": "auto",
      "value": 3,
      "unit": "dimensionless",
      "definition": "Net evidence score: sum of +1 (supporting), 0 (neutral), -1 (contradicting) across all scored observations",
      "uncertainty": { "sigma": 1, "unit": "dimensionless" }
    }
  ]
}
```

**Agent reasoning contract for hypothesis descriptors:**
- `kind: "theoretical_metric"` predictions are **claims**, not measured facts
- When comparing a hypothesis prediction against an evidence descriptor, both must use the same `descriptor.name` and compatible units
- Status descriptors use `kind: "categorical"` with confidence values

### 5.5 `links`

Hypothesis records participate in the knowledge graph via both existing and new link relations.

**Existing relations (unchanged semantics):**

| `rel` | Direction | Usage |
|--------|-----------|-------|
| `derived_from` | hypothesis → evidence/literature | "This hypothesis was derived from analysis of these records" |
| `validates` | evidence → hypothesis | "This evidence supports the hypothesis" (from evidence side) |
| `invalidates` | evidence → hypothesis | "This evidence contradicts the hypothesis" (from evidence side) |
| `follows` | hypothesis → hypothesis | "This hypothesis refines/revises the target hypothesis" |

**New relations (see Section 6.5):**

| `rel` | Direction | Usage |
|--------|-----------|-------|
| `motivates` | hypothesis → intent | "This hypothesis motivated this planned calculation/experiment" |
| `supersedes` | hypothesis → hypothesis | "This hypothesis replaces the target hypothesis" |
| `competes_with` | hypothesis → hypothesis | "This hypothesis offers an alternative explanation to the target" |

### 5.6 `assets`

Standard usage. Typical content roles for hypothesis records:

- `auxiliary_reference`: Literature papers that informed the hypothesis (DOIs)
- `documentation`: Analysis reports, reasoning documents
- `processing_script`: Scripts that generated or ranked the hypothesis
- `supplementary_image`: Diagrams of proposed mechanisms

### 5.7 Blocks NOT used

- `measurement`: Hypothesis records have no measured data series
- `computation`: Hypothesis records do not specify a DFT method (but they may link to computation records)

---

## 6. Vocabulary Extensions

### 6.1 `record_type`

Add: `"hypothesis"` — A falsifiable scientific claim with structured provenance, predictions, and evidence trail.

### 6.2 `system.domain`

Add: `"analytical"` — Record produced by reasoning, synthesis, or meta-analysis rather than direct measurement or simulation.

### 6.3 `system.technique`

Add:
- `"hypothesis_generation"` — Structured generation of scientific hypotheses from data, literature, and reasoning
- `"systematic_review"` — Systematic analysis and synthesis of multiple source records

### 6.4 `system.instrument.instrument_type`

Add: `"reasoning_engine"` — An AI agent, expert panel, or analytical tool that produces hypotheses or meta-analyses.

### 6.5 `links.rel`

Add:
- `"motivates"` — This record motivated the creation of the target record (typically hypothesis → intent)
- `"supersedes"` — This record replaces the target record (typically hypothesis → hypothesis)
- `"competes_with"` — This record offers an alternative explanation to the target (hypothesis → hypothesis, symmetric in meaning)

### 6.6 `links.basis`

Add:
- `"shared_prediction_target"` — Both records make predictions about the same observable
- `"hypothesis_refinement"` — This record is a refined version of the target
- `"literature_analysis"` — Link established through literature review and analysis

### 6.7 New Descriptor Names

Add to `descriptors.hypothesis_evaluation` vocabulary:

| Name | Kind | Unit | Description |
|------|------|------|-------------|
| `hypothesis_status` | categorical | dimensionless | Current status: `proposed`, `supported`, `contradicted`, `eliminated`, `needs_more_data`, `superseded` |
| `hypothesis_score` | absolute | dimensionless | Net evidence score (sum of per-observation ratings) |
| `hypothesis_confidence` | absolute | dimensionless | Current confidence level [0, 1] |
| `observation_score.{OBS_ID}` | categorical | dimensionless | Per-observation rating: `supports`, `contradicts`, `neutral`, `insufficient` |

---

## 7. Validation Rules

### 7.1 JSON Schema Conditional

Add to `allOf`:

```json
{
  "if": {
    "properties": { "record_type": { "const": "hypothesis" } }
  },
  "then": {
    "required": ["hypothesis"],
    "properties": {
      "hypothesis": {
        "required": ["statement", "hypothesis_type", "scope", "origin", "predictions"]
      }
    }
  }
}
```

### 7.2 Semantic Integrity Rules

1. **Prediction descriptor alignment**: Every `hypothesis.predictions[].descriptor_name` should correspond to a known ISAAC descriptor name from the vocabulary. Unknown names trigger a warning (not error) to allow novel descriptors.

2. **Reasoning chain completeness**: `hypothesis.origin.reasoning_chain` must have at least one step. Steps must be numbered sequentially from 1.

3. **Falsification criterion required**: Every prediction must have a non-empty `falsification_criterion`.

4. **No measurement block**: Hypothesis records should not contain a `measurement` block (warning, not error).

5. **Hypothesis-specific link validation**:
   - `motivates` can only appear on hypothesis records (source) pointing to intent records (target)
   - `supersedes` can only link records of the same `record_type`
   - `competes_with` can only link hypothesis records to hypothesis records

### 7.3 Agent Reasoning Contract

- **Never treat hypothesis predictions as measured facts.** Filter by `record_type != "hypothesis"` when aggregating descriptor values for quantitative analysis.
- **Prediction comparison**: When comparing a hypothesis prediction to evidence, verify that the `descriptor_name` matches and that any relevant `computation.output_quantity` values are compatible.
- **Status is the latest**: The current hypothesis status is the `hypothesis_status` descriptor in the **last** (most recent `generated_utc`) output of the descriptors block.
- **Confidence is subjective**: `hypothesis.confidence` values are assessments, not probabilities. They inform prioritization, not statistical inference.

---

## 8. Example Records

### 8.1 Example: CO Spillover Hypothesis (Cu-Au CO₂RR)

```json
{
  "isaac_record_version": "1.05",
  "record_id": "01JSHYP00001CO2RRSPILLOVER",
  "record_type": "hypothesis",
  "record_domain": "hypothesis",
  "source_type": "literature",
  "timestamps": {
    "created_utc": "2026-04-07T14:00:00Z"
  },
  "sample": {
    "material": {
      "name": "Cu-Au patterned electrode for CO2RR",
      "formula": "CuAu",
      "provenance": "literature"
    },
    "sample_form": "film",
    "electrode_type": "patterned_film",
    "composition": {
      "Cu_pct": 80,
      "Au_pct": 20
    }
  },
  "system": {
    "domain": "analytical",
    "technique": "hypothesis_generation",
    "instrument": {
      "instrument_type": "reasoning_engine",
      "instrument_name": "claude_hypothesis_agent",
      "vendor_or_project": "ISAAC"
    },
    "configuration": {
      "model_version": "claude-opus-4-6",
      "literature_search_tool": "Edison"
    }
  },
  "context": {
    "environment": "in_situ",
    "temperature_K": 298.15,
    "electrochemistry": {
      "reaction": "CO2RR",
      "cell_type": "flow_cell",
      "control_mode": "potentiostatic",
      "potential_setpoint_V": -1.0,
      "potential_scale": "RHE",
      "electrolyte": {
        "name": "KHCO3",
        "concentration_M": 1.0
      },
      "pH": 6.8,
      "pH_basis": "nominal"
    },
    "transport": {
      "flow_mode": "gas_diffusion",
      "feed": {
        "phase": "gas",
        "composition": "CO2"
      }
    }
  },
  "hypothesis": {
    "statement": "CO spillover from Au domains to Cu domains is the primary mechanism driving C2H4 selectivity enhancement in Cu-Au patterned electrodes, with selectivity scaling inversely with Au-to-Cu domain spacing at spacings below the CO diffusion length (~80 um).",
    "hypothesis_type": "mechanistic",
    "scope": {
      "material_system": "Cu-Au",
      "reaction": "CO2RR",
      "conditions_summary": "Patterned Cu-Au electrodes in flow cell, -0.8 to -1.2V RHE, 1M KHCO3"
    },
    "origin": {
      "source_type": "literature_synthesis",
      "source_details": {
        "tool": "Edison",
        "query": "Cu-Au CO2 reduction C-C coupling selectivity mechanism"
      },
      "reasoning_chain": [
        {
          "step": 1,
          "statement": "Au selectively reduces CO2 to CO with high faradaic efficiency (>90%) due to weak CO binding (E_ads ~ -0.01 eV)",
          "basis": "computation",
          "reference": "UMA benchmark: E_ads(CO/Au111) = -0.01 eV"
        },
        {
          "step": 2,
          "statement": "Cu binds CO moderately (E_ads ~ -0.42 eV on Cu(111)), enabling subsequent C-C coupling to C2+ products",
          "basis": "computation",
          "reference": "UMA benchmark: E_ads(CO/Cu111) = -0.42 eV"
        },
        {
          "step": 3,
          "statement": "In Cu-Au patterned electrodes, CO produced on Au domains can diffuse to nearby Cu domains, increasing local CO coverage",
          "basis": "literature",
          "reference": "doi:10.1021/jacs.7b10410"
        },
        {
          "step": 4,
          "statement": "Higher local CO coverage on Cu promotes C-C coupling (CO* + CO* -> OCCO*), which is the rate-limiting step for C2H4 formation",
          "basis": "mechanism_analysis",
          "reference": "OCCO coupling barrier from DFT literature"
        },
        {
          "step": 5,
          "statement": "The 80um Cu / 20um Au geometry shows highest C2H4 FE (25.8%), while 20um Cu / 80um Au shows only 2% — consistent with Cu domain size controlling CO utilization",
          "basis": "observation",
          "reference": "ISAAC records: Cu-Au CO2RR performance dataset"
        }
      ]
    },
    "mechanism": {
      "description": "Tandem catalysis: Au domains selectively produce CO from CO2, which spills over to adjacent Cu domains where elevated CO* coverage promotes C-C coupling via the OCCO* intermediate pathway to C2H4.",
      "species_involved": ["CO2", "CO*", "OCCO*", "C2H4", "H*", "OH*"],
      "elementary_steps": [
        {
          "reaction": "CO2 + H2O + 2e- → CO + 2OH- (on Au)",
          "role": "equilibrated"
        },
        {
          "reaction": "CO(Au) → CO(Cu) (spillover/diffusion)",
          "role": "unknown"
        },
        {
          "reaction": "CO* + CO* → OCCO* (on Cu)",
          "role": "rate_limiting"
        },
        {
          "reaction": "OCCO* + 4H+ + 4e- → C2H4 + 2H2O",
          "role": "equilibrated"
        }
      ],
      "rate_limiting_step": "CO* + CO* → OCCO* (C-C coupling on Cu)",
      "length_scale": {
        "value_m": 80e-6,
        "description": "CO diffusion distance from Au to Cu domains under reaction conditions",
        "determined_by": "diffusion"
      }
    },
    "predictions": [
      {
        "prediction_id": "P-001",
        "descriptor_name": "faradaic_efficiency.C2H4",
        "direction": "increase",
        "reference_condition": "pure Cu electrode (no Au)",
        "magnitude": ">10x increase in FE(C2H4) at optimal geometry",
        "conditions": {
          "potential_range_V_RHE": "-0.8 to -1.2",
          "geometry": "Cu stripe width 60-100 um, Au stripe width 15-25 um"
        },
        "falsification_criterion": "If Cu-Au patterned electrodes show no C2H4 enhancement over pure Cu at any geometry, the spillover mechanism is falsified"
      },
      {
        "prediction_id": "P-002",
        "descriptor_name": "faradaic_efficiency.C2H4",
        "direction": "non_monotonic",
        "reference_condition": "varying Cu-to-Au stripe ratio",
        "magnitude": "Maximum FE(C2H4) at Cu stripe width ~ CO diffusion length",
        "conditions": {
          "potential_V_RHE": -1.0,
          "Au_stripe_width_um": 20
        },
        "falsification_criterion": "If FE(C2H4) increases monotonically with Cu fraction (no optimum), the diffusion-length argument is wrong"
      },
      {
        "prediction_id": "P-003",
        "descriptor_name": "faradaic_efficiency.CO",
        "direction": "decrease",
        "reference_condition": "pure Au electrode",
        "magnitude": "CO FE should decrease as Cu-to-Au spacing decreases (more CO consumed by Cu)",
        "conditions": {
          "potential_V_RHE": -1.0
        },
        "falsification_criterion": "If FE(CO) remains unchanged in Cu-Au vs pure Au, CO is not transferring to Cu"
      },
      {
        "prediction_id": "P-004",
        "descriptor_name": "adsorption_energy.CO",
        "direction": "increase",
        "reference_condition": "Cu(111) far from Au",
        "magnitude": "CO binding on Cu sites near Au should differ by <0.1 eV (electronic effect is secondary to transport)",
        "conditions": {
          "surface": "Cu3Au(111) alloy vs pure Cu(111)"
        },
        "falsification_criterion": "If E_ads(CO) on Cu near Au differs by >0.3 eV, electronic modification (not spillover) is the dominant effect"
      }
    ],
    "confidence": {
      "prior": 0.65,
      "current": 0.65,
      "basis": "Strong geometry-dependent experimental trend consistent with diffusion-limited spillover. UMA data shows expected binding energy trends. But no direct CO transport measurement yet."
    }
  },
  "descriptors": {
    "outputs": [
      {
        "label": "initial_evaluation",
        "generated_utc": "2026-04-07T14:00:00Z",
        "generated_by": {
          "agent": "hypothesis_generator",
          "version": "1.0"
        },
        "descriptors": [
          {
            "name": "hypothesis_status",
            "kind": "categorical",
            "source": "auto",
            "value": "proposed",
            "unit": "dimensionless",
            "definition": "Current hypothesis status after evidence evaluation. Vocabulary: proposed, supported, contradicted, eliminated, needs_more_data, superseded.",
            "uncertainty": {
              "confidence": 0.65
            }
          },
          {
            "name": "hypothesis_score",
            "kind": "absolute",
            "source": "auto",
            "value": 3,
            "unit": "dimensionless",
            "definition": "Net evidence score: +1 per supporting observation, -1 per contradicting observation",
            "uncertainty": {
              "sigma": 1,
              "unit": "dimensionless"
            }
          }
        ]
      }
    ]
  },
  "assets": [
    {
      "asset_id": "tandem_catalysis_ref",
      "content_role": "auxiliary_reference",
      "uri": "https://doi.org/10.1021/jacs.7b10410",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "media_type": "text/html"
    },
    {
      "asset_id": "uma_benchmark_data",
      "content_role": "documentation",
      "uri": "repo://hackathon_april2026/results/uma_benchmark/",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    }
  ],
  "links": [
    {
      "rel": "derived_from",
      "target": "01JFH5Z0A3S9H2ZI5X9P6M4O0E",
      "basis": "shared_material_batch",
      "notes": "Hypothesis motivated by geometry-dependent C2H4 selectivity in Cu-Au CO2RR performance data"
    }
  ]
}
```

### 8.2 Example: Competing Hypothesis — Electronic Modification

```json
{
  "isaac_record_version": "1.05",
  "record_id": "01JSHYP00002CO2RRELECTRONIC",
  "record_type": "hypothesis",
  "record_domain": "hypothesis",
  "source_type": "computation",
  "timestamps": {
    "created_utc": "2026-04-07T15:00:00Z"
  },
  "sample": {
    "material": {
      "name": "Cu-Au alloy/interface for CO2RR",
      "formula": "CuAu",
      "provenance": "theoretical"
    },
    "sample_form": "slab_model"
  },
  "system": {
    "domain": "analytical",
    "technique": "hypothesis_generation",
    "instrument": {
      "instrument_type": "reasoning_engine",
      "instrument_name": "claude_hypothesis_agent",
      "vendor_or_project": "ISAAC"
    }
  },
  "context": {
    "environment": "in_situ",
    "temperature_K": 298.15,
    "electrochemistry": {
      "reaction": "CO2RR",
      "cell_type": "flow_cell",
      "control_mode": "potentiostatic",
      "potential_setpoint_V": -1.0,
      "potential_scale": "RHE",
      "electrolyte": {
        "name": "KHCO3",
        "concentration_M": 1.0
      }
    }
  },
  "hypothesis": {
    "statement": "Electronic modification of Cu surface states by neighboring Au atoms is the primary driver of C2H4 selectivity in Cu-Au electrodes, not CO spillover. The Au d-band interaction shifts the Cu d-band center, weakening H* binding and suppressing HER while maintaining CO* binding for C-C coupling.",
    "hypothesis_type": "mechanistic",
    "scope": {
      "material_system": "Cu-Au",
      "reaction": "CO2RR",
      "conditions_summary": "Any Cu-Au configuration including alloys, interfaces, and patterned electrodes"
    },
    "origin": {
      "source_type": "computational_screening",
      "source_details": {
        "tool": "UMA",
        "query": "Compare adsorption energies on Cu(111), Au(111), Cu3Au(111)"
      },
      "reasoning_chain": [
        {
          "step": 1,
          "statement": "UMA shows Cu3Au(111) has dramatically different H* binding (E_ads = +0.16 eV) compared to Cu(111) (E_ads = -0.07 eV), indicating Au strongly modifies Cu electronic structure",
          "basis": "computation",
          "reference": "UMA benchmark: Cu3Au(111) vs Cu(111)"
        },
        {
          "step": 2,
          "statement": "Weaker H* binding on Cu3Au suppresses HER, redirecting selectivity toward CO2RR products",
          "basis": "mechanism_analysis"
        },
        {
          "step": 3,
          "statement": "CO binding on Cu3Au(111) is +0.04 eV (vs -0.42 eV on Cu(111)), suggesting the electronic effect may be too strong — intermediate compositions may be optimal",
          "basis": "computation",
          "reference": "UMA benchmark: E_ads(CO/Cu3Au111) = +0.04 eV"
        },
        {
          "step": 4,
          "statement": "If electronic modification dominates, C2H4 selectivity should correlate with Au content in the surface layer, not with geometric patterning",
          "basis": "inference"
        }
      ]
    },
    "mechanism": {
      "description": "Au atoms in or near the Cu surface modify the Cu d-band center via ligand and strain effects, weakening H* binding (suppressing HER) while shifting CO* binding to an intermediate strength favorable for C-C coupling.",
      "species_involved": ["CO*", "H*", "OCCO*", "C2H4"],
      "rate_limiting_step": "C-C coupling (CO* + CO* → OCCO*) on electronically modified Cu sites"
    },
    "predictions": [
      {
        "prediction_id": "P-001",
        "descriptor_name": "faradaic_efficiency.H2",
        "direction": "decrease",
        "reference_condition": "pure Cu electrode",
        "magnitude": "HER suppressed by >50% on Cu-Au vs pure Cu",
        "falsification_criterion": "If HER is unchanged on Cu-Au alloy surfaces vs pure Cu, electronic modification of H* binding is not significant"
      },
      {
        "prediction_id": "P-002",
        "descriptor_name": "faradaic_efficiency.C2H4",
        "direction": "correlation",
        "reference_condition": "varying Au surface fraction",
        "magnitude": "C2H4 FE should correlate with surface Au fraction, not domain spacing",
        "falsification_criterion": "If two electrodes with the same Au surface fraction but different domain spacings show different C2H4 FE, geometry (not electronics) matters"
      },
      {
        "prediction_id": "P-003",
        "descriptor_name": "d_band_center.Cu_surface",
        "direction": "decrease",
        "reference_condition": "pure Cu(111)",
        "magnitude": "d-band center shift of 0.2-0.5 eV for Cu sites adjacent to Au",
        "falsification_criterion": "If DFT shows <0.1 eV d-band shift, electronic modification is negligible"
      }
    ],
    "confidence": {
      "prior": 0.35,
      "current": 0.35,
      "basis": "UMA shows large binding energy changes on Cu3Au, but the geometry-dependent experimental data (80um vs 160um stripe width matters) is hard to explain by pure electronic effects since both geometries have the same Au surface fraction."
    }
  },
  "descriptors": {
    "outputs": [
      {
        "label": "initial_evaluation",
        "generated_utc": "2026-04-07T15:00:00Z",
        "generated_by": {
          "agent": "hypothesis_generator",
          "version": "1.0"
        },
        "descriptors": [
          {
            "name": "hypothesis_status",
            "kind": "categorical",
            "source": "auto",
            "value": "proposed",
            "unit": "dimensionless",
            "definition": "Current hypothesis status after evidence evaluation.",
            "uncertainty": {
              "confidence": 0.35
            }
          },
          {
            "name": "hypothesis_score",
            "kind": "absolute",
            "source": "auto",
            "value": 0,
            "unit": "dimensionless",
            "definition": "Net evidence score",
            "uncertainty": { "sigma": 1, "unit": "dimensionless" }
          }
        ]
      }
    ]
  },
  "assets": [],
  "links": [
    {
      "rel": "competes_with",
      "target": "01JSHYP00001CO2RRSPILLOVER",
      "basis": "shared_prediction_target",
      "notes": "Alternative mechanism to CO spillover hypothesis H-001. Both explain C2H4 enhancement but make different predictions about geometry dependence."
    }
  ]
}
```

### 8.3 Example: Hypothesis After Evidence Update (Status Change)

This shows how the **same hypothesis record** from 8.1 would look after UMA screening evidence arrives. The `descriptors.outputs` array gains a new entry:

```json
"descriptors": {
  "outputs": [
    {
      "label": "initial_evaluation",
      "generated_utc": "2026-04-07T14:00:00Z",
      "generated_by": { "agent": "hypothesis_generator", "version": "1.0" },
      "descriptors": [
        {
          "name": "hypothesis_status",
          "kind": "categorical",
          "source": "auto",
          "value": "proposed",
          "unit": "dimensionless",
          "definition": "Current hypothesis status after evidence evaluation.",
          "uncertainty": { "confidence": 0.65 }
        },
        {
          "name": "hypothesis_score",
          "kind": "absolute",
          "source": "auto",
          "value": 3,
          "unit": "dimensionless",
          "definition": "Net evidence score",
          "uncertainty": { "sigma": 1, "unit": "dimensionless" }
        }
      ]
    },
    {
      "label": "post_uma_screening",
      "generated_utc": "2026-04-08T10:30:00Z",
      "generated_by": { "agent": "ranking_engine", "version": "1.0" },
      "descriptors": [
        {
          "name": "hypothesis_status",
          "kind": "categorical",
          "source": "auto",
          "value": "supported",
          "unit": "dimensionless",
          "definition": "Current hypothesis status after evidence evaluation.",
          "uncertainty": { "confidence": 0.78 }
        },
        {
          "name": "hypothesis_score",
          "kind": "absolute",
          "source": "auto",
          "value": 5,
          "unit": "dimensionless",
          "definition": "Net evidence score: +2 from UMA E_ads trends confirming P-004, +5 total",
          "uncertainty": { "sigma": 1, "unit": "dimensionless" }
        },
        {
          "name": "observation_score.OBS_EADS_TREND",
          "kind": "categorical",
          "source": "auto",
          "value": "supports",
          "unit": "dimensionless",
          "definition": "UMA shows E_ads(CO) on Cu3Au(111) = +0.04 eV vs Cu(111) = -0.42 eV. Small shift consistent with spillover being dominant over electronic modification.",
          "uncertainty": { "confidence": 0.80 }
        }
      ]
    }
  ]
}
```

---

## 9. Design Decisions and Rationale

### Q: Why a new `record_type` instead of `synthesis`?

`synthesis` in ISAAC refers to sample preparation instructions. Hypothesis records have fundamentally different semantics — they are falsifiable claims, not synthesis protocols. Overloading `synthesis` would confuse both humans and agents.

### Q: Why not put hypothesis content in `descriptors` alone?

Descriptors are for **results** — numerical claims with uncertainty. Hypotheses have structured, non-numerical content (statements, reasoning chains, mechanisms, predictions) that doesn't fit the descriptor pattern. The `hypothesis` block handles structured content; `descriptors` handles the quantitative predictions and status tracking.

### Q: Why track status in `descriptors` instead of updating `hypothesis.status`?

ISAAC records are **immutable**. The `descriptors.outputs` array is the ISAAC-native mechanism for adding information to a record over time (each output has its own `generated_utc` and `generated_by`). This gives full provenance of how the hypothesis status evolved.

### Q: Why is `hypothesis.confidence` separate from the descriptor confidence?

`hypothesis.confidence` is a convenience snapshot. The descriptor history provides the full audit trail. This parallels how `context.potential_setpoint_V` is a convenience field while the measurement series contains the actual time-resolved data.

### Q: Why a new `record_domain: "hypothesis"` instead of reusing `theory` or `derived`?

`theory` means "theoretical predictions without explicit simulation" — close but not quite. `derived` means "aggregation of multiple source records" — also close. A hypothesis is a claim that can span experimental and computational domains. A dedicated domain value makes filtering cleaner and semantics more precise.

### Q: How does this relate to the autoCatalysisAgent hypothesis schema?

The autoCatalysisAgent schema was the proof-of-concept. This proposal maps its concepts into the ISAAC framework:

| autoCatalysisAgent | ISAAC hypothesis record |
|-------------------|------------------------|
| `id` | `record_id` (ULID format) |
| `statement` | `hypothesis.statement` |
| `origin` | `hypothesis.origin` |
| `mechanism` | `hypothesis.mechanism` |
| `predictions` | `hypothesis.predictions` + predicted values in `descriptors` |
| `evidence.supporting/contradicting` | `links` (validates/invalidates) + `observation_score.*` descriptors |
| `status` | `hypothesis_status` descriptor |
| `connections` | `links` (competes_with, supersedes, follows) |

---

## 10. Open Questions for Review

1. **Should `record_domain: "hypothesis"` be a new value, or should we reuse `"theory"` or `"derived"`?**

2. **Should the `computation` block be allowed on hypothesis records?** Currently excluded, but a hypothesis about DFT barriers might want to specify the computational setup it applies to.

3. **Immutability model**: ISAAC records are immutable. Should hypothesis status updates be:
   - (a) New descriptor outputs on the same record (proposed above)
   - (b) New hypothesis records linked via `supersedes`
   - (c) Both options available, with guidance on when to use each

4. **Should `hypothesis.predictions[].conditions` be a free-form object, or should it reuse the `context` block schema?** Free-form is more flexible; structured context is more machine-readable.

5. **Should we add `computation.output_quantity` to predictions?** This would enforce that each quantitative prediction specifies exactly what thermodynamic quantity it predicts (delta_E vs delta_G, etc.) — preventing the comparison errors we've learned from the hard way.

6. **Vocabulary governance**: Should the new vocabulary terms go through the formal proposal workflow, or be added directly as part of the v1.06 schema release?

---

## 11. Wiki Page Outline

If this proposal is accepted, the following wiki pages should be created:

1. **Record Type: Hypothesis** — Purpose, lifecycle, validation rules, agent reasoning contract, examples
2. **Hypothesis Block** — Field-by-field documentation with examples
3. **Hypothesis Vocabulary** — All new controlled vocabulary terms with definitions
4. **Ecosystem update** — Add hypothesis records to the knowledge graph diagrams

---

*This proposal is a working draft. Do not merge into the schema or submit to the ISAAC API until all open questions are resolved and at least two team members have reviewed the example records.*
