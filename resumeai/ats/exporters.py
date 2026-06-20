"""
ats/exporters.py — Transform v7.0.0 results into ATS wire formats.

Supported targets:
  - generic_json   : Clean JSON for internal APIs (no debug, no raw_lines)
  - greenhouse     : Greenhouse ATS candidate format
  - lever          : Lever ATS candidate format
  - workday        : Workday-compatible flat structure
  - csv_row        : Single CSV row for bulk import pipelines
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── Generic JSON export ───────────────────────────────────────────────────────

def to_generic_json(result: Dict[str, Any], strip_debug: bool = True, indent: int = 2) -> str:
    """
    Export a v7.0.0 result as clean JSON.
    Strips debug and raw_lines by default for external consumption.
    """
    output = _clean_for_export(result, strip_debug=strip_debug)
    return json.dumps(output, indent=indent, ensure_ascii=False, default=str)


def _clean_for_export(result: Dict[str, Any], strip_debug: bool = True) -> Dict[str, Any]:
    import copy
    cleaned = copy.deepcopy(result)

    if strip_debug:
        cleaned.pop("debug", None)
        cleaned.get("metadata", {}).pop("invariant_violations", None)

    # Strip raw_lines from all list sections
    for section in ["education", "experience", "projects", "leadership", "certifications"]:
        for entry in cleaned.get(section, []):
            entry.pop("raw_lines", None)

    if isinstance(cleaned.get("skills"), dict):
        cleaned["skills"].pop("raw_lines", None)

    cleaned.pop("other_section", None)
    return cleaned


# ── Greenhouse export ─────────────────────────────────────────────────────────

def to_greenhouse(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert to Greenhouse Harvest API candidate format.
    https://developers.greenhouse.io/harvest.html#candidates
    """
    contact = result.get("contact", {})
    education = result.get("education", [])
    experience = result.get("experience", [])

    # Greenhouse phone_numbers format
    phones = []
    if contact.get("phone"):
        phones.append({"value": contact["phone"], "type": "mobile"})

    # Greenhouse email_addresses format
    emails = []
    if contact.get("email"):
        emails.append({"value": contact["email"], "type": "personal"})

    # Greenhouse website_addresses
    websites = []
    if contact.get("linkedin"):
        websites.append({"value": contact["linkedin"], "type": "linkedin"})
    if contact.get("github"):
        websites.append({"value": contact["github"], "type": "github"})
    if contact.get("portfolio"):
        websites.append({"value": contact["portfolio"], "type": "portfolio"})

    # Greenhouse educations
    gh_educations = []
    for edu in education:
        gh_educations.append({
            "school_name": edu.get("institution"),
            "degree": edu.get("degree"),
            "discipline": edu.get("field_of_study"),
            "start_date": _gh_date(edu.get("start_date")),
            "end_date": _gh_date(edu.get("end_date")),
        })

    # Greenhouse employments
    gh_employments = []
    for exp in experience:
        gh_employments.append({
            "company_name": exp.get("company"),
            "title": exp.get("title"),
            "start_date": _gh_date(exp.get("start_date")),
            "end_date": _gh_date(exp.get("end_date")),
            "current": exp.get("is_current", False),
        })

    return {
        "first_name": _first_name(contact.get("name")),
        "last_name": _last_name(contact.get("name")),
        "phone_numbers": phones,
        "email_addresses": emails,
        "website_addresses": websites,
        "addresses": [{"value": contact.get("location"), "type": "home"}]
            if contact.get("location") else [],
        "educations": gh_educations,
        "employments": gh_employments,
        "resume_source": "ResumeAI",
        "_meta": {
            "parser_version": result.get("version"),
            "parsed_at": result.get("debug", {}).get("parse_timestamp"),
        },
    }


def _gh_date(date_str: Optional[str]) -> Optional[Dict]:
    """Convert 'YYYY-MM' or 'YYYY' to Greenhouse date object."""
    if not date_str:
        return None
    parts = date_str.split("-")
    if len(parts) == 2:
        return {"year": int(parts[0]), "month": int(parts[1]), "day": None}
    try:
        return {"year": int(parts[0]), "month": None, "day": None}
    except ValueError:
        return None


# ── Lever export ──────────────────────────────────────────────────────────────

