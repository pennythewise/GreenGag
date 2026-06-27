"""Per-pillar routing via local MiniLM cosine similarity (top-K always)."""

from __future__ import annotations

import numpy as np

from ..llm.models import PillarRetrievalStatus, RetrievedChunk
from .pillar_queries import PILLAR_QUERIES, PILLARS
from ...store.document_store import DocumentStore
from config import settings
from models.schemas import EsgPillar
from providers.local_embedder import encode_texts_async


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


class RagRetriever:
    """Route chunks to pillars using sentence-transformers/all-MiniLM-L6-v2."""

    def __init__(self, store: DocumentStore | None = None) -> None:
        self.store = store or DocumentStore()
        self.chunks_per_pillar = settings.rag_chunks_per_pillar

    async def retrieve(
        self, document_id: str
    ) -> tuple[dict[EsgPillar, list[RetrievedChunk]], dict[EsgPillar, PillarRetrievalStatus]]:
        rows = self.store.list_chunks(document_id)
        pillar_chunks: dict[EsgPillar, list[RetrievedChunk]] = {p: [] for p in PILLARS}
        pillar_status: dict[EsgPillar, PillarRetrievalStatus] = {}

        if not rows:
            for pillar in PILLARS:
                pillar_status[pillar] = PillarRetrievalStatus(
                    status="insufficient_text_retrieved",
                    best_score=0.0,
                    chunks_selected=0,
                )
            return pillar_chunks, pillar_status

        texts = [str(r["content"]) for r in rows]
        chunk_vectors = await encode_texts_async(texts)
        query_vectors = await encode_texts_async([PILLAR_QUERIES[p] for p in PILLARS])

        for idx, pillar in enumerate(PILLARS):
            query_vec = query_vectors[idx]
            scored: list[tuple[float, dict[str, float], int]] = []

            for row_idx, row in enumerate(rows):
                score = _cosine(query_vec, chunk_vectors[row_idx])
                pillar_scores = {
                    p: _cosine(query_vectors[i], chunk_vectors[row_idx])
                    for i, p in enumerate(PILLARS)
                }
                scored.append((score, pillar_scores, row_idx))

            scored.sort(key=lambda item: item[0], reverse=True)
            top = scored[: self.chunks_per_pillar]
            best_score = top[0][0] if top else 0.0

            chunks: list[RetrievedChunk] = []
            for score, pillar_scores, row_idx in top:
                row = rows[row_idx]
                chunks.append(
                    RetrievedChunk(
                        id=str(row["id"]),
                        content=str(row["content"]),
                        page=row.get("page"),
                        section_heading=row.get("section_heading"),
                        pillar_hint=row.get("pillar_hint"),
                        vector_score=score,
                        hybrid_score=score,
                        matched_pillar=pillar,
                        pillar_scores=pillar_scores,
                    )
                )

            pillar_chunks[pillar] = chunks
            pillar_status[pillar] = PillarRetrievalStatus(
                status="ok" if chunks else "insufficient_text_retrieved",
                best_score=best_score,
                chunks_selected=len(chunks),
            )

        return pillar_chunks, pillar_status
