# Record Type: Hypothesis

**Schema version**: 1.06 (proposed)
**Status**: Draft — pending review

---

## 1. Purpose

A **hypothesis record** declares a falsifiable scientific claim about a material system. It captures the claim, its provenance (origin and reasoning chain), proposed mechanism, testable predictions with falsification criteria, and evolving evidence assessment.

Unlike evidence records (which assert measured or computed facts) and intent records (which specify planned work), a hypothesis record asserts a **claim to be tested**. The claim may be supported, contradicted, or refined as evidence accumulates, but the hypothesis record itself is immutable once created.

Hypothesis records enable:

1. **Pre-registration of scientific claims before testing.** The hypothesis is recorded with full provenance before any test is executed, preventing post-hoc rationalization.
2. **Structured provenance.** Every hypothesis has an explicit reasoning chain — a step-by-step derivation with references, making it possible for agents and humans to audit why a claim was proposed.
3. **Machine-readable predictions that bridge to evidence via shared descriptor vocabulary.** Each prediction references an ISAAC descriptor name (e.g., `faradaic_efficiency.C2H4`, `adsorption_energy.CO`), enabling programmatic comparison when evidence arrives.
4. **Knowledge transfer.** Hypotheses can be marked as transferable to other material systems via `scope.transferability`, enabling cross-system reasoning.
5. **Comparative evaluation.** Competing hypotheses are grouped via `group.group_id` and ranked through separate derived evidence records.

---

## 2. Validation Rules

### 2.1 Block Requirements by Record Type

The hypothesis record type shares the top-level block structure with evidence and intent but uses them differently.

| Block | Evidence | Intent | Hypothesis |
|-------|----------|--------|------------|
| `sample` | required | required | required |
| `system` | required | required | required |
| `context` | optional | optional | optional (recommended) |
| `descriptors` | required (>=1 non-null value) | optional (target values) | optional (status tracking) |
| `hypothesis` | not used | not used | **required** |
| `measurement` | conditional | optional | **not used** |
| `computation` | conditional | optional | optional (specifies what computational conditions the predictions apply to) |
| `links` | optional | optional | optional (recommended: `derived_from` evidence that motivated the hypothesis) |
| `assets` | optional | optional | optional |
| `timestamps.created_utc` | required | required | required |
| `timestamps.acquired_start` | required | optional | **not used** |
| `timestamps.acquired_end` | required | optional | **not used** |

**Key differences from evidence:**

- The `hypothesis` block is required and replaces `measurement` as the primary content block.
- `descriptors` are optional at creation. When present, they track hypothesis status (`hypothesis_status`, `hypothesis_score`) and optionally predicted values (`theoretical_metric` kind). They are **not** measured facts.
- No `acquired_start` / `acquired_end` timestamps. A hypothesis is authored, not acquired.
- `computation` is optional. When present, it specifies what computational method the predictions assume (e.g., PBE+D3 DFT), not a computation that was performed.

### 2.2 Conditional Schema Validation

The JSON Schema enforces the `hypothesis` block requirement via `allOf`:

```json
"allOf": [{
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
}]
```

### 2.3 Semantic Integrity Rules

1. **Prediction descriptor alignment.** Every `hypothesis.predictions[].descriptor_name` should correspond to a known ISAAC descriptor name from the controlled vocabulary. Unknown names trigger a warning (not error) to allow novel descriptors.
2. **Reasoning chain completeness.** `hypothesis.origin.reasoning_chain` must contain at least one step. Steps must be numbered sequentially from 1 with `depends_on` referencing only prior step numbers.
3. **Falsification criterion required.** Every prediction must have a non-empty `falsification_criterion`.
4. **No measurement block.** Hypothesis records should not contain a `measurement` block (warning, not error).
5. **Link relation constraints:**
   - `motivates` can only appear on hypothesis records (source) pointing to intent records (target).
   - `supersedes` can only link records of the same `record_type`.
   - `competes_with` can only link hypothesis records to hypothesis records.

---

## 3. Lifecycle

### 3.1 Full Lifecycle

```
Evidence / Literature Records
(observations that motivate the hypothesis)
         |
         |  derived_from
         v
+--------------------+
| HYPOTHESIS RECORD  |   <--- Immutable once created
| - statement        |
| - reasoning chain  |
| - predictions      |
+--------------------+
         |
         |  motivates
         v
+--------------------+
| INTENT RECORD      |   <--- Planned test of the hypothesis
| - computation spec |
| - target values    |
+--------------------+
         |
         |  derived_from (intent -> evidence)
         v
+--------------------+
| EVIDENCE RECORD    |   <--- Test result
| - descriptors      |
| - measured values  |
+--------------------+
         |
         |  validates / invalidates
         v
+--------------------+
| HYPOTHESIS RECORD  |   <--- Same record; new descriptor output appended
| descriptors.outputs|
|   [0]: proposed    |
|   [1]: supported   |   <--- New entry with updated status
+--------------------+
```

