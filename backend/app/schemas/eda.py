"""EDA insight schemas for the evidence and analysis view."""

from pydantic import BaseModel


class EDAChurnSegment(BaseModel):
    name: str
    n: int
    churn_rate: float
    lift: float


class EDAChurnBySim(BaseModel):
    segments: list[EDAChurnSegment]


class EDAChurnByTenure(BaseModel):
    bands: list[EDAChurnSegment]


class EDAChurnByGeneration(BaseModel):
    generations: list[EDAChurnSegment]


class EDAChurnSimGeneration(BaseModel):
    segments: list[EDAChurnSegment]


class EDAVolteImpact(BaseModel):
    segments: list[EDAChurnSegment]


class EDAEvidenceLayer(BaseModel):
    layer: str
    supported: bool
    detail: str


class EDAQuestionEvidence(BaseModel):
    question_id: str
    question: str
    answer: str
    confidence: str
    confidence_basis: str
    evidence_layers: list[EDAEvidenceLayer]
    business_implication: str
    caveat: str


class EDANarrative(BaseModel):
    key: str
    bullets: list[str]


class EDAInsightSummary(BaseModel):
    label: str
    value: str
    detail: str


class EDAExecutiveSummary(BaseModel):
    generated_at_utc: str
    n_subscribers: int
    mean_calibrated_risk: float
    narratives: list[EDANarrative]


class EDAInsightCard(BaseModel):
    title: str
    value: str
    insight: str
    evidence_level: str


class EDAResponse(BaseModel):
    generated_at_utc: str
    n_subscribers: int
    churn_rate: float
    churn_by_sim: EDAChurnBySim | None = None
    churn_by_tenure: EDAChurnByTenure | None = None
    churn_by_generation: EDAChurnByGeneration | None = None
    churn_by_sim_and_generation: EDAChurnSimGeneration | None = None
    volte_impact: EDAVolteImpact | None = None
    insight_cards: list[EDAInsightCard]
    executive_narratives: list[EDANarrative]
    retention_simulation: dict | None = None
    top_shap_features: list[str] = []
