"""
ats/ — Phase 4: ATS Integration Layer.

Responsibilities:
  - Accept v7.0.0 parse results only (reject older schemas).
  - Transform parsed resume into ATS-compatible formats.
  - Score resumes against job descriptions.
  - Export to common ATS wire formats (Greenhouse, Lever, Workday, generic JSON).
  - Anomaly gating: block or flag results with critical anomalies.
"""