### 3.2 Key Lifecycle Rules

1. **Hypothesis records are immutable once created.** Like all ISAAC records, the document is never modified in place.

2. **Status changes are tracked as new descriptor outputs.** The `descriptors.outputs` array grows over time. Each new entry has its own `generated_utc` and `generated_by`, providing a full audit trail of how the hypothesis status evolved.

3. **Statement revision requires a new record.** If the hypothesis statement, mechanism, or predictions need to change, create a **new** hypothesis record and link it to the original via `links.rel = "supersedes"`. The original record remains intact.

4. **Competing hypotheses are grouped.** Multiple hypotheses that offer alternative explanations for the same phenomenon share a `hypothesis.group.group_id`. Ranking is performed in separate derived evidence records, not within the hypothesis records themselves.

5. **Ranking is external.** A ranking evaluation record (`record_type: "evidence"`, `record_domain: "derived"`) provides comparative assessment across a hypothesis group. This separation ensures that the hypothesis record remains a clean assertion and the evaluation remains an independent judgment.

---

## 4. Hypothesis Block Structure

The `hypothesis` block is a top-level block, parallel to `computation` and `measurement`. It contains all hypothesis-specific content.

```
hypothesis
+-- statement              (string, REQUIRED)
+-- hypothesis_type        (enum, REQUIRED)
+-- scope                  (object, REQUIRED)
|   +-- material_system        (string, REQUIRED)
|   +-- reaction               (enum, optional)
|   +-- conditions_summary     (string, optional)
|   +-- transferability        (object, optional)
|       +-- generalizable_to       (array of {material_system, basis, confidence})
|       +-- mechanism_class        (string)
|       +-- generality_level       (enum)
+-- origin                 (object, REQUIRED)
|   +-- source_type            (enum, REQUIRED)
|   +-- source_details         (object, optional)
|   |   +-- tool                   (string)
|   |   +-- query                  (string)
|   |   +-- output_ref             (string)
|   +-- reasoning_chain        (array, REQUIRED, minItems: 1)
|       +-- [] { step, statement, basis, reference, depends_on }
+-- mechanism              (object, optional, recommended for mechanistic hypotheses)
|   +-- description            (string, REQUIRED)
|   +-- species_involved       (array[string], REQUIRED)
|   +-- elementary_steps       (array, optional)
|   |   +-- [] { reaction, role, reference_record_id }
|   +-- rate_limiting_step     (string, optional)
|   +-- length_scale           (object, optional)
|       +-- value_m                (number, REQUIRED)
|       +-- description            (string, REQUIRED)
|       +-- determined_by          (enum, REQUIRED)
+-- predictions            (array, REQUIRED, minItems: 1)
|   +-- [] {
|       prediction_id              (string, REQUIRED)
|       descriptor_name            (string, REQUIRED)
|       direction                  (enum, REQUIRED)
|       reference_condition        (string, optional)
|       reference_record_id        (ULID, optional)
|       magnitude                  (string, optional)
|       magnitude_range            ({min, max, unit}, optional)
|       conditions                 (object, optional)
|       test_domain                (enum, optional)
|       computation_context        (object, optional)
|       |   +-- output_quantity        (enum, REQUIRED)
|       |   +-- corrections_applied    (object, optional)
|       |   +-- method_family          (string, optional)
|       |   +-- functional_name        (string, optional)
|       falsification_criterion    (string, REQUIRED)
|       falsification_quantitative (object, optional)
|           +-- descriptor_name        (string, REQUIRED)
|           +-- operator               (enum, REQUIRED)
|           +-- threshold              (number, conditional)
|           +-- range_min              (number, conditional)
|           +-- range_max              (number, conditional)
|           +-- unit                   (string, REQUIRED)
|   }
+-- group                  (object, optional)
|   +-- group_id               (string, REQUIRED)
|   +-- group_label            (string, optional)
|   +-- role_in_group          (enum, REQUIRED)
+-- confidence             (object, optional)
    +-- prior                  (number [0,1], REQUIRED)
    +-- basis                  (string, REQUIRED)
```

### 4.1 `statement` (string, required)

A single-sentence falsifiable claim. It must be possible to imagine evidence that would disprove it.

**Good**: "CO spillover from Au domains to Cu domains is the primary mechanism driving C2H4 selectivity enhancement in Cu-Au patterned electrodes, with selectivity scaling inversely with Au-to-Cu domain spacing at spacings below the CO diffusion length (~80 um)."

