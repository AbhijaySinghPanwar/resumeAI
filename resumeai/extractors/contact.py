"""
contact.py — Extract contact information from the contact section block.
"""

import re
from typing import Dict, List, Optional


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s\-.]?)?"   # country code
    r"(?:\(?\d{2,4}\)?[\s\-.]?)?"  # area code
    r"\d{3,4}[\s\-.]?\d{3,5}(?!\d)"    # main number
)
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in/)?[A-Za-z0-9\-]+|linkedin\s*(?:profile)?\s*:\s*[A-Za-z0-9\-]+", re.IGNORECASE)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9\-]+", re.IGNORECASE)
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:[a-zA-Z0-9\-]+\.)+(?:com|org|net|io|dev|me|co)(?:/[^\s,\|]*)?", re.IGNORECASE)


def extract_contact(raw_lines: List[str]) -> Dict:
    """
    Extract contact fields from raw lines of the contact section.
    Returns a dict matching the schema contact object.
    """
    text = " ".join(raw_lines)

    email = _first_match(EMAIL_RE, text)
    phone = _extract_phone(text)
    linkedin_match = _first_match(LINKEDIN_RE, text)
    if linkedin_match:
        if "linkedin.com" in linkedin_match.lower():
            linkedin = linkedin_match
        else:
            user = linkedin_match.split(":")[-1].strip()
            linkedin = f"linkedin.com/in/{user}"
    else:
        linkedin = None
        
    github = _first_match(GITHUB_RE, text)

    # Find other URLs (excluding linkedin, github, and email domains)
    other_links = []
    for url in URL_RE.findall(text):
        if "linkedin" not in url.lower() and "github" not in url.lower():
            if email and email.split("@")[-1].lower() in url.lower():
                continue
            other_links.append(url)

    # Name: usually the first non-empty, non-email, non-phone line
    name = _extract_name(raw_lines)

    # Location: look for city/state/country patterns
    location = _extract_location(raw_lines)

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": f"https://{linkedin}" if linkedin and not linkedin.startswith("http") else linkedin,
        "github": f"https://{github}" if github and not github.startswith("http") else github,
        "portfolio": _extract_portfolio(text, linkedin, github, email),
        "other_links": other_links,
    }


def _first_match_group(pattern: re.Pattern, text: str) -> Optional[str]:
    m = pattern.search(text)
    if m:
        return m.group(1) if m.groups() else m.group(0)
    return None

def _first_match(pattern: re.Pattern, text: str) -> Optional[str]:
    m = pattern.search(text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> Optional[str]:
    for m in PHONE_RE.finditer(text):
        candidate = m.group(0).strip()
        # Must have at least 7 digits
        digits = re.sub(r"\D", "", candidate)
        
        # Prevent matching YYYY-YYYY date ranges
        if len(digits) == 8 and re.match(r"^(?:19|20)\d{2}[-.\s]*(?:19|20)\d{2}$", candidate):
            continue
            
        if 7 <= len(digits) <= 15:
            return candidate
    return None


def _extract_name(raw_lines: List[str]) -> Optional[str]:
    """Name is typically the first substantial non-contact-detail line."""
    skip_patterns = [EMAIL_RE, PHONE_RE, LINKEDIN_RE, GITHUB_RE, URL_RE]
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip lines that are purely contact details
        is_contact_detail = any(p.search(stripped) for p in skip_patterns)
        if is_contact_detail:
            continue
        # Skip lines that look like addresses (contain digits + words)
        if re.match(r"^\d+\s+\w+", stripped):
            continue
        # Short line with mostly letters — likely a name
        if 2 <= len(stripped.split()) <= 5 and re.match(r"^[A-Za-z\s\.\-\']+$", stripped):
            return stripped
    return None


def _extract_location(raw_lines: List[str]) -> Optional[str]:
    """Look for city, state / country pattern."""
    location_re = re.compile(
        r"[A-Za-z\s]+,\s*[A-Za-z\s]+"   # "City, State" or "City, Country"
    )
    for line in raw_lines:
        m = location_re.search(line.strip())
        if m:
            candidate = m.group(0).strip()
            # Avoid matching email domains
            if "@" not in candidate and len(candidate) < 60:
                return candidate
    return None


def _extract_portfolio(text: str, linkedin: Optional[str], github: Optional[str], email: Optional[str]) -> Optional[str]:
    """Find portfolio URL (not linkedin or github)."""
    for url in URL_RE.findall(text):
        url_lower = url.lower()
        if "linkedin" in url_lower or "github" in url_lower:
            continue
        if email and email.split("@")[-1].lower() in url_lower:
            continue
        if any(domain in url_lower for domain in [".io", ".dev", ".me", ".com", ".net", ".co"]):
            return url
    return None
