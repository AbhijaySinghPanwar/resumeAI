#!/usr/bin/env python3
"""
cli.py — Command-line interface for ResumeAI Parser v7.0.0

Usage:
    python -m resumeai.cli resume.pdf
    python -m resumeai.cli resume.pdf --format greenhouse
    python -m resumeai.cli resume.pdf --format lever --no-debug
    python -m resumeai.cli resume.pdf --score "job description text..."
    python -m resumeai.cli resume.txt --input-type text
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="resumeai",
        description="ResumeAI Parser v7.0.0 — Deterministic resume parsing pipeline",
    )
    parser.add_argument("input", help="Path to resume file (PDF or text)")
    parser.add_argument(
        "--input-type", choices=["auto", "pdf", "text"], default="auto",
        help="Force input type (default: auto-detect)"
    )
    parser.add_argument(
        "--format", choices=["json", "greenhouse", "lever", "workday", "csv"],
        default="json", help="Output format (default: json)"
    )
    parser.add_argument(
        "--no-debug", action="store_true",
        help="Strip debug block from output"
    )
    parser.add_argument(
        "--score", metavar="JD_TEXT",
        help="Score resume against a job description string"
    )
    parser.add_argument(
        "--score-file", metavar="JD_FILE",
        help="Score resume against a job description file"
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Run parse and schema validation only, print violations"
    )
    parser.add_argument(
        "--gate", action="store_true",
        help="Run ATS gate check and print decision"
    )
    parser.add_argument(
        "--indent", type=int, default=2,
        help="JSON indentation level (default: 2)"
    )

    args = parser.parse_args()

    # ── Parse ─────────────────────────────────────────────────────────────────
    from resumeai.pipeline import ResumeParser

    rparser = ResumeParser(
        strict_schema=False,
        include_debug=not args.no_debug,
    )

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    input_type = args.input_type
    if input_type == "auto":
        input_type = "pdf" if input_path.suffix.lower() == ".pdf" else "text"

    try:
        if input_type == "pdf":
            result = rparser.parse_pdf(input_path)
        else:
            text = input_path.read_text(encoding="utf-8")
            result = rparser.parse_text(text)
    except Exception as e:
        print(f"Error: Parse failed: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Validate only ─────────────────────────────────────────────────────────
    if args.validate_only:
        from resumeai.core.schema import validate_result
        violations = validate_result(result)
        if violations:
            print(f"SCHEMA VIOLATIONS ({len(violations)}):")
            for v in violations:
                print(f"  - {v}")
            sys.exit(1)
        else:
            print("Schema valid. ✓")
            anomalies = result.get("debug", {}).get("anomalies", [])
            if anomalies:
                print(f"\nAnomalies detected ({len(anomalies)}):")
                for a in anomalies:
                    print(f"  [{a.get('severity','?').upper()}] {a.get('type')}: {a.get('detail')}")
            sys.exit(0)

    # ── ATS Gate ──────────────────────────────────────────────────────────────
    if args.gate:
        from resumeai.ats.gate import ATSGate
        gate = ATSGate()
        decision = gate.evaluate(result)
        print(json.dumps(decision.to_dict(), indent=args.indent))
        sys.exit(0 if decision.passed else 1)

    # ── Scoring ───────────────────────────────────────────────────────────────
    if args.score or args.score_file:
        from resumeai.ats.scorer import ResumeScorer
        jd_text = args.score
        if args.score_file:
            jd_text = Path(args.score_file).read_text(encoding="utf-8")
        scorer = ResumeScorer()
        report = scorer.score(result, jd_text)
        print(json.dumps(report.to_dict(), indent=args.indent))
        return

    # ── Format and output ─────────────────────────────────────────────────────
    if args.format == "json":
        from resumeai.ats.exporters import to_generic_json
        print(to_generic_json(result, strip_debug=args.no_debug, indent=args.indent))

    elif args.format == "greenhouse":
        from resumeai.ats.exporters import to_greenhouse
        print(json.dumps(to_greenhouse(result), indent=args.indent, default=str))

    elif args.format == "lever":
        from resumeai.ats.exporters import to_lever
        print(json.dumps(to_lever(result), indent=args.indent, default=str))

    elif args.format == "workday":
        from resumeai.ats.exporters import to_workday
        print(json.dumps(to_workday(result), indent=args.indent, default=str))

    elif args.format == "csv":
        from resumeai.ats.exporters import to_csv_row
        print(to_csv_row(result))


if __name__ == "__main__":
    main()