**Bad**: "Cu-Au is a good catalyst for CO2 reduction." (Not falsifiable -- no specific prediction.)

### 4.2 `hypothesis_type` (enum, required)

| Value | Description |
|-------|-------------|
| `mechanistic` | Proposes a specific reaction mechanism or pathway |
| `selectivity` | Claims about product selectivity dependence on a variable |
| `activity` | Claims about catalytic activity (rate, overpotential) |
| `stability` | Claims about catalyst stability or degradation mechanism |
| `scaling` | Claims about scaling relations between descriptors |
| `structural` | Claims about structure-property relationships |
| `transport` | Claims about mass transport or diffusion effects |

### 4.3 `scope` (object, required)

Defines the domain of applicability for the hypothesis.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `material_system` | string | Yes | Short label: `"Cu-Au"`, `"Cu-Ag"`, `"Pt-Ni"` |
| `reaction` | enum | No | Reuses `context.electrochemistry.reaction` vocabulary |
| `conditions_summary` | string | No | Free-text summary of applicable conditions |
| `transferability` | object | No | Cross-system applicability (see Section 7) |

### 4.4 `origin` (object, required)

Full provenance -- how the hypothesis was generated.

#### `origin.source_type` (enum, required)

| Value | Description |
|-------|-------------|
| `literature_synthesis` | Synthesized from multiple literature sources |
| `data_pattern` | Inferred from patterns in experimental or computed data |
| `computational_screening` | Generated from computational screening (UMA, DFT, ML) |
| `expert_reasoning` | Domain expert knowledge and intuition |
| `analogy` | Transferred from a related material system |
| `mechanistic_analysis` | Derived from reaction mechanism analysis (microkinetic, DFT pathways) |

#### `origin.source_details` (object, optional)

| Property | Type | Description |
|----------|------|-------------|
| `tool` | string | Tool used: `"Edison"`, `"CatMAP"`, `"UMA"`, `"VASP"`, `"Claude"` |
| `query` | string | Query or input that produced this hypothesis |
| `output_ref` | string | File path or URI to the analysis output |

#### `origin.reasoning_chain` (array, required, minItems: 1)

Step-by-step reasoning that led to this hypothesis. Each step is:

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `step` | integer | Yes | Step number (1-indexed, sequential) |
| `statement` | string | Yes | What was concluded in this step |
| `basis` | enum | Yes | Epistemic basis (see table below) |
| `reference` | string | No | Record ID, DOI, or description supporting this step |
| `depends_on` | array[integer] | No | Step numbers of prior steps this inference builds on |

**`reasoning_chain[].basis` vocabulary:**

| Value | Description |
|-------|-------------|
| `observation` | Based on experimental observation (references evidence record) |
| `computation` | Based on DFT/simulation result (references evidence record) |
| `literature` | Based on published finding (references DOI or literature record) |
| `inference` | Logical deduction from prior steps |
| `analogy` | Transferred from analogous system |
| `mechanism_analysis` | Based on reaction pathway analysis |

The `depends_on` field creates a directed acyclic graph within the reasoning chain. An agent can trace any conclusion back to its foundational observations.

### 4.5 `mechanism` (object, optional)

The proposed physical or chemical mechanism. Recommended when `hypothesis_type` is `mechanistic`.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `description` | string | Yes | Prose description of the mechanism |
| `species_involved` | array[string] | Yes | Chemical species: `["CO*", "OCCO*", "H*"]` |
| `elementary_steps` | array[object] | No | Ordered list of elementary reaction steps |
| `rate_limiting_step` | string | No | Which elementary step is rate-limiting |
| `length_scale` | object | No | Characteristic length scale for the mechanism |

#### `mechanism.elementary_steps[]`

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `reaction` | string | Yes | Reaction equation, e.g., `"CO* + CO* -> OCCO*"` |
| `role` | enum | Yes | `rate_limiting`, `equilibrated`, `irreversible`, `unknown` |
| `reference_record_id` | ULID | No | ISAAC evidence/intent record with data for this step |

#### `mechanism.length_scale`

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `value_m` | number | Yes | In meters (e.g., `80e-6` for 80 um) |
| `description` | string | Yes | What this length scale represents |
| `determined_by` | enum | Yes | `diffusion`, `electronic`, `grain_size`, `patterning`, `strain_field`, `nanostructure`, `film_thickness` |

### 4.6 `predictions` (array, required, minItems: 1)