def to_lever(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert to Lever Postings API candidate format.
    https://hire.lever.co/developer/postings
    """
    contact = result.get("contact", {})
    experience = result.get("experience", [])
    education = result.get("education", [])
    skills = result.get("skills", {})

    # Lever uses a flat candidate structure
    return {
        "name": contact.get("name"),
        "email": contact.get("email"),
        "phone": contact.get("phone"),
        "location": contact.get("location"),
        "links": list(filter(None, [
            contact.get("linkedin"),
            contact.get("github"),
            contact.get("portfolio"),
        ])),
        "headline": _build_headline(experience),
        "summary": result.get("summary"),
        "tags": skills.get("flat_list", [])[:20],  # Lever limits tags
        "sources": ["ResumeAI"],
        "origin": "sourced",
        "resumeFiles": [],       # caller must attach actual file
        "customFields": {
            "education_count": len(education),
            "experience_count": len(experience),
            "certifications": [c.get("name") for c in result.get("certifications", []) if c.get("name")],
            "parser_version": result.get("version"),
        },
    }


def _build_headline(experience: List[Dict]) -> Optional[str]:
    """Build a one-line headline from most recent experience."""
    if not experience:
        return None
    latest = experience[0]
    parts = [p for p in [latest.get("title"), latest.get("company")] if p]
    return " at ".join(parts) if parts else None


# ── Workday export ────────────────────────────────────────────────────────────

def to_workday(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert to Workday-compatible flat candidate structure.
    Workday prefers flat, denormalized records for bulk import.
    """
    contact = result.get("contact", {})
    education = result.get("education", [])
    experience = result.get("experience", [])
    skills = result.get("skills", {})
    certs = result.get("certifications", [])

    # Flatten education
    edu_str = "; ".join(
        f"{e.get('degree', '')} from {e.get('institution', '')} ({e.get('end_date', '')})"
        for e in education if e.get("institution") or e.get("degree")
    )

    # Flatten experience
    exp_str = "; ".join(
        f"{e.get('title', '')} at {e.get('company', '')} ({e.get('start_date', '')}–{e.get('end_date', '')})"
        for e in experience if e.get("company") or e.get("title")
    )

    # Flatten skills
    skills_str = ", ".join(skills.get("flat_list", [])[:30])

    # Flatten certs
    certs_str = "; ".join(c.get("name", "") for c in certs if c.get("name"))

    return {
        "Candidate_ID": None,          # Workday generates this
        "First_Name": _first_name(contact.get("name")),
        "Last_Name": _last_name(contact.get("name")),
        "Email_Address": contact.get("email"),
        "Phone_Number": contact.get("phone"),
        "Address": contact.get("location"),
        "LinkedIn_URL": contact.get("linkedin"),
        "Resume_Source": "ResumeAI",
        "Education_History": edu_str,
        "Work_Experience": exp_str,
        "Skills": skills_str,
        "Certifications": certs_str,
        "Years_Experience": _estimate_years_experience(experience),
        "Parser_Version": result.get("version"),
    }


def _estimate_years_experience(experience: List[Dict]) -> Optional[int]:
    """Rough estimate of total years of experience from date ranges."""
    if not experience:
        return None
    total_months = 0
    for exp in experience:
        start = exp.get("start_date")
        end = exp.get("end_date")
        if not start:
            continue
        try:
            start_year = int(start[:4])
            if end:
                end_year = int(end[:4])
            else:
                end_year = datetime.now().year
            total_months += (end_year - start_year) * 12
        except (ValueError, TypeError):
            continue
    return max(0, total_months // 12) if total_months else None


# ── CSV export ────────────────────────────────────────────────────────────────

def to_csv_row(result: Dict[str, Any]) -> str:
    """
    Export a single resume as a CSV row (for bulk import pipelines).
    Returns a single CSV line string including header on first call.
    """
    workday = to_workday(result)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(workday.keys()))
    writer.writeheader()
    writer.writerow(workday)
    return output.getvalue()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _first_name(full_name: Optional[str]) -> Optional[str]:
    if not full_name:
        return None
    parts = full_name.strip().split()
    return parts[0] if parts else None


def _last_name(full_name: Optional[str]) -> Optional[str]:
    if not full_name:
        return None
    parts = full_name.strip().split()
    return parts[-1] if len(parts) > 1 else None
