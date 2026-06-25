"""
backend/services/export_service.py — PDF, JSON, CSV export generation.

PDF is generated using reportlab (pure Python — no system dependencies).
Every export includes: candidate name, timestamps, ATS score, breakdown,
skills, projects, JD match, recommendations, and a footer.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _safe(v, default="N/A"):
    return v if v is not None else default


# ── JSON Export ───────────────────────────────────────────────────────────────

def generate_json(data: dict) -> dict:
    """Return a structured JSON export of the analysis data."""
    return {
        "export_metadata": {
            "generated_at": _ts(),
            "source": "ResumeAI v4.0.0",
            "format": "json",
        },
        "candidate": data.get("candidate", {}),
        "ats_analysis": data.get("ats_analysis", {}),
        "jd_match": data.get("jd_match", {}),
        "skills": data.get("skills", {}),
        "projects": data.get("projects", []),
        "recommendations": data.get("recommendations", []),
    }


# ── CSV Export ────────────────────────────────────────────────────────────────

def generate_csv(data: dict) -> str:
    """Return CSV string with key resume metrics."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Field", "Value"])
    writer.writerow(["Generated At", _ts()])
    writer.writerow(["Source", "ResumeAI v4.0.0"])
    writer.writerow([])

    # Candidate
    candidate = data.get("candidate", {})
    writer.writerow(["=== CANDIDATE ==="])
    writer.writerow(["Name", _safe(candidate.get("name"))])
    writer.writerow(["Email", _safe(candidate.get("email"))])
    writer.writerow([])

    # ATS
    ats = data.get("ats_analysis", {})
    writer.writerow(["=== ATS ANALYSIS ==="])
    writer.writerow(["ATS Score", _safe(ats.get("score"))])
    breakdown = ats.get("breakdown", {})
    for k, v in breakdown.items():
        writer.writerow([f"  {k}", v])
    writer.writerow([])

    # JD Match
    jd = data.get("jd_match", {})
    if jd:
        writer.writerow(["=== JD MATCH ==="])
        writer.writerow(["Job Title", _safe(jd.get("job_title"))])
        writer.writerow(["Match Score", _safe(jd.get("match_score"))])
        writer.writerow(["Matched Skills", ", ".join(jd.get("matched_skills", []))])
        writer.writerow(["Missing Skills", ", ".join(jd.get("missing_skills", []))])
        writer.writerow([])

    # Skills
    skills = data.get("skills", {})
    if skills:
        writer.writerow(["=== SKILLS ==="])
        for s in skills.get("flat_list", []):
            writer.writerow(["Skill", s])
        writer.writerow([])

    return output.getvalue()


# ── PDF Export ────────────────────────────────────────────────────────────────