Each prediction is a specific, testable claim that maps to an ISAAC descriptor. See Section 5 for how predictions bridge to evidence.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `prediction_id` | string | Yes | Short identifier: `"P-001"`, `"P-002"` |
| `descriptor_name` | string | Yes | Must match ISAAC descriptor vocabulary |
| `direction` | enum | Yes | Predicted direction of change (see table) |
| `reference_condition` | string | No | What the direction is relative to (e.g., `"pure Cu(111)"`) |
| `reference_record_id` | ULID | No | Baseline ISAAC record for comparison |
| `magnitude` | string | No | Human-readable magnitude: `">0.2 eV difference"` |
| `magnitude_range` | object | No | Machine-readable magnitude: `{min, max, unit}` |
| `conditions` | object | No | Conditions under which prediction holds (free-form) |
| `test_domain` | enum | No | What kind of evidence tests this prediction |
| `computation_context` | object | No | Context for computational predictions (see Section 5) |
| `falsification_criterion` | string | Yes | What observation would disprove this prediction |
| `falsification_quantitative` | object | No | Machine-readable falsification criterion |

**`predictions[].direction` vocabulary:**

| Value | Description |
|-------|-------------|
| `increase` | Predicted to increase relative to reference condition |
| `decrease` | Predicted to decrease relative to reference condition |
| `no_change` | Predicted to remain unchanged (null hypothesis) |
| `non_monotonic` | Predicted to show a maximum or minimum |
| `threshold` | Predicted to change above/below a critical value |
| `correlation` | Predicted to correlate with another variable |

**`predictions[].test_domain` vocabulary:**

| Value | Description |
|-------|-------------|
| `characterization` | Tested by structural or spectroscopic characterization |
| `performance` | Tested by electrochemical or catalytic performance measurement |
| `simulation` | Tested by DFT, ML, or other computational simulation |

**`predictions[].falsification_quantitative`:**

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `descriptor_name` | string | Yes | Descriptor to evaluate against |
| `operator` | enum | Yes | `less_than`, `greater_than`, `equals`, `not_equals`, `within_range`, `outside_range` |
| `threshold` | number | Conditional | Threshold for single-bound operators |
| `range_min` | number | Conditional | Lower bound for range operators |
| `range_max` | number | Conditional | Upper bound for range operators |
| `unit` | string | Yes | Unit of the threshold or range values |

### 4.7 `group` (object, optional)

Groups competing hypotheses that offer alternative explanations for the same phenomenon.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `group_id` | string | Yes | Identifier for the competing hypothesis set |
| `group_label` | string | No | Human-readable label for the group |
| `role_in_group` | enum | Yes | `primary`, `alternative`, `null_hypothesis`, `refinement` |

All hypothesis records sharing the same `group_id` are considered competing explanations. Ranking across the group is performed in a separate derived evidence record.

### 4.8 `confidence` (object, optional)

The author's subjective assessment of hypothesis plausibility at the time of creation.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `prior` | number [0, 1] | Yes | Initial confidence before testing |
| `basis` | string | Yes | Explanation of the confidence assessment |

**Note**: There is no `current` field in the `confidence` object. The current confidence is tracked in `descriptors.outputs` as the hypothesis is evaluated over time. This ensures immutability of the hypothesis block and provides a full audit trail of confidence evolution.

---

## 5. Predictions and the Descriptor Bridge

The prediction system is the core mechanism by which hypothesis records connect to evidence records. Each prediction references an ISAAC descriptor name, creating a machine-readable bridge between claims and observations.

### 5.1 How the Bridge Works

```
HYPOTHESIS RECORD                         EVIDENCE RECORD
hypothesis.predictions[0]                 descriptors.outputs[0].descriptors[0]
  descriptor_name: "adsorption_energy.CO"   name: "adsorption_energy.CO"
  direction: "decrease"                     kind: "theoretical_metric"
  magnitude: ">0.2 eV difference"          value: -0.42
  reference_condition: "pure Cu(111)"       unit: "eV"
                                            ...
```

When an evidence record arrives with a descriptor whose `name` matches a prediction's `descriptor_name`, an agent can programmatically:

1. Look up the prediction's `direction` and `magnitude_range`.
2. Compare against the evidence descriptor's `value`.
3. Evaluate the `falsification_quantitative` criterion if present.
4. Append a new descriptor output to the hypothesis record with an `observation_score.{prediction_id}` descriptor.

### 5.2 Computation Context for DFT Predictions

For predictions that depend on computational method, the `computation_context` sub-object prevents comparison errors between incompatible quantities.

```json
{
  "prediction_id": "P-004",
  "descriptor_name": "adsorption_energy.CO",
  "direction": "increase",
  "computation_context": {
    "output_quantity": "delta_E",
    "corrections_applied": {
      "zero_point_energy": false,
      "solvation": false
    },
    "method_family": "DFT",
    "functional_name": "PBE"
  },
  "falsification_criterion": "..."
}
```

