# Schema Patch: Adding Hypothesis Records to isaac_record_v1.json

This document shows the exact changes needed in `schema/isaac_record_v1.json` to support hypothesis records.

## Change 1: Add "hypothesis" to record_type enum

```json
// In: properties.record_type.enum
// Add "hypothesis" to the array:
"record_type": {
  "type": "string",
  "enum": [
    "evidence",
    "intent",
    "synthesis",
    "hypothesis"        // ← NEW
  ]
}
```

## Change 2: Add "hypothesis" to record_domain enum

```json
// In: properties.record_domain.enum
"record_domain": {
  "type": "string",
  "enum": [
    "characterization",
    "performance",
    "simulation",
    "theory",
    "derived",
    "hypothesis"        // ← NEW
  ]
}
```

## Change 3: Add "analytical" to system.domain enum

```json
// In: properties.system.properties.domain.enum
"domain": {
  "type": "string",
  "enum": [
    "experimental",
    "computational",
    "analytical"        // ← NEW
  ]
}
```

## Change 4: Add new technique values to system.technique enum

```json
// In: properties.system.properties.technique.enum
// Add to the end of the existing 36-value array:
"hypothesis_generation",    // ← NEW
"systematic_review"         // ← NEW
```

## Change 5: Add new link relation values

```json
// In: properties.links.items.properties.rel.enum
"rel": {
  "type": "string",
  "enum": [
    "derived_from",
    "intended_comparison_target",
    "calibration_of",
    "same_sample_as",
    "replica_of",
    "follows",
    "validates",
    "invalidates",
    "motivates",         // ← NEW
    "supersedes",        // ← NEW
    "competes_with"      // ← NEW
  ]
}
```

## Change 6: Add new link basis values

```json
// In: properties.links.items.properties.basis.enum
"basis": {
  "type": "string",
  "enum": [
    "same_absorber_edge",
    "matched_operating_conditions",
    "matched_computational_method",
    "shared_reference_state",
    "same_workflow_version",
    "identical_geometry",
    "analysis_pipeline_output",
    "replicate_preparation",
    "same_sample_id",
    "shared_analysis_method",
    "shared_material_batch",
    "unspecified",
    "shared_prediction_target",   // ← NEW
    "hypothesis_refinement",      // ← NEW
    "abductive_inference"         // ← NEW
  ]
}
```

## Change 7: Add hypothesis conditional to allOf

```json
// In: allOf array, add a second conditional after the existing evidence one:
"allOf": [
  {
    "if": {
      "properties": { "record_type": { "const": "evidence" } }
    },
    "then": {
      "required": ["descriptors"]
    }
  },
  {
    "if": {
      "properties": { "record_type": { "const": "hypothesis" } }
    },
    "then": {
      "required": ["hypothesis"]
    }
  }
]
```

## Change 8: Add hypothesis block to root properties

```json
// In: properties (at root level, alongside sample, system, context, etc.)
// Add the complete hypothesis block from hypothesis_schema_block.json
"hypothesis": {
  // ... (full definition in hypothesis_schema_block.json — 464 lines)
}
```

## Summary of line changes

| Location | Change | Lines affected |
|----------|--------|---------------|
| record_type enum | Add "hypothesis" | +1 |
| record_domain enum | Add "hypothesis" | +1 |
| system.domain enum | Add "analytical" | +1 |
| system.technique enum | Add 2 values | +2 |
| links.rel enum | Add 3 values | +3 |
| links.basis enum | Add 3 values | +3 |
| allOf | Add hypothesis conditional | +8 |
| properties | Add hypothesis block | +462 |

**Total: ~481 lines added, 0 lines modified, 0 lines removed.**

No existing records are affected. All changes are purely additive.