def generate_pdf(data: dict) -> bytes:
    """Generate a professionally formatted PDF report using reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()

    # ── Custom Styles ─────────────────────────────────────────────────────
    PURPLE = colors.HexColor("#4F46E5")
    LIGHT_PURPLE = colors.HexColor("#EEF2FF")
    DARK = colors.HexColor("#0F172A")
    MUTED = colors.HexColor("#64748B")
    SUCCESS = colors.HexColor("#10B981")
    WARNING = colors.HexColor("#F59E0B")
    DANGER = colors.HexColor("#EF4444")

    title_style = ParagraphStyle("Title", parent=styles["Heading1"],
        fontSize=22, textColor=PURPLE, spaceAfter=4, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"],
        fontSize=11, textColor=MUTED, spaceAfter=16, alignment=TA_CENTER)
    section_style = ParagraphStyle("Section", parent=styles["Heading2"],
        fontSize=13, textColor=PURPLE, spaceBefore=16, spaceAfter=6,
        borderPad=4)
    body_style = ParagraphStyle("Body", parent=styles["Normal"],
        fontSize=9.5, textColor=DARK, spaceAfter=4, leading=14)
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"],
        fontSize=8, textColor=MUTED, alignment=TA_CENTER)

    # ── Data extraction ───────────────────────────────────────────────────
    candidate = data.get("candidate", {})
    ats = data.get("ats_analysis", {})
    jd = data.get("jd_match", {})
    skills_data = data.get("skills", {})
    projects = data.get("projects", [])
    recs = data.get("recommendations", [])

    name = _safe(candidate.get("name"), "Candidate")
    email = _safe(candidate.get("email"), "")
    ats_score = ats.get("score")
    match_score = jd.get("match_score")

    # ── Score colour helper ───────────────────────────────────────────────
    def score_color(score):
        if score is None: return MUTED
        if score >= 75:   return SUCCESS
        if score >= 50:   return WARNING
        return DANGER

    story = []

    # ── Header ────────────────────────────────────────────────────────────
    story.append(Paragraph("✦ ResumeAI", title_style))
    story.append(Paragraph("Resume Analysis Report", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=PURPLE))
    story.append(Spacer(1, 12))

    # Candidate info
    info_rows = [
        ["Candidate", name],
        ["Email", email],
        ["Generated At", _ts()],
    ]
    if ats_score is not None:
        info_rows.append(["ATS Score", f"{ats_score:.1f} / 100"])
    if match_score is not None:
        info_rows.append(["JD Match Score", f"{match_score:.1f} / 100"])

    info_table = Table(info_rows, colWidths=[4*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), PURPLE),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_PURPLE, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 16))

    # ── ATS Breakdown ─────────────────────────────────────────────────────
    breakdown = ats.get("breakdown", {})
    if breakdown:
        story.append(Paragraph("ATS Score Breakdown", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0")))
        story.append(Spacer(1, 6))
        bd_rows = [["Component", "Score"]]
        for k, v in breakdown.items():
            bd_rows.append([k.replace("_", " ").title(), str(v)])
        bd_table = Table(bd_rows, colWidths=[10*cm, 6*cm])
        bd_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_PURPLE]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(bd_table)
        story.append(Spacer(1, 10))

    # ── Skills ────────────────────────────────────────────────────────────
    flat_skills = skills_data.get("flat_list", [])
    if flat_skills:
        story.append(Paragraph("Skills", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0")))
        story.append(Spacer(1, 6))
        story.append(Paragraph(", ".join(flat_skills), body_style))
        story.append(Spacer(1, 10))

    # ── JD Match ──────────────────────────────────────────────────────────
    if jd:
        story.append(Paragraph("Job Description Match", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0")))
        story.append(Spacer(1, 6))

        jd_rows = [["Field", "Detail"]]
        if jd.get("job_title"):
            jd_rows.append(["Job Title", jd["job_title"]])
        jd_rows.append(["Match Score", f"{match_score:.1f} / 100" if match_score else "N/A"])

        matched = jd.get("matched_skills", [])
        missing = jd.get("missing_skills", [])
        if matched:
            jd_rows.append(["Matched Skills", ", ".join(matched)])
        if missing:
            jd_rows.append(["Missing Skills", ", ".join(missing)])

        jd_table = Table(jd_rows, colWidths=[5*cm, 11*cm])
        jd_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("TEXTCOLOR", (0, 1), (0, -1), PURPLE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_PURPLE]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(jd_table)
        story.append(Spacer(1, 10))

    # ── Projects ──────────────────────────────────────────────────────────
    if projects:
        story.append(Paragraph("Projects", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0")))
        story.append(Spacer(1, 6))
        for proj in projects[:6]:
            pname = proj.get("name", "Unnamed Project")
            pdesc = proj.get("description", "")
            techs = proj.get("technologies", [])
            blk = []
            blk.append(Paragraph(f"<b>{pname}</b>", body_style))
            if pdesc:
                blk.append(Paragraph(pdesc, body_style))
            if techs:
                blk.append(Paragraph(f"<i>Technologies: {', '.join(techs)}</i>", body_style))
            blk.append(Spacer(1, 6))
            story.append(KeepTogether(blk))

    # ── Recommendations ───────────────────────────────────────────────────
    if recs:
        story.append(Paragraph("Recommendations", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0")))
        story.append(Spacer(1, 6))
        for rec in recs:
            story.append(Paragraph(f"• {rec}", body_style))
        story.append(Spacer(1, 10))

    # ── Footer ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0")))
    story.append(Paragraph(
        f"Generated by ResumeAI v4.0.0 · {_ts()} · Confidential",
        footer_style,
    ))

    doc.build(story)
    return buffer.getvalue()
