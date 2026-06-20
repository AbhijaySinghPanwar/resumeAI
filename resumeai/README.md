# ResumeAI Parser — v7.0.0

A **deterministic, ownership-based** resume parsing pipeline.  
Built to be stable across thousands of resume formats instead of patching one failure at a time.

---

## The Problem This Solves

Regex-driven parsers accumulate aliases until they collapse under their own weight:

- Certifications absorb leadership content (unrecognized header, no ownership transition)
- Education disappears (year-prefixed lines confuse the boundary detector)
- Leadership silently vanishes (combined headers like `Positions of Responsibility / Extracurriculars` not in alias list)
- Tests pass while real resumes fail (fixtures were clean ASCII; production PDFs had artifacts)

**v7.0.0 is a ground-up redesign.** It solves ownership structurally, not with more aliases.

---

## Architecture — Four Phases

```
PDF / Text
    │
    ▼
┌─────────────────────────────────────────┐
│  PHASE 1 — Section Ownership Engine     │
│                                         │
│  normalizer.py     ← artifact cleanup   │
│  header_detector.py ← 5-stage pipeline  │
│  ownership_engine.py ← state machine    │
│                                         │
│  Output: List[SectionBlock] + DebugLog  │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  PHASE 2 — Field Extractors             │
│                                         │
│  contact.py   experience.py             │
│  education.py leadership.py             │
│  projects.py  certifications.py         │
│  skills.py    summary.py                │
│                                         │
│  Each extractor: isolated, no shared    │
│  state, consumes only its own block     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  PHASE 3 — Schema v7.0.0                │
│                                         │
│  schema.py ← contract enforcement       │
│  All arrays always exist                │
│  All objects always exist               │
│  debug block always present             │
│  Versioned, frontend-safe               │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  PHASE 4 — ATS Integration              │
│                                         │
│  gate.py     ← version + anomaly gate   │
│  exporters.py ← Greenhouse/Lever/       │
│                 Workday/CSV             │
│  scorer.py   ← JD match scoring         │
└─────────────────────────────────────────┘
```

### Core Guarantee: Ownership

Every line belongs to **exactly one** section. No line can belong to two sections.  
An unrecognized header **closes** the previous section immediately — it cannot bleed.  
This is enforced structurally, not by aliases.

### Header Detection Pipeline (5 Stages)

```
Raw line
  │
  ├─ Stage 1: Artifact normalization
  │     zero-width chars, Unicode dashes, spaced chars ("L e a d e r s h i p"), smart quotes
  │
  ├─ Stage 2: Structural signal scoring
  │     all-caps, title-case, short length, terminal punctuation, context signals
  │
  ├─ Stage 3: Exact alias matching
  │     fixed registry → canonical section name
  │
  ├─ Stage 4: Combined header resolution
  │     "Positions of Responsibility / Extracurriculars" → leadership
  │     "Education and Certifications" → education (higher priority)
  │
  └─ Stage 5: Fuzzy matching fallback
        rapidfuzz token_sort_ratio against all aliases
        ambiguous → other_section (but previous section still CLOSES)
```

---

## Project Structure

```
resumeai/
├── __init__.py
├── __main__.py              # python -m resumeai resume.pdf
├── cli.py                   # command-line interface
├── pipeline.py              # main orchestration
├── setup.py
├── requirements.txt
├── pytest.ini
├── conftest.py
│
├── core/
│   ├── constants.py         # canonical sections, alias registry, thresholds
│   ├── normalizer.py        # Phase 1 Stage 1: artifact cleanup
│   ├── header_detector.py   # Phase 1 Stages 2-5: header detection
│   ├── ownership_engine.py  # Phase 1: state machine + debug output
│   ├── pdf_extractor.py     # pdfplumber + PyPDF2 extraction
│   └── schema.py            # v7.0.0 schema definition + validator
│
├── extractors/
│   ├── date_utils.py        # shared date parsing
│   ├── contact.py
│   ├── summary.py
│   ├── education.py
│   ├── experience.py
│   ├── projects.py
│   ├── leadership.py
│   ├── certifications.py
│   └── skills.py
│
├── ats/
│   ├── gate.py              # Phase 4: version enforcement + anomaly gating
│   ├── exporters.py         # Greenhouse, Lever, Workday, CSV export
│   └── scorer.py            # JD match scoring
│
└── tests/
    ├── fixtures/
    │   └── fixtures.py      # 8 realistic resume fixtures + ground truth
    ├── unit/
    │   ├── test_normalizer.py      # 25 tests
    │   ├── test_header_detector.py # 38 tests
    │   └── test_ownership_engine.py # 73 tests
    ├── integration/
    │   ├── test_pipeline.py  # 85 tests
    │   └── test_ats.py       # 26 tests
    └── adversarial/
        └── test_adversarial.py # 35 tests (extreme inputs)
```

**Total: 256 tests, all passing.**

---

## Quick Start

### Install

```bash
pip install -r requirements.txt
pip install -e .
```

### Parse a resume

```python
from resumeai.pipeline import parse_resume

# From PDF
result = parse_resume("resume.pdf")

# From plain text
result = parse_resume("raw text of resume...", source_type="text")

# From pre-split lines
result = parse_resume(["line1", "line2", ...], source_type="lines")
```

