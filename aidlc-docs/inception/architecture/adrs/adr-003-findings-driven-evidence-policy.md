# ADR-003: Findings-Driven Evidence Policy

## Status

Accepted

## Date

2026-06-03

## Context

ADR-002 fixed the MVP screenshot policy to "failure + final step" to protect the S3 budget
(~500 MB/month vs ~17 GB/month if every step were captured). The 2026-06-02 scope realignment
(branch `rework/storefront-audit-scope`) restored the **6-dimension audit document** as a core
deliverable (PRD M21, RF-24/RF-25). An audit document without visual evidence linked to each
finding is hard to read and violates the product principle "trazabilidad sobre opinión —
sin evidencia no hay hallazgo".

The naive fix — capturing every module in OK+FAIL states — was already rejected by ADR-002
for cost reasons. The team decision (2026-06-03, scope-realignment-brief §7-#5) is that
captures must exist "solo cuando realmente valga la pena resaltar algo".

## Decision

Evidence capture is **event-driven, never schedule-driven**:

1. **Always (all modes)** — unchanged from ADR-002: capture on step failure + final step of
   each executed flow.
2. **Audit/exploratory context** — additional captures ONLY when:
   - a deterministic collector (RF-24) emits a **finding** in one of the 6 audit dimensions —
     the capture is taken at the finding's page/moment and linked in `evidence_refs`; or
   - the flow reaches a **critical point declared in the FlowCatalog** (e.g., payment summary,
     card-declined validation). Critical points are declared per flow in the catalog, never
     ad-hoc inside step code.
3. **Never** capture an OK step that has no finding and no declared critical point.
4. `capture_intermediate_screenshots` remains `const false` in the schema — findings-driven
   capture is not "intermediate screenshots": per-step/calendar capture stays forbidden.
5. Naming extends the ADR-002 convention: `{run_id}/{perfil}/{flujo}/{paso}-{fail|final|finding-{dimension}|critical}.png`.
6. Network evidence (HAR, RF-23) follows the same S3 lifecycle as visual evidence
   (90 days hot → Glacier) and the PRD C4 cost KPI (≤1 GB week 4, ≤5 GB week 12) remains the
   control criterion.

This ADR **amends ADR-002** (it does not replace it): the ADR-002 baseline policy is intact
for gate mode; this ADR adds the bounded, event-driven extension required by the audit document.

## Consequences

### Positive

- The audit document gets visual evidence exactly where it adds signal — every capture exists
  because a finding or a declared critical process point justifies it (zero noise).
- Cost stays near the ADR-002 budget: a clean module produces zero extra evidence.
- Evidence is self-explaining: the filename carries why it was captured (`finding-{dim}`,
  `critical`).
- The deterministic collectors are the single trigger for finding-evidence — the LLM agent
  cannot cause captures (consistent with P7/C10).

### Negative

- A finding missed by a collector produces no visual evidence (the collectors' coverage
  bounds the audit document's evidence).
- Critical points require curation in the FlowCatalog — adding a flow now includes deciding
  its critical points.
- Worst-case storage is less predictable than fixed fail+final (bounded by findings count);
  mitigated by the C4 KPI watch and S3 lifecycle.

## Verification

This decision is verified when:

- A clean run (no findings) in audit mode produces exactly the ADR-002 set: failure (if any) +
  final-step screenshots.
- A run with a seeded finding produces one additional capture named `finding-{dimension}` and
  linked in that finding's `evidence_refs`.
- Critical-point captures only occur at points declared in the FlowCatalog (test enumerates
  the catalog and asserts no other `critical` captures exist).
- `capture_intermediate_screenshots` remains `const false` in `specs/synthetic-user-config.schema.json` (v2).
- `screenshot_state` in `specs/execution_report.schema.json` (v2) only admits
  `fail | final | finding | critical`.

## Related Artifacts

- `aidlc-docs/inception/architecture/adrs/adr-002-screenshot-capture-policy.md` (amended)
- `aidlc-docs/inception/scope-realignment-brief.md` (§7-#5)
- `aidlc-docs/inception/requirements/requirements.md` (RF-26, C4)
- `aidlc-docs/inception/user-stories/user-stories.md` (H7.4, D16)
- `specs/synthetic-user-config.schema.json` (v2)
- `specs/execution_report.schema.json` (v2)
