"""Per-pillar vector retrieval with hybrid pillar_hint boost."""

from __future__ import annotations

from greengag.config import settings
from greengag.models.extraction import PillarRetrievalStatus, RetrievedChunk
from greengag.models.schemas import EsgPillar
from greengag.providers.embeddings import OpenAIEmbedder
from greengag.providers.supabase_store import SupabaseStore
from greengag.services.rag.pillar_queries import PILLAR_QUERIES, PILLARS


def _pillar_boost(chunk_pillar: str | None, query_pillar: EsgPillar) -> float:
    if chunk_pillar == query_pillar:
        return 1.0
    if chunk_pillar is None:
        return 0.85
    return 0.5


class RagRetriever:
    def __init__(
        self,
        store: SupabaseStore | None = None,
        embedder: OpenAIEmbedder | None = None,
    ) -> None:
        self.store = store or SupabaseStore()
        self.embedder = embedder or OpenAIEmbedder()
        self.threshold = settings.rag_similarity_threshold
        self.top_k = settings.rag_top_k_per_pillar
        self.max_chunks = settings.rag_max_chunks_to_llm

    async def retrieve(
        self, document_id: str
    ) -> tuple[list[RetrievedChunk], dict[EsgPillar, PillarRetrievalStatus]]:
        selected: dict[str, RetrievedChunk] = {}
        pillar_status: dict[EsgPillar, PillarRetrievalStatus] = {}

        for pillar in PILLARS:
            query = PILLAR_QUERIES[pillar]
            embedding = await self.embedder.embed_query(query)
            rows = self.store.match_chunks(
                document_id, embedding, pillar, self.top_k
            )
            best_score = max(
                (float(r.get("vector_score", 0)) for r in rows), default=0.0
            )

            if best_score < self.threshold:
                pillar_status[pillar] = PillarRetrievalStatus(
                    status="insufficient_text_retrieved",
                    best_score=best_score,
                    chunks_selected=0,
                )
                continue

            count = 0
            for row in rows:
                vector_score = float(row.get("vector_score", 0))
                if vector_score < self.threshold:
                    continue
                hint = row.get("pillar_hint")
                hybrid = vector_score * _pillar_boost(hint, pillar)
                chunk_id = str(row["id"])
                candidate = RetrievedChunk(
                    id=chunk_id,
                    content=row["content"],
                    page=row.get("page"),
                    section_heading=row.get("section_heading"),
                    pillar_hint=hint,
                    vector_score=vector_score,
                    hybrid_score=hybrid,
                    matched_pillar=pillar,
                )
                existing = selected.get(chunk_id)
                if existing is None or candidate.hybrid_score > existing.hybrid_score:
                    selected[chunk_id] = candidate
                count += 1

            pillar_status[pillar] = PillarRetrievalStatus(
                status="ok",
                best_score=best_score,
                chunks_selected=count,
            )

        ranked = sorted(selected.values(), key=lambda c: c.hybrid_score, reverse=True)
        return ranked[: self.max_chunks], pillar_status