### Result structure (v7.0.0)

```python
{
    "version": "7.0.0",
    "contact": {
        "name": "Priya Sharma",
        "email": "priya@email.com",
        "phone": "+91-9876543210",
        "location": "Bangalore, India",
        "linkedin": "https://linkedin.com/in/priyasharma",
        "github": None,
        "portfolio": None,
        "other_links": []
    },
    "summary": "Results-driven software engineer...",
    "education": [
        {
            "institution": "IIT Bombay",
            "degree": "B.Tech",
            "field_of_study": "Computer Science",
            "start_date": "2017",
            "end_date": "2021",
            "gpa": "8.7",
            "honors": [],
            "raw_lines": [...]
        }
    ],
    "experience": [...],
    "projects": [...],
    "leadership": [...],
    "certifications": [...],
    "skills": {
        "categories": [{"category": "Languages", "skills": ["Python", "Java"]}],
        "flat_list": ["Python", "Java", "Django", ...],
        "raw_lines": [...]
    },
    "other_section": {"blocks": [...]},
    "metadata": {
        "parse_duration_ms": 12,
        "sections_detected": ["contact", "education", "experience", ...],
        "parser_version": "7.0.0",
        "anomaly_count": 0
    },
    "debug": {
        "detected_headers": [...],
        "section_transitions": [...],
        "unrecognized_headers": [...],
        "ownership_log": [...],
        "anomalies": [...]
    }
}
```

### ATS Integration

```python
from resumeai.ats.gate import ATSGate
from resumeai.ats.exporters import to_greenhouse, to_lever, to_workday
from resumeai.ats.scorer import ResumeScorer

# Gate check (blocks bad results before ATS submission)
gate = ATSGate()
decision = gate.evaluate(result)
if decision.passed:
    greenhouse_payload = to_greenhouse(result)
    # POST to Greenhouse API...

# JD scoring
scorer = ResumeScorer()
report = scorer.score(result, job_description_text)
print(f"{report.overall_score:.1f}/100 — Grade: {report.grade}")
print(f"Matched skills: {report.matched_skills}")
print(report.recommendation)
```

### CLI

```bash
# Parse and print JSON
python -m resumeai resume.pdf

# Export to Greenhouse format
python -m resumeai resume.pdf --format greenhouse

# Export to Lever
python -m resumeai resume.pdf --format lever

# Export to Workday flat structure
python -m resumeai resume.pdf --format workday

# Export as CSV row
python -m resumeai resume.pdf --format csv

# Score against a job description
python -m resumeai resume.pdf --score-file job_description.txt

# ATS gate check (exits 1 if blocked)
python -m resumeai resume.pdf --gate

# Schema validation only
python -m resumeai resume.pdf --validate-only

# Strip debug output
python -m resumeai resume.pdf --no-debug

# Plain text input
python -m resumeai resume.txt --input-type text
```

### Run tests

```bash
# All 256 tests
pytest

# With coverage
pytest --cov=resumeai --cov-report=html

# Specific suites
pytest tests/unit/                  # normalizer, header detector, ownership engine
pytest tests/integration/           # full pipeline + ATS
pytest tests/adversarial/           # extreme inputs
pytest tests/unit/test_ownership_engine.py -k "bleeding"   # regression tests only
```

---

## Schema Contract (v7.0.0)

| Rule | Enforcement |
|------|------------|
| All arrays always exist | `schema.py validate_result()` |
| All objects always exist | `schema.py validate_result()` |
| No fields conditionally absent | Checked on every parse |
| Debug block always present | Never stripped pre-validation |
| Version field always present | Gate rejects wrong versions |
| Deterministic output | 256 determinism tests |

---

## Anomaly Detection

The debug block automatically flags suspicious parse results:

| Anomaly | Meaning | Severity |
|---------|---------|----------|
| `zero_transitions` | No section headers recognized at all | error |
| `certifications_absorbed_content` | Certs block suspiciously large | error |
| `empty_section` | Expected section has zero lines | warning |
| `suspiciously_large_section` | One section owns >60% of document | warning |
| `no_leadership_detected` | Leadership keywords found outside leadership section | warning |

---

## Adding New Section Aliases

Edit **only** `core/constants.py`, inside `SECTION_REGISTRY`.  
Nowhere else. No other file stores aliases.

```python
AliasEntry("leadership", aliases=[
    ...,
    "your new alias here",   # ← add here
]),
```

The alias is automatically picked up by exact matching, combined header resolution,
and fuzzy matching. No other code changes needed.

---

## Why Previous Tests Passed But Production Failed

The previous test suite was **tautological** — fixtures were written by developers
who knew what the parser expected, so inputs were clean ASCII with no PDF artifacts.

This suite fixes that:

1. **Fixture inputs include real artifacts** (spaced chars, Unicode dashes, zero-width chars)
2. **Ground truth is manually curated**, not auto-generated by the parser
3. **Structural invariant tests** run on every fixture regardless of content
4. **Adversarial tests** use deliberately pathological inputs
5. **Regression tests** are named after the exact production failure they prevent

---

## License

MIT
