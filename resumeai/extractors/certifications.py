"""
extractors/certifications.py — Phase 1.6 Certification Extraction.

Phase 1.6 fix: Uses continuation-line detection so that wrapped description
lines (e.g., "services, cloud security..." after "AWS Certified...") are
merged into the current certification instead of becoming a new card.

Each certification → one object: {name, issuer, date, description, credential_id}
"""

import re
from typing import Dict, List, Optional

from resumeai.extractors.date_utils import extract_years, parse_date, is_date_line
from resumeai.extractors._continuation import is_continuation

BULLET_RE     = re.compile(r"^[\-\*\•\·\◦\▸\►\–\—]\s+")
PIPE_SEP_RE   = re.compile(r"\s*[|\-\u2013\u2014/]\s*")
CREDENTIAL_RE = re.compile(r"(?:credential|cert(?:ificate)?|license|id)[:\s#]+([A-Z0-9\-]+)", re.IGNORECASE)
DATE_PREFIX_RE= re.compile(r"^(\d{4})\s*[\-–—]\s*(.+)")  # "2026—AWS Certified..."

EXACT_ISSUERS = {
    "amazon","aws","google","microsoft","azure","comptia","cisco",
    "oracle","ibm","salesforce","pmi","isaca","isc2","ec-council",
    "coursera","udemy","edx","nptel","linkedin","meta","mongodb",
    "databricks","snowflake","hashicorp","red hat","vmware",
    "amazon web services","ibm skills network","postman",
    "cfa institute","garp","cncf","iassc","autodesk","nvidia",
}

ISSUER_NORMALIZE = {
    "aws": "AWS", "ibm": "IBM", "cncf": "CNCF", "garp": "GARP",
    "google": "Google", "microsoft": "Microsoft", "oracle": "Oracle",
    "meta": "Meta", "nvidia": "NVIDIA", "cisco": "Cisco",
    "comptia": "CompTIA", "coursera": "Coursera", "udemy": "Udemy",
}


def _empty_cert() -> Dict:
    return {"name": None, "issuer": None, "date": None,
            "description": None, "credential_id": None, "raw_lines": []}


def _is_new_cert_line(stripped: str, prev_cert: Optional[Dict]) -> bool:
    """
    Decide if this line starts a new certification.
    A line is NOT a new cert if is_continuation() returns True, or if it's
    a pure date/issuer line that belongs to the current cert.
    """
    if not stripped:
        return False

    # Continuation → never a new cert
    if is_continuation(stripped):
        return False

    # Always-new: bullet prefix
    if BULLET_RE.match(stripped):
        return True

    # Always-new: date prefix like "2025—Certification Name"
    if DATE_PREFIX_RE.match(stripped):
        return True

    # Pure date/year line → metadata for current cert, not a new one
    years = extract_years(stripped)
    if years and len(stripped) < 12:
        return False

    # Known issuer on its own → metadata for current cert
    lower = stripped.lower()
    if lower in EXACT_ISSUERS:
        return False

    # Has a pipe separator + issuer keyword → structured cert line
    if "|" in stripped and any(kw in lower for kw in EXACT_ISSUERS):
        return True

    # If there's no current cert → first cert
    if prev_cert is None or prev_cert["name"] is None:
        return True

    # Current cert already complete (name + date + issuer) → new cert title
    if (prev_cert["name"]
            and prev_cert.get("date")
            and prev_cert.get("issuer")
            and not is_date_line(stripped)
            and lower not in EXACT_ISSUERS):
        return True

    # Current cert has name + one of {date, issuer} → new title starts new cert
    if (prev_cert["name"]
            and (prev_cert.get("date") or prev_cert.get("issuer"))
            and not is_date_line(stripped)
            and lower not in EXACT_ISSUERS
            # But only if this line reads like a title (title-case, short)
            and stripped[0].isupper()
            and len(stripped.split()) <= 12
            and not stripped.endswith((",", ";"))
            and not any(kw in lower for kw in [
                "services", "cloud", "studio", "platform", "experience",
                "hands-on", "covered", "including", "practical",
            ])):
        return True

    return False


def _infer_issuer_from_name(name: str) -> Optional[str]:
    """Try to detect the issuer from the certification name."""
    if not name:
        return None
    lower = name.lower()
    for kw in sorted(EXACT_ISSUERS, key=len, reverse=True):
        if kw in lower:
            return ISSUER_NORMALIZE.get(kw, kw.title())
    return None