**`computation_context.output_quantity` vocabulary:**

| Value | Description |
|-------|-------------|
| `E_DFT` | Raw DFT total energy |
| `E_DFT_plus_ZPE` | DFT energy with zero-point energy correction |
| `delta_E` | Reaction energy (no thermal corrections) |
| `delta_G_CHE` | Free energy under computational hydrogen electrode |
| `delta_G_grand_canonical` | Free energy under grand canonical conditions |
| `activation_energy_raw` | Raw activation barrier from NEB or TS search |
| `activation_energy_ZPE` | Activation barrier with ZPE correction |
| `activation_free_energy` | Activation free energy with full thermal corrections |

**Critical rule**: When comparing a prediction to evidence, the agent must verify that `computation_context.output_quantity` on the prediction matches `computation.output_quantity.quantity` on the evidence record. A `delta_E` prediction cannot be compared against a `delta_G_CHE` evidence value -- the difference can be 0.3-0.7 eV even on identical slabs.

### 5.3 Test Domain

The `test_domain` field tells agents what kind of evidence record to look for:

- `simulation` -- look for evidence records with `record_domain: "simulation"` or `record_domain: "theory"`
- `performance` -- look for evidence records with `record_domain: "performance"`
- `characterization` -- look for evidence records with `record_domain: "characterization"`

This prevents agents from trying to validate a DFT prediction with an electrochemical measurement (or vice versa) without explicit methodological reasoning.

---

## 6. Agent Reasoning Contract

These rules are mandatory for any AI agent that reads or writes hypothesis records.

### 6.1 Hypothesis Predictions Are Not Facts

**Never treat hypothesis predictions as established facts.** When aggregating descriptor values for quantitative analysis (e.g., "what is the average adsorption energy of CO on Cu?"), filter by `record_type != "hypothesis"`. Hypothesis descriptor values are claims, not observations.

### 6.2 Descriptor Matching

When comparing a prediction to evidence:

1. Verify `descriptor_name` matches exactly.
2. Verify `computation_context.output_quantity` is compatible (if present).
3. Verify units are consistent.
4. Check `conditions` or `reference_condition` for applicability.

### 6.3 Status Resolution

The current hypothesis status is the `hypothesis_status` descriptor in the **last** (most recent `generated_utc`) entry of the `descriptors.outputs` array. Do not average or aggregate status values across outputs -- the latest output is the current state.

### 6.4 Confidence Interpretation

`hypothesis.confidence.prior` and any confidence values in descriptor outputs are **subjective assessments**, not calibrated probabilities. They inform prioritization and resource allocation, not statistical inference. Two agents may assign different confidence values to the same hypothesis given the same evidence.

### 6.5 Separation of Concerns

Different agents SHOULD evaluate evidence against hypotheses than the agent that generated the hypothesis. This prevents confirmation bias. The `generated_by` field in descriptor outputs provides an audit trail of which agent performed each evaluation.

### 6.6 Ranking Evaluation Records

A ranking evaluation record is a separate evidence record with `record_domain: "derived"` that provides comparative assessment across a hypothesis group. It links to all hypothesis records in the group via `links.rel = "derived_from"` and contains descriptors such as `hypothesis_rank` for each hypothesis in the group. Ranking logic and criteria are documented in the evaluation record's assets.

---

## 7. Transferability

Hypotheses often apply beyond the specific material system they were originally proposed for. The `scope.transferability` sub-object captures this explicitly.

### 7.1 Marking a Hypothesis as Transferable

```json
"scope": {
  "material_system": "Cu-Au",
  "reaction": "CO2RR",
  "transferability": {
    "generalizable_to": [
      {
        "material_system": "Cu-Ag",
        "basis": "Ag also reduces CO2 to CO selectively; same tandem catalysis mechanism expected",
        "confidence": "high"
      },
      {
        "material_system": "Cu-Zn",
        "basis": "Zn shows moderate CO selectivity but weaker than Au/Ag; mechanism may apply with lower enhancement",
        "confidence": "moderate"
      }
    ],
    "mechanism_class": "CO_spillover_tandem_catalysis",
    "generality_level": "class_specific"
  }
}
```

### 7.2 Fields

| Property | Type | Description |
|----------|------|-------------|
| `generalizable_to` | array | List of material systems this hypothesis may transfer to |
| `generalizable_to[].material_system` | string | Target material system label |
| `generalizable_to[].basis` | string | Reason for expecting transferability |
| `generalizable_to[].confidence` | enum | `high`, `moderate`, `low` |
| `mechanism_class` | string | Short label for the general mechanism type (e.g., `"CO_spillover_tandem_catalysis"`) |
| `generality_level` | enum | `system_specific`, `class_specific`, `universal` |

