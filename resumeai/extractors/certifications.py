"""
certifications.py — Extract certification entries.

Handles:
  - "AWS Certified Solutions Architect – Amazon | 2023"
  - Bullet-listed certs
  - Cert with credential ID
"""

import re
from enum import Enum
from typing import Dict, List, Optional

from resumeai.extractors.date_utils import parse_date, extract_years, is_date_line

BULLET_RE = re.compile(r"^[\-\*\•\·\◦\▸\►\–\—]\s+")
PIPE_SEP_RE = re.compile(r"\s*[|\-\u2013\u2014/]\s*")
CREDENTIAL_RE = re.compile(r"(?:credential|cert(?:ificate)?|license|id)[:\s#]+([A-Z0-9\-]+)", re.IGNORECASE)
EXPIRY_RE = re.compile(r"(?:expir(?:es|y|ed)|valid(?:\s+until)?|expires)[:\s]+(.+)", re.IGNORECASE)

EXACT_ISSUERS = {
    "amazon", "aws", "google", "microsoft", "azure", "comptia", "cisco",
    "oracle", "ibm", "salesforce", "pmi", "isaca", "isc2", "ec-council",
    "coursera", "udemy", "edx", "nptel", "linkedin", "meta", "mongodb",
    "databricks", "snowflake", "hashicorp", "red hat", "vmware",
    "amazon web services", "ibm skills network", "postman",
    "cfa institute", "garp", "cncf", "iassc", "autodesk"
}

class SegmentType(Enum):
    TITLE = "title"
    ISSUER = "issuer"
    DATE = "date"
    CREDENTIAL_ID = "credential_id"


def extract_certifications(raw_lines: List[str]) -> List[Dict]:
    content_lines = _get_content_lines(raw_lines)
    return _stateful_grouping(content_lines)


def _get_content_lines(raw_lines: List[str]) -> List[str]:
    while raw_lines and not raw_lines[0].strip():
        raw_lines = raw_lines[1:]
    while raw_lines and not raw_lines[-1].strip():
        raw_lines = raw_lines[:-1]
        
    if not raw_lines:
        return []
        
    first_lower = raw_lines[0].strip().lower()
    skip_keywords = [
        "certification", "certificate", "credential", "license",
        "course", "training", "qualification", "accreditation",
    ]
    if any(kw in first_lower for kw in skip_keywords) and len(raw_lines[0].strip()) < 50:
        return raw_lines[1:]
    return raw_lines


def _classify_segment(seg: str) -> SegmentType:
    seg_lower = seg.lower()
    
    # Credential ID
    if CREDENTIAL_RE.search(seg):
        return SegmentType.CREDENTIAL_ID
        
    # Date
    years = extract_years(seg)
    if years and len(seg) < 20:
        return SegmentType.DATE

    # Exact issuer
    if seg_lower in EXACT_ISSUERS:
        return SegmentType.ISSUER

    # Check for embedded issuer names
    kw_hits = [kw for kw in EXACT_ISSUERS if kw in seg_lower]
    if kw_hits:
        match_len = sum(len(kw) for kw in kw_hits)
        # If the issuer keyword dominates the string, it's an issuer
        if match_len / len(seg_lower) > 0.5:
            return SegmentType.ISSUER
            
    return SegmentType.TITLE


def _parse_cert_line(cert: Dict, stripped: str):
    cred_m = CREDENTIAL_RE.search(stripped)
    if cred_m:
        cert["credential_id"] = cred_m.group(1)
        stripped = stripped[:cred_m.start()].strip()

    exp_m = EXPIRY_RE.search(stripped)
    if exp_m:
        cert["expiry"] = parse_date(exp_m.group(1))
        stripped = stripped[:exp_m.start()].strip()

    parts = [p.strip() for p in PIPE_SEP_RE.split(stripped) if p.strip()]
    
    line_has_title = False
    for part in parts:
        seg_type = _classify_segment(part)
        if seg_type == SegmentType.TITLE:
            if cert["name"]:
                if line_has_title:
                    cert["name"] += f" - {part}"
                else:
                    # Should not reach here if _parse_cert_line is only called on is_new lines
                    cert["name"] += f" - {part}"
            else:
                cert["name"] = part
                line_has_title = True
        elif seg_type == SegmentType.ISSUER:
            if not cert["issuer"]:
                cert["issuer"] = part
        elif seg_type == SegmentType.DATE:
            years = extract_years(part)
            if years and not cert["date"]:
                cert["date"] = years[-1]
        elif seg_type == SegmentType.CREDENTIAL_ID:
            cred_m2 = CREDENTIAL_RE.search(part)
            if cred_m2 and not cert["credential_id"]:
                cert["credential_id"] = cred_m2.group(1)

def _stateful_grouping(lines: List[str]) -> List[Dict]:
    certs = []
    current_cert = None
    prev_line_blank = False

    def finalize_cert():
        nonlocal current_cert
        if current_cert and current_cert["name"]:
            certs.append(current_cert)
        current_cert = None

    for raw_line in lines:
        # Split on multiple spaces OR inline bullets/pipes to handle PDF column merging
        sublines = re.split(r"(?<=\S)\s{2,}(?=\S)|\s+(?=[\•\·\◦\▸\►\|]\s+)", raw_line)
        for i, line in enumerate(sublines):
            stripped = line.strip()
            if not stripped:
                if not sublines: # only mark blank if the whole line was blank
                    prev_line_blank = True
                continue

            has_bullet = bool(BULLET_RE.match(stripped))
            has_date = bool(extract_years(stripped))
            has_cred = bool(CREDENTIAL_RE.search(stripped))
            
            has_issuer = False
            parts = [p.strip() for p in PIPE_SEP_RE.split(stripped) if p.strip()]
            for p in parts:
                if p.lower() in EXACT_ISSUERS:
                    has_issuer = True
                    break

            is_new = False
            if has_bullet or prev_line_blank or current_cert is None:
                is_new = True
            elif has_date or has_issuer or has_cred:
                is_new = True
            elif i > 0 and len(stripped) > 5:
                # If it's a separate chunk on the same line (columns), treat as new cert
                is_new = True
            elif current_cert and (current_cert.get("issuer") or current_cert.get("date") or current_cert.get("credential_id")):
                # If the previous cert is already fully formed (has issuer/date/cred), and this line is something else,
                # it's likely a new cert on a new line.
                is_new = True

            if is_new:
                finalize_cert()
                if has_bullet:
                    stripped = BULLET_RE.sub("", stripped).strip()
                
                current_cert = {
                    "name": None, "issuer": None, "date": None, "expiry": None, 
                    "credential_id": None, "raw_lines": []
                }
                _parse_cert_line(current_cert, stripped)
                
            current_cert["raw_lines"].append(line)
            prev_line_blank = False

    finalize_cert()
    
    # Post-process to detect issuer from name if missing
    for cert in certs:
        if cert["name"] and not cert["issuer"]:
            name_lower = cert["name"].lower()
            for kw in EXACT_ISSUERS:
                if kw in name_lower:
                    # special casing to preserve original capitalization if possible, else title()
                    cert["issuer"] = kw.title()
                    if cert["issuer"] == "Aws": cert["issuer"] = "AWS"
                    if cert["issuer"] == "Cncf": cert["issuer"] = "CNCF"
                    if cert["issuer"] == "Garp": cert["issuer"] = "GARP"
                    break
                    
    return certs
