from dataclasses import dataclass

import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase


@dataclass
class FaceMatch:
    attendee_id: str
    confidence: float
    ambiguous: bool = False


class FaceMatcher:
    def __init__(self) -> None:
        self.event_id: str | None = None
        self.attendee_ids: list[str] = []
        self.matrix: np.ndarray | None = None

    async def refresh(self, db: AsyncIOMotorDatabase, event_id: str) -> None:
        rows = await db.attendees.find({"event_id": event_id, "face_embedding": {"$type": "array"}}).to_list(None)
        self.event_id = event_id
        self.attendee_ids = [row["id"] for row in rows]
        if not rows:
            self.matrix = None
            return
        matrix = np.asarray([row["face_embedding"] for row in rows], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        self.matrix = matrix / np.clip(norms, 1e-6, None)

    async def match(self, db: AsyncIOMotorDatabase, event_id: str, embedding: list[float], threshold: float = 0.5, margin: float = 0.05) -> FaceMatch | None:
        if self.event_id != event_id or self.matrix is None:
            await self.refresh(db, event_id)
        if self.matrix is None or not self.attendee_ids:
            return None
        vector = np.asarray(embedding, dtype=np.float32)
        vector = vector / max(float(np.linalg.norm(vector)), 1e-6)
        scores = self.matrix @ vector
        order = np.argsort(scores)[::-1]
        best_index = int(order[0])
        best = float(scores[best_index])
        if best < threshold:
            return None
        second = float(scores[int(order[1])]) if len(order) > 1 else -1.0
        return FaceMatch(self.attendee_ids[best_index], best, best - second < margin)


face_matcher = FaceMatcher()
