"""
resumeai/ontology — single source of truth for skill vocabulary and the
skill relationship graph. See registry.py for the loader/matcher and
schema.py for the JSON's structural contract.
"""
from .registry import get_registry, preload_registry, extract_skills_from_text, normalize_skill

__all__ = ["get_registry", "preload_registry", "extract_skills_from_text", "normalize_skill"]
