import math
import hashlib
import logging
from typing import List, Optional
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """
    Embedding generation provider supporting dual modes:
    1. Online OpenAI / provider embeddings when credentials are configured.
    2. High-performance, deterministic local feature hashing embeddings (384 dimensions)
       for offline test suites and environments without paid external API keys.
    """

    def __init__(self):
        self.settings = get_settings()
        self.dim = self.settings.AI_EMBEDDING_DIMENSION or 384

    async def get_embedding(self, text: str) -> List[float]:
        """Generates a dense unit-norm embedding vector for the input text."""
        # Try OpenAI if configured
        if (
            self.settings.AI_EMBEDDING_PROVIDER in ("auto", "openai")
            and self.settings.OPENAI_API_KEY
        ):
            try:
                return await self._get_openai_embedding(text)
            except Exception as e:
                logger.warning(f"OpenAI embedding call failed, falling back to local deterministic: {e}")

        return self._get_local_embedding(text)

    async def _get_openai_embedding(self, text: str) -> List[float]:
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": text[:8000],
            "model": self.settings.AI_EMBEDDING_MODEL or "text-embedding-3-small",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    def _get_local_embedding(self, text: str) -> List[float]:
        """
        Generates a 384-dimensional deterministic dense vector using
        word tokens + character tri-grams with hashed sign projections.
        Guarantees unit L2 norm so dot-product equals cosine similarity.
        """
        vec = [0.0] * self.dim
        clean_text = text.lower().strip()
        tokens = clean_text.split()

        # Add word tokens
        for token in tokens:
            self._hash_into_vector(token, vec, weight=1.0)
            # Add character tri-grams for subword similarity
            if len(token) >= 4:
                for i in range(len(token) - 2):
                    ngram = token[i:i + 3]
                    self._hash_into_vector(ngram, vec, weight=0.4)

        # Compute Euclidean L2 norm
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0.0:
            vec = [round(x / norm, 6) for x in vec]
        else:
            vec[0] = 1.0

        return vec

    def _hash_into_vector(self, term: str, vec: List[float], weight: float = 1.0) -> None:
        """Projects term hash into vector indices with positive/negative signs."""
        h = int(hashlib.md5(term.encode("utf-8")).hexdigest(), 16)
        idx1 = h % self.dim
        idx2 = (h >> 16) % self.dim
        sign1 = 1.0 if ((h >> 8) & 1) else -1.0
        sign2 = 1.0 if ((h >> 24) & 1) else -1.0

        vec[idx1] += sign1 * weight
        vec[idx2] += sign2 * weight * 0.5
