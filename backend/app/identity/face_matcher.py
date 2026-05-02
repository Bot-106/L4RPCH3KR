import base64
import html
import logging
import re
from dataclasses import dataclass

import httpx
import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase

log = logging.getLogger(__name__)

PROFILE_IMAGE_RE = re.compile(r"https://media\.licdn\.com/[^\s\"'<>]+profile-displayphoto[^\s\"'<>]+")
OG_IMAGE_RE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)


@dataclass
class FaceMatch:
    attendee_id: str
    confidence: float
    method: str = "profile_picture_similarity"
    ambiguous: bool = False


class FaceMatcher:
    def __init__(self) -> None:
        self.event_id: str | None = None
        self.attendee_ids: list[str] = []
        self.matrix: np.ndarray | None = None
        self.missing_profile_images = 0

    def _embedding_from_image_bytes(self, image: bytes) -> list[float] | None:
        try:
            import cv2

            raw = np.frombuffer(image, dtype=np.uint8)
            decoded = cv2.imdecode(raw, cv2.IMREAD_COLOR)
            if decoded is None:
                return None
            gray = cv2.cvtColor(decoded, cv2.COLOR_BGR2GRAY)
            detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
            if len(faces):
                x, y, w, h = max(faces, key=lambda face: face[2] * face[3])
                pad = int(max(w, h) * 0.2)
                y0 = max(y - pad, 0)
                y1 = min(y + h + pad, decoded.shape[0])
                x0 = max(x - pad, 0)
                x1 = min(x + w + pad, decoded.shape[1])
                face = decoded[y0:y1, x0:x1]
            else:
                height, width = decoded.shape[:2]
                side = min(height, width)
                y0 = (height - side) // 2
                x0 = (width - side) // 2
                face = decoded[y0 : y0 + side, x0 : x0 + side]

            face = cv2.resize(face, (64, 64), interpolation=cv2.INTER_AREA)
            face_gray = cv2.equalizeHist(cv2.cvtColor(face, cv2.COLOR_BGR2GRAY))
            pixels = cv2.resize(face_gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32).reshape(-1) / 255.0
            hsv = cv2.cvtColor(face, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256]).astype(np.float32).reshape(-1)
            hist = hist / max(float(hist.sum()), 1e-6)
            vector = np.concatenate([pixels, hist])
            vector = vector - float(vector.mean())
            vector = vector / max(float(np.linalg.norm(vector)), 1e-6)
            return vector.astype(np.float32).tolist()
        except Exception as exc:
            log.warning("face: image embedding failed: %s", exc)
            return None

    def embedding_from_base64(self, image_b64: str | None) -> list[float] | None:
        if not image_b64:
            return None
        try:
            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            return self._embedding_from_image_bytes(base64.b64decode(image_b64))
        except Exception as exc:
            log.warning("face: invalid base64 image: %s", exc)
            return None

    async def _embedding_from_url(self, url: str) -> list[float] | None:
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 L4RPCH3KR demo profile-image resolver"})
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "image" not in content_type and not url.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp")):
                log.info("face: profile url is not a direct image: %s", url)
                return None
            return self._embedding_from_image_bytes(response.content)
        except Exception as exc:
            log.warning("face: failed to fetch profile image %s: %s", url, exc)
            return None

    def _best_linkedin_image_from_html(self, body: str) -> str | None:
        body = html.unescape(body)
        urls = PROFILE_IMAGE_RE.findall(body)
        og_match = OG_IMAGE_RE.search(body)
        if og_match:
            urls.append(html.unescape(og_match.group(1)))
        if not urls:
            return None

        def score(url: str) -> int:
            match = re.search(r"(?:scale|crop)_(\d+)_(\d+)", url)
            if match:
                return int(match.group(1)) * int(match.group(2))
            return 0

        return max(urls, key=score)

    async def _profile_image_url_from_linkedin_page(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 L4RPCH3KR demo profile-image resolver"})
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type:
                return None
            return self._best_linkedin_image_from_html(response.text)
        except Exception as exc:
            log.warning("face: failed to resolve LinkedIn profile image %s: %s", url, exc)
            return None

    def _profile_page_url(self, row: dict) -> str | None:
        socials = row.get("socials") or {}
        url = row.get("linkedin_url") or socials.get("linkedin")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return url
        return None

    async def refresh(self, db: AsyncIOMotorDatabase, event_id: str) -> None:
        rows = await db.attendees.find({"event_id": event_id, "deleted_at": None}).to_list(None)
        self.event_id = event_id
        self.attendee_ids = []
        self.missing_profile_images = 0
        embeddings: list[list[float]] = []
        for row in rows:
            embedding = row.get("profile_image_embedding")
            if not embedding:
                image_url = row.get("profile_pic_url") or row.get("photo_url")
                if not image_url:
                    linkedin_url = self._profile_page_url(row)
                    if linkedin_url:
                        image_url = await self._profile_image_url_from_linkedin_page(linkedin_url)
                        if image_url:
                            await db.attendees.update_one({"id": row["id"]}, {"$set": {"profile_pic_url": image_url, "photo_url": image_url}})
                if image_url:
                    embedding = await self._embedding_from_url(image_url)
                    if embedding:
                        await db.attendees.update_one({"id": row["id"]}, {"$set": {"profile_image_embedding": embedding, "profile_image_source_url": image_url}})
                else:
                    self.missing_profile_images += 1
            if embedding:
                self.attendee_ids.append(row["id"])
                embeddings.append(embedding)
        if not embeddings:
            self.matrix = None
            return
        matrix = np.asarray(embeddings, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        self.matrix = matrix / np.clip(norms, 1e-6, None)

    async def match(self, db: AsyncIOMotorDatabase, event_id: str, embedding: list[float], threshold: float = 0.35, margin: float = 0.03) -> FaceMatch | None:
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
