"""OpenAI embedding provider."""

from __future__ import annotations

from openai import AsyncOpenAI

from greengag.config import settings


class OpenAIEmbedder:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for embeddings.")
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # OpenAI allows large batches; keep moderate for reliability.
        batch_size = 64
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = await self._client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimensions,
            )
            vectors.extend(item.embedding for item in resp.data)
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]