### 7.3 Creating Transferred Hypotheses

When an agent creates a new hypothesis for a target system based on a transferable hypothesis:

1. The new hypothesis record links back to the source via `links.rel = "derived_from"` with `basis: "abductive_inference"`.
2. The new hypothesis's `origin.source_type` is set to `"analogy"`.
3. The reasoning chain includes a step with `basis: "analogy"` referencing the source hypothesis record ID.
4. Predictions are adjusted for the target system (different binding energies, different expected magnitudes).

### 7.4 Cross-System Queries

The `mechanism_class` field enables agents to query across material systems:

> "Find all hypothesis records where `scope.transferability.mechanism_class` = `'CO_spillover_tandem_catalysis'`"

This returns all hypotheses -- across Cu-Au, Cu-Ag, Cu-Zn, and any other system -- that propose the same general mechanism, enabling systematic comparison and meta-analysis.

---

## 8. Examples

### 8.1 CO Spillover Hypothesis (Cu-Au CO2RR)

This example shows a complete hypothesis record proposing that CO spillover from Au domains to Cu domains drives C2H4 selectivity in patterned electrodes. The hypothesis was derived from Edison literature search and UMA benchmark calculations.

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
    "electrode_type": "patterned_film"
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
      }
    }
  },
  "hypothesis": {
    "statement": "CO spillover from Au domains to Cu domains is the primary mechanism driving C2H4 selectivity enhancement in Cu-Au patterned electrodes, with selectivity scaling inversely with Au-to-Cu domain spacing at spacings below the CO diffusion length (~80 um).",
    "hypothesis_type": "mechanistic",
    "scope": {
      "material_system": "Cu-Au",
      "reaction": "CO2RR",
      "conditions_summary": "Patterned Cu-Au electrodes in flow cell, -0.8 to -1.2V RHE, 1M KHCO3",
      "transferability": {
        "generalizable_to": [
          {
            "material_system": "Cu-Ag",
            "basis": "Ag also reduces CO2 to CO selectively; same tandem catalysis mechanism expected",
            "confidence": "high"
          }
        ],
        "mechanism_class": "CO_spillover_tandem_catalysis",
        "generality_level": "class_specific"
      }
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
          "reference": "UMA benchmark: E_ads(CO/Cu111) = -0.42 eV",
          "depends_on": [1]
        },
        {
          "step": 3,
          "statement": "In Cu-Au patterned electrodes, CO produced on Au domains can diffuse to nearby Cu domains, increasing local CO coverage",
          "basis": "literature",
          "reference": "doi:10.1021/jacs.7b10410",
          "depends_on": [1, 2]
        },
        {
          "step": 4,
          "statement": "Higher local CO coverage on Cu promotes C-C coupling (CO* + CO* -> OCCO*), which is the rate-limiting step for C2H4 formation",
          "basis": "mechanism_analysis",
          "depends_on": [3]
        },
        {
          "step": 5,
          "statement": "The 80um Cu / 20um Au geometry shows highest C2H4 FE (25.8%), while 20um Cu / 80um Au shows only 2% -- consistent with Cu domain size controlling CO utilization",
          "basis": "observation",
          "reference": "ISAAC records: Cu-Au CO2RR performance dataset",
          "depends_on": [3, 4]
        }
      ]
    },
    "mechanism": {
      "description": "Tandem catalysis: Au domains selectively produce CO from CO2, which spills over to adjacent Cu domains where elevated CO* coverage promotes C-C coupling via the OCCO* intermediate pathway to C2H4.",
      "species_involved": ["CO2", "CO*", "OCCO*", "C2H4", "H*", "OH*"],
      "elementary_steps": [
        { "reaction": "CO2 + H2O + 2e- -> CO + 2OH- (on Au)", "role": "equilibrated" },
        { "reaction": "CO(Au) -> CO(Cu) (spillover/diffusion)", "role": "unknown" },
        { "reaction": "CO* + CO* -> OCCO* (on Cu)", "role": "rate_limiting" },
        { "reaction": "OCCO* + 4H+ + 4e- -> C2H4 + 2H2O", "role": "equilibrated" }
      ],
      "rate_limiting_step": "CO* + CO* -> OCCO* (C-C coupling on Cu)",
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
        "test_domain": "performance",
        "falsification_criterion": "If Cu-Au patterned electrodes show no C2H4 enhancement over pure Cu at any geometry, the spillover mechanism is falsified"
      },
      {
        "prediction_id": "P-002",
        "descriptor_name": "faradaic_efficiency.C2H4",
        "direction": "non_monotonic",
        "reference_condition": "varying Cu-to-Au stripe ratio",
        "magnitude": "Maximum FE(C2H4) at Cu stripe width ~ CO diffusion length",
        "test_domain": "performance",
        "falsification_criterion": "If FE(C2H4) increases monotonically with Cu fraction (no optimum), the diffusion-length argument is wrong"
      },
      {
        "prediction_id": "P-003",
        "descriptor_name": "faradaic_efficiency.CO",
        "direction": "decrease",
        "reference_condition": "pure Au electrode",
        "test_domain": "performance",
        "falsification_criterion": "If FE(CO) remains unchanged in Cu-Au vs pure Au, CO is not transferring to Cu"
      },
      {
        "prediction_id": "P-004",
        "descriptor_name": "adsorption_energy.CO",
        "direction": "increase",
        "reference_condition": "Cu(111) far from Au",
        "magnitude": "CO binding on Cu sites near Au should differ by <0.1 eV",
        "test_domain": "simulation",
        "computation_context": {
          "output_quantity": "delta_E",
          "corrections_applied": {
            "zero_point_energy": false,
            "solvation": false
          },
          "method_family": "DFT",
          "functional_name": "PBE"
        },
        "falsification_criterion": "If E_ads(CO) on Cu near Au differs by >0.3 eV, electronic modification (not spillover) is the dominant effect",
        "falsification_quantitative": {
          "descriptor_name": "adsorption_energy.CO",
          "operator": "outside_range",
          "range_min": -0.52,
          "range_max": -0.32,
          "unit": "eV"
        }
      }
    ],
    "group": {
      "group_id": "CuAu_CO2RR_C2H4_mechanism",
      "group_label": "Cu-Au CO2RR C2H4 selectivity mechanism",
      "role_in_group": "primary"
    },
    "confidence": {
      "prior": 0.65,
      "basis": "Strong geometry-dependent experimental trend consistent with diffusion-limited spillover. UMA data shows expected binding energy trends. But no direct CO transport measurement yet."
    }
  },
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
            "definition": "Current hypothesis status. Vocabulary: proposed, supported, contradicted, eliminated, needs_more_data, superseded.",
            "uncertainty": { "confidence": 0.65 }
          },
          {
            "name": "hypothesis_score",
            "kind": "absolute",
            "source": "auto",
            "value": 3,
            "unit": "dimensionless",
            "definition": "Net evidence score: +1 per supporting observation, -1 per contradicting observation.",
            "uncertainty": { "sigma": 1, "unit": "dimensionless" }
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

### 8.2 Competing Hypothesis -- Electronic Modification

This hypothesis competes with the CO spillover hypothesis (8.1), proposing that electronic modification of Cu by Au is the dominant mechanism. Note the `group` block with the same `group_id` and `competes_with` link.

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
  "hypothesis": {
    "statement": "Electronic modification of Cu surface states by neighboring Au atoms is the primary driver of C2H4 selectivity in Cu-Au electrodes, not CO spillover. The Au d-band interaction shifts the Cu d-band center, weakening H* binding and suppressing HER while maintaining CO* binding for C-C coupling.",
    "hypothesis_type": "mechanistic",
    "scope": {
      "material_system": "Cu-Au",
      "reaction": "CO2RR"
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
          "basis": "mechanism_analysis",
          "depends_on": [1]
        },
        {
          "step": 3,
          "statement": "If electronic modification dominates, C2H4 selectivity should correlate with Au content in the surface layer, not with geometric patterning",
          "basis": "inference",
          "depends_on": [1, 2]
        }
      ]
    },
    "predictions": [
      {
        "prediction_id": "P-001",
        "descriptor_name": "faradaic_efficiency.H2",
        "direction": "decrease",
        "reference_condition": "pure Cu electrode",
        "magnitude": "HER suppressed by >50% on Cu-Au vs pure Cu",
        "test_domain": "performance",
        "falsification_criterion": "If HER is unchanged on Cu-Au alloy surfaces vs pure Cu, electronic modification of H* binding is not significant"
      },
      {
        "prediction_id": "P-002",
        "descriptor_name": "faradaic_efficiency.C2H4",
        "direction": "correlation",
        "reference_condition": "varying Au surface fraction",
        "magnitude": "C2H4 FE should correlate with surface Au fraction, not domain spacing",
        "test_domain": "performance",
        "falsification_criterion": "If two electrodes with the same Au surface fraction but different domain spacings show different C2H4 FE, geometry (not electronics) matters"
      }
    ],
    "group": {
      "group_id": "CuAu_CO2RR_C2H4_mechanism",
      "group_label": "Cu-Au CO2RR C2H4 selectivity mechanism",
      "role_in_group": "alternative"
    },
    "confidence": {
      "prior": 0.35,
      "basis": "UMA shows large binding energy changes on Cu3Au, but the geometry-dependent experimental data (80um vs 160um stripe width matters) is hard to explain by pure electronic effects since both geometries have the same Au surface fraction."
    }
  },
  "descriptors": {
    "outputs": [
      {
        "label": "initial_evaluation",
        "generated_utc": "2026-04-07T15:00:00Z",
        "generated_by": { "agent": "hypothesis_generator", "version": "1.0" },
        "descriptors": [
          {
            "name": "hypothesis_status",
            "kind": "categorical",
            "source": "auto",
            "value": "proposed",
            "unit": "dimensionless",
            "definition": "Current hypothesis status after evidence evaluation.",
            "uncertainty": { "confidence": 0.35 }
          }
        ]
      }
    ]
  },
  "links": [
    {
      "rel": "competes_with",
      "target": "01JSHYP00001CO2RRSPILLOVER",
      "basis": "shared_prediction_target",
      "notes": "Alternative mechanism to CO spillover hypothesis. Both explain C2H4 enhancement but make different predictions about geometry dependence."
    }
  ]
}
```

### 8.3 Hypothesis After Evidence Update (Status Change)

This shows how the descriptors block of hypothesis 8.1 evolves after UMA screening evidence arrives. The `outputs` array gains a new entry -- the hypothesis record itself is never modified; only new outputs are appended.

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
          "definition": "Net evidence score.",
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
          "definition": "Net evidence score: +2 from UMA E_ads trends confirming P-004.",
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

The current status is `"supported"` (from the second output, which has the latest `generated_utc`). The full history of status evolution is preserved.

---

## 9. New Vocabulary Terms

This section summarizes all controlled vocabulary additions required by hypothesis records. These extend the existing ISAAC vocabulary without modifying any existing values.

### 9.1 Root-Level Enums

| Field | New Value | Description |
|-------|-----------|-------------|
| `record_type` | `hypothesis` | A falsifiable scientific claim with structured provenance and predictions |
| `record_domain` | `hypothesis` | Record content is a hypothesis (distinct from theory, derived, etc.) |

### 9.2 System Block

| Field | New Value | Description |
|-------|-----------|-------------|
| `system.domain` | `analytical` | Record produced by reasoning, synthesis, or meta-analysis |
| `system.technique` | `hypothesis_generation` | Structured generation of scientific hypotheses |
| `system.technique` | `systematic_review` | Systematic analysis and synthesis of multiple source records |
| `system.instrument.instrument_type` | `reasoning_engine` | AI agent, expert panel, or analytical tool |

### 9.3 Link Relations

| `rel` Value | Direction | Description |
|-------------|-----------|-------------|
| `motivates` | hypothesis -> intent | This hypothesis motivated the creation of the target intent |
| `supersedes` | hypothesis -> hypothesis | This hypothesis replaces the target hypothesis |
| `competes_with` | hypothesis -> hypothesis | This hypothesis offers an alternative explanation |

| `basis` Value | Description |
|---------------|-------------|
| `shared_prediction_target` | Both records make predictions about the same observable |
| `hypothesis_refinement` | This record is a refined version of the target |
| `abductive_inference` | Link established through abductive reasoning (inference to best explanation) |

### 9.4 Hypothesis Evaluation Descriptors

| Descriptor Name | Kind | Unit | Description |
|----------------|------|------|-------------|
| `hypothesis_status` | categorical | dimensionless | Status enum: `proposed`, `supported`, `contradicted`, `eliminated`, `needs_more_data`, `superseded` |
| `hypothesis_score` | absolute | dimensionless | Net evidence score (sum of per-observation +1/-1 ratings) |
| `hypothesis_rank` | absolute | dimensionless | Rank within a hypothesis group (1 = best) |
| `observation_score.{ID}` | categorical | dimensionless | Per-observation rating: `supports`, `contradicts`, `neutral`, `insufficient` |

---

## 10. Reference Files

- **Schema block**: [`hypothesis_schema_block.json`](hypothesis_schema_block.json) -- Full JSON Schema for the `hypothesis` block
- **Vocabulary additions**: [`hypothesis_vocabulary_additions.json`](hypothesis_vocabulary_additions.json) -- All new controlled vocabulary terms
- **Design proposal**: [`hypothesis_record_proposal.md`](hypothesis_record_proposal.md) -- Original design document with rationale and open questions
