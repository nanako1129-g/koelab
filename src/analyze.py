from typing import List, Dict
from src.llm_gemini import classify_with_gemini
from src.schemas import ClassifiedBatch


def classify_records(records: List[Dict], batch_size: int = 10) -> List[Dict]:
    all_items = []
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            raw = classify_with_gemini(batch)
            validated = ClassifiedBatch(items=raw)
            all_items.extend([item.model_dump() for item in validated.items])
        except Exception as e:
            print(f"Batch {i}~{i+len(batch)} failed: {e}")
            raise
    return all_items
