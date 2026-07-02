"""
resumeai/matching/eval_threshold.py — Evaluate the ONNX semantic-similarity
threshold used as the last-resort match tier in gap_analyzer.generate_skill_gap.

Per architecture_review.md §2.3, this replaces a guessed constant with a
measured one:
  1. Build a labeled (jd_skill, resume_skill, is_match) dataset, stratified
     by how the pair *should* resolve (exact/alias, sibling, hierarchical,
     unrelated) so the sweep reflects the mix of cases the embedding tier
     actually has to handle in production.
  2. IMPORTANT: only evaluate pairs that would actually reach the embedding
     stage in production -- i.e., pairs the exact/alias/relationship-graph
     tiers do NOT already resolve. Mixing in already-resolved pairs would
     make the threshold look better than it performs on the hard cases it's
     meant for.
  3. Sweep thresholds, compute precision/recall/F1/F2, report the winner.
  4. Runs against whichever backend is configured (ONNX by default) via
     embedding_engine's dispatch -- so results reflect the deployed model,
     not an assumption carried over from the PyTorch path.

Usage:
    python -m resumeai.matching.eval_threshold

The labeled set below is a starting point (covers the relation-type
categories called out in the audit/review). Replace/extend it with labeled
pairs mined from real traffic (server_logs*.txt) before trusting the exact
number in production -- see the note at the bottom of this file.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Tuple

from resumeai.matching.gap_analyzer import _registry, _RELATIONSHIP_MATCH_THRESHOLD


@dataclass
class LabeledPair:
    jd_skill: str
    resume_skill: str
    is_match: bool
    category: str  # for stratified reporting only


# ── Labeled evaluation set ──────────────────────────────────────────────────
# Deliberately excludes pairs that exact/alias matching already resolves
# (e.g. "Python"/"python") -- those never reach the embedding tier in
# production, so scoring them here would inflate the apparent performance
# of whatever threshold we pick.
LABELED_PAIRS: List[LabeledPair] = [
    # ── sibling / hierarchical pairs the relationship graph already resolves
    #    (included here to confirm they're EXCLUDED from the embedding-only
    #    evaluation below, not to score the embedding path on them) ─────────
    # (handled separately -- see filtering step)

    # ── genuinely hard cases: related concepts with no explicit ontology edge,
    #    where the embedding tier is the only thing that CAN catch them ──────
    LabeledPair("Data Visualization", "Tableau", True, "semantic-related"),
    LabeledPair("Data Visualization", "Matplotlib", True, "semantic-related"),
    LabeledPair("Container Orchestration", "Kubernetes", True, "semantic-related"),
    LabeledPair("Version Control", "Git", True, "semantic-related"),
    LabeledPair("Frontend Development", "React", True, "semantic-related"),
    LabeledPair("Backend Development", "Express.js", True, "semantic-related"),
    LabeledPair("Natural Language Processing", "NLP", True, "semantic-related"),
    LabeledPair("Message Queue", "Apache Kafka", True, "semantic-related"),
    LabeledPair("Object Storage", "S3", True, "semantic-related"),
    LabeledPair("Serverless Computing", "AWS Lambda", True, "semantic-related"),

    # ── unrelated pairs (should NOT match at any reasonable threshold) ──────
    LabeledPair("Python", "Figma", False, "unrelated"),
    LabeledPair("JWT", "Tableau", False, "unrelated"),
    LabeledPair("Kubernetes", "Photoshop", False, "unrelated"),
    LabeledPair("React", "PostgreSQL", False, "unrelated"),
    LabeledPair("Machine Learning", "HTML", False, "unrelated"),
    LabeledPair("CRUD", "Figma", False, "unrelated"),
    LabeledPair("Data Visualization", "Kubernetes", False, "unrelated"),
    LabeledPair("Authentication", "Photoshop", False, "unrelated"),
    LabeledPair("Real-time Systems", "PowerPoint", False, "unrelated"),
    LabeledPair("IoT", "Tableau", False, "unrelated"),

    # ── near-miss / plausible-but-wrong pairs (precision stress test) ───────
    LabeledPair("DevOps", "Photoshop", False, "near-miss"),
    LabeledPair("Machine Learning", "Excel", False, "near-miss"),
    LabeledPair("System Design", "Figma", False, "near-miss"),
]


def _filter_to_embedding_only_pairs(pairs: List[LabeledPair]) -> List[LabeledPair]:
    """Drop any pair the exact/alias/relationship-graph tiers already
    resolve -- those never reach the embedding stage in production."""
    kept = []
    for p in pairs:
        jd_canon = _registry.normalize_skill(p.jd_skill)
        rs_canon = _registry.normalize_skill(p.resume_skill)
        if jd_canon == rs_canon:
            continue  # exact/alias match, not an embedding-stage case
        hit = _registry.closure_for(rs_canon).get(jd_canon)
        if hit and hit[0] >= _RELATIONSHIP_MATCH_THRESHOLD:
            continue  # relationship graph already resolves this
        kept.append(p)
    return kept


def sweep_thresholds(pairs: List[LabeledPair], thresholds: List[float]) -> List[dict]:
    from resumeai.matching.embedding_engine import is_available, batch_encode_with_cache, cosine_similarity_matrix

    if not is_available():
        print("Embedding backend not available in this environment -- cannot run eval.", file=sys.stderr)
        return []

    cache: dict = {}
    jd_vecs = batch_encode_with_cache([p.jd_skill for p in pairs], cache)
    rs_vecs = batch_encode_with_cache([p.resume_skill for p in pairs], cache)

    sims = []
    for i in range(len(pairs)):
        sim_row = cosine_similarity_matrix(jd_vecs[i], rs_vecs[i:i + 1])
        sims.append(float(sim_row[0][0]))

    results = []
    for t in thresholds:
        tp = fp = tn = fn = 0
        for p, sim in zip(pairs, sims):
            predicted = sim >= t
            if predicted and p.is_match:
                tp += 1
            elif predicted and not p.is_match:
                fp += 1
            elif not predicted and p.is_match:
                fn += 1
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        f2 = 5 * precision * recall / (4 * precision + recall) if (4 * precision + recall) else 0.0
        results.append({
            "threshold": t, "precision": precision, "recall": recall,
            "f1": f1, "f2": f2, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        })
    return results


def main():
    pairs = _filter_to_embedding_only_pairs(LABELED_PAIRS)
    print(f"Evaluating {len(pairs)} embedding-stage pairs "
          f"(of {len(LABELED_PAIRS)} total labeled pairs; the rest are "
          f"already resolved by exact/alias/relationship-graph matching).\n")

    thresholds = [round(0.50 + 0.05 * i, 2) for i in range(8)]  # 0.50 .. 0.85
    results = sweep_thresholds(pairs, thresholds)
    if not results:
        return

    print(f"{'thresh':>7} {'prec':>6} {'recall':>7} {'f1':>6} {'f2':>6}  tp fp tn fn")
    best_f1, best_f2 = None, None
    for r in results:
        print(f"{r['threshold']:>7.2f} {r['precision']:>6.2f} {r['recall']:>7.2f} "
              f"{r['f1']:>6.2f} {r['f2']:>6.2f}  {r['tp']:>2} {r['fp']:>2} {r['tn']:>2} {r['fn']:>2}")
        if best_f1 is None or r["f1"] > best_f1["f1"]:
            best_f1 = r
        if best_f2 is None or r["f2"] > best_f2["f2"]:
            best_f2 = r

    print(f"\nBest by F1 (balanced): threshold={best_f1['threshold']:.2f} "
          f"(precision={best_f1['precision']:.2f}, recall={best_f1['recall']:.2f})")
    print(f"Best by F2 (recall-weighted, recommended for ATS -- missing a real "
          f"match costs the candidate more than an occasional over-credit): "
          f"threshold={best_f2['threshold']:.2f} "
          f"(precision={best_f2['precision']:.2f}, recall={best_f2['recall']:.2f})")


if __name__ == "__main__":
    main()

# ── Before trusting this in production ──────────────────────────────────────
# This dataset is a stratified starting point, not a substitute for labels
# drawn from real traffic. Recommended next step: mine server_logs*.txt for
# (jd_skill, resume_skill) pairs that fell through to the embedding tier,
# manually label a sample (~100-150), and re-run this sweep against that
# set before changing SKILL_SEMANTIC_THRESHOLD in gap_analyzer.py. Re-run
# whenever the ontology's relationship-graph coverage changes (it changes
# which pairs even reach this stage) or the embedding model/pooling code
# changes.
