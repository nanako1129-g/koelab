from pydantic import BaseModel, Field
from typing import List, Literal


class ClassifiedItem(BaseModel):
    source_id: str
    labels: List[Literal["賛成", "反対", "課題", "提案"]]
    themes: List[str] = Field(default_factory=list)
    stance: Literal["賛成", "反対", "中立"]
    summary: str
    quote: str
    confidence: float


class ClassifiedBatch(BaseModel):
    items: List[ClassifiedItem]
