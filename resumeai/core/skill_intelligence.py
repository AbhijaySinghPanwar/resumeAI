"""
core/skill_intelligence.py — Central Skill Intelligence Engine v1.1
Domain-Agnostic Semantic Skill Inference Engine.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, Any, List, Set, Tuple
from functools import lru_cache

from resumeai.matching.schemas import SkillEvidence

class SkillIntelligenceEngine:
    _instance = None
    _ontology = None
    
    # Pre-computed lookups
    _alias_to_canonical = {}
    _canonical_list_sorted = []
    _skill_to_category = {}
    _skill_to_families = {}
    _relationships = []
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SkillIntelligenceEngine, cls).__new__(cls)
            cls._instance._load_ontology()
        return cls._instance

    def _load_ontology(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ontology_path = os.path.join(current_dir, "..", "matching", "skill_ontology.json")
        if not os.path.exists(ontology_path):
            raise FileNotFoundError(f"Ontology not found at {ontology_path}")
            
        with open(ontology_path, "r", encoding="utf-8") as f:
            self._ontology = json.load(f)
            
        self._build_lookups()

    def _build_lookups(self):
        self._alias_to_canonical = {}
        self._skill_to_category = {}
        self._skill_to_families = {}
        self._relationships = self._ontology.get("relationships", [])
        
        # Build categories and aliases
        for cat_name, skills in self._ontology.get("categories", {}).items():
            for canonical, data in skills.items():
                self._alias_to_canonical[canonical.lower()] = canonical
                self._skill_to_category[canonical] = cat_name
                for alias in data.get("aliases", []):
                    self._alias_to_canonical[alias.lower()] = canonical

        # Sort aliases by length for greedy matching
        self._canonical_list_sorted = sorted(
            self._alias_to_canonical.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )
        
        # Build families lookup
        for family_name, skills in self._ontology.get("families", {}).items():
            for skill in skills:
                if skill not in self._skill_to_families:
                    self._skill_to_families[skill] = set()
                self._skill_to_families[skill].add(family_name)

    @lru_cache(maxsize=1024)
    def normalize_skill(self, raw: str) -> str:
        return self._alias_to_canonical.get(raw.strip().lower(), raw.strip())

    def extract_skills_from_text(self, text: str) -> List[str]:
        if not text:
            return []
        text_lower = text.lower()
        found = set()
        consumed_spans = []

        for alias, canonical in self._canonical_list_sorted:
            pattern = r"(?<![a-zA-Z0-9/\-])" + re.escape(alias) + r"(?![a-zA-Z0-9/\-])"
            for m in re.finditer(pattern, text_lower):
                start, end = m.start(), m.end()
                overlaps = any(s < end and start < e for s, e in consumed_spans)
                if not overlaps:
                    found.add(canonical)
                    consumed_spans.append((start, end))

        return sorted(list(found))

    def classify_industry_domain(self, text: str) -> List[str]:
        text_lower = text.lower()
        matched_domains = []
        for domain, keywords in self._ontology.get("industry_domains", {}).items():
            if any(re.search(r"\b" + re.escape(kw) + r"\b", text_lower) for kw in keywords):
                matched_domains.append(domain)
        return matched_domains

    def classify_jd_domain(self, parsed_jd: Any) -> Dict[str, Any]:
        """Classify JD into a primary domain (e.g., Backend Engineer) and return its weights."""
        title = getattr(parsed_jd, "title", "").lower()
        domains = self._ontology.get("domains", {})
        
        # Check by title first
        for domain_name, data in domains.items():
            if domain_name.lower() in title:
                return {"domain": domain_name, "weights": data.get("weights", {}), "boosted_families": data.get("boosted_families", [])}
                
        # Fallback to Software Engineer or default
        return {"domain": "Software Engineer", "weights": domains.get("Software Engineer", {}).get("weights", {}), "boosted_families": domains.get("Software Engineer", {}).get("boosted_families", [])}

    def match_skill(self, jd_skill: str, evidence_map: Dict[str, List[SkillEvidence]]) -> SkillEvidence | None:
        """
        Match JD skill against extracted resume evidence using 5-level priority.
        1. Explicit Match (100-80)
        2. Semantic Ontology Match (95-90)
        3. Technology Family Match (80)
        4. Cross-Skill Reasoning (85)
        """
        jd_norm = self.normalize_skill(jd_skill)
        
        # Level 1: Explicit Match
        if jd_norm in evidence_map:
            # We have direct evidence! Let's aggregate confidence.
            evidences = evidence_map[jd_norm]
            
            best_confidence = max(e.confidence for e in evidences)
            
            # Boost for multiple sources
            if len(evidences) > 1:
                best_confidence = min(100, best_confidence + (len(evidences) * 2))
                
            sources = []
            for e in evidences:
                for s in e.sources:
                    if s not in sources:
                        sources.append(s)
            
            return SkillEvidence(
                skill=jd_skill,
                match_type="Explicit Match",
                confidence=best_confidence,
                reason=f"Explicitly found in {len(sources)} resume section(s).",
                sources=sources[:5] # keep top 5
            )
            
        # Level 2: Semantic Ontology Match
        # Check if the resume has a skill that implies the jd_skill.
        # e.g., JD wants "Cloud Computing", Resume has "AWS". AWS belongs_to Cloud Computing.
        canonical_jd = self._alias_to_canonical.get(jd_norm, jd_skill)
        
        # Find multi-hop semantic parents
        for rel in self._relationships:
            if rel["target"] == canonical_jd:
                source = rel["source"]
                if source in evidence_map:
                    evidences = evidence_map[source]
                    base_conf = max(e.confidence for e in evidences)
                    semantic_conf = min(95, int(base_conf * 0.95)) # Decay
                    
                    sources = []
                    for e in evidences:
                        for s in e.sources:
                            if s not in sources:
                                sources.append(s)
                                
                    return SkillEvidence(
                        skill=jd_skill,
                        match_type="Semantic Match",
                        confidence=semantic_conf,
                        reason=f"Resume contains {source} which {rel['type'].replace('_', ' ')} {canonical_jd}.",
                        sources=sources[:3]
                    )

        # Level 3: Cross-Skill Reasoning (Combinations)
        # E.g. Python + FastAPI + PostgreSQL -> Backend Development
        cross_skill_inferences = {
            "CI/CD": ["Docker", "GitHub Actions", "Jenkins", "Kubernetes", "AWS"],
            "DevOps": ["Docker", "Kubernetes", "AWS", "CI/CD", "Terraform", "Linux"],
            "Backend Development": ["Python", "FastAPI", "Django", "Node.js", "Java", "SQL", "PostgreSQL", "REST APIs"],
            "Frontend Development": ["React", "JavaScript", "TypeScript", "HTML/CSS", "Vue.js", "Angular"],
            "Machine Learning": ["Python", "TensorFlow", "PyTorch", "Scikit-learn", "Pandas", "NumPy"],
            "Data Engineering": ["SQL", "Python", "Apache Spark", "Kafka", "Data Warehousing"],
            "API Design": ["REST APIs", "GraphQL", "FastAPI", "Express.js", "Django"],
        }
        
        if canonical_jd in cross_skill_inferences:
            required_combo = cross_skill_inferences[canonical_jd]
            # Count how many of these exist in the resume
            matches = [s for s in required_combo if s in evidence_map]
            if len(matches) >= 2:
                # Strong inference
                return SkillEvidence(
                    skill=jd_skill,
                    match_type="Cross-Skill Inference",
                    confidence=85 + (len(matches) * 2),
                    reason=f"Inferred because resume combines {', '.join(matches)}.",
                    sources=["Aggregated Experience"]
                )

        # Level 4: Technology Family Match
        jd_families = self._skill_to_families.get(canonical_jd, set())
        for fam in jd_families:
            for resume_skill in evidence_map.keys():
                if fam in self._skill_to_families.get(resume_skill, set()):
                    # They share a family!
                    return SkillEvidence(
                        skill=jd_skill,
                        match_type="Family Match",
                        confidence=80,
                        reason=f"Both {resume_skill} and {canonical_jd} belong to the {fam} family.",
                        sources=evidence_map[resume_skill][0].sources[:1]
                    )

        return None