def _parse_line_into_cert(cert: Dict, stripped: str) -> None:
    """Parse a structured cert line (may contain name | issuer | date)."""
    # Handle credential ID
    cred_m = CREDENTIAL_RE.search(stripped)
    if cred_m:
        cert["credential_id"] = cred_m.group(1)
        stripped = stripped[:cred_m.start()].strip()

    # Handle date prefix "2026—Content"
    date_pfx = DATE_PREFIX_RE.match(stripped)
    if date_pfx:
        year, rest = date_pfx.group(1), date_pfx.group(2).strip()
        if not cert["date"]:
            cert["date"] = year
        stripped = rest

    # Split on pipe/dash separators
    parts = [p.strip() for p in PIPE_SEP_RE.split(stripped) if p.strip()]

    for part in parts:
        part_lower = part.lower()
        years = extract_years(part)

        if years and len(part) < 20:
            # Date/year field
            if not cert["date"]:
                cert["date"] = str(years[-1])
        elif part_lower in EXACT_ISSUERS:
            if not cert["issuer"]:
                cert["issuer"] = ISSUER_NORMALIZE.get(part_lower, part)
        elif any(kw in part_lower for kw in EXACT_ISSUERS) and len(part) < 40:
            match_kw = next((kw for kw in EXACT_ISSUERS if kw in part_lower), None)
            if match_kw and (len(match_kw) / len(part_lower) > 0.4):
                if not cert["issuer"]:
                    cert["issuer"] = ISSUER_NORMALIZE.get(match_kw, part)
            else:
                if not cert["name"]:
                    cert["name"] = part
        else:
            if not cert["name"]:
                cert["name"] = part


def _get_content_lines(raw_lines: List[str]) -> List[str]:
    lines = [l for l in raw_lines if l.strip()]
    if not lines:
        return []
    first_lower = lines[0].strip().lower()
    skip_kw = ["certification","certificate","credential","license",
                "course","training","qualification","accreditation"]
    if any(kw in first_lower for kw in skip_kw) and len(lines[0].strip()) < 50:
        return lines[1:]
    return lines


def extract_certifications(raw_lines: List[str]) -> List[Dict]:
    content_lines = _get_content_lines(raw_lines)
    certs: List[Dict] = []
    current: Optional[Dict] = None
    prev_stripped = ""

    def finalize():
        nonlocal current
        if current and current["name"]:
            if not current["issuer"]:
                current["issuer"] = _infer_issuer_from_name(current["name"])
            certs.append(current)
        current = None

    for raw_line in content_lines:
        # Handle PDF column-merged lines (two certs on one line separated by 2+ spaces)
        sublines = re.split(r"(?<=\S)\s{3,}(?=\S)", raw_line)

        for line in sublines:
            stripped = line.strip()
            if not stripped:
                continue

            has_bullet = bool(BULLET_RE.match(stripped))
            if has_bullet:
                stripped_nb = BULLET_RE.sub("", stripped).strip()
            else:
                stripped_nb = stripped

            # Decide: new cert or continuation?
            if _is_new_cert_line(stripped_nb, current):
                finalize()
                current = _empty_cert()
                current["raw_lines"].append(line)
                _parse_line_into_cert(current, stripped_nb)
            else:
                # Continuation line → append to description or fill missing fields
                if current is None:
                    current = _empty_cert()

                current["raw_lines"].append(line)

                # Try to fill issuer/date if not set yet
                years = extract_years(stripped_nb)
                lower = stripped_nb.lower()
                if years and len(stripped_nb) < 20 and not current["date"]:
                    current["date"] = str(years[-1])
                elif lower in EXACT_ISSUERS and not current["issuer"]:
                    current["issuer"] = ISSUER_NORMALIZE.get(lower, stripped_nb)
                elif any(kw in lower for kw in EXACT_ISSUERS) and len(stripped_nb) < 40 and not current["issuer"]:
                    match_kw = next((kw for kw in EXACT_ISSUERS if kw in lower), None)
                    if match_kw:
                        current["issuer"] = ISSUER_NORMALIZE.get(match_kw, stripped_nb)
                else:
                    # It's a description continuation
                    if current["description"]:
                        current["description"] += " " + stripped_nb
                    else:
                        current["description"] = stripped_nb

            prev_stripped = stripped_nb

    finalize()
    return certs
