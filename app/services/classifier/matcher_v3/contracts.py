from __future__ import annotations

from dataclasses import dataclass, field

from app.services.classifier.matching_runtime import CompiledProductMatcher
from app.services.classifier.models import SubtypeCandidate


@dataclass(slots=True)
class CandidateEvidence:
    matcher: CompiledProductMatcher
    shortlist_score: int = 0
    shortlist_reasons: tuple[str, ...] = ()
    candidate: SubtypeCandidate | None = None


@dataclass(slots=True)
class MatcherPhaseSnapshot:
    retrieval: list[CandidateEvidence] = field(default_factory=list)
    candidate_features: list[CandidateEvidence] = field(default_factory=list)
    scoring: list[SubtypeCandidate] = field(default_factory=list)
    confusable_rerank: list[SubtypeCandidate] = field(default_factory=list)
    stop_policy_reason: str | None = None
    audit_notes: list[str] = field(default_factory=list)
