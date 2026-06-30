"""Local sentence-transformer embeddings for deterministic pillar routing."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import numpy as np

from config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None
_model_name: str | None = None


def _get_model() -> SentenceTransformer:
    global _model, _model_name
    target = settings.rag_pillar_routing_model
    if _model is None or _model_name != target:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(target)
        _model_name = target
    return _model


def encode_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    vectors = _get_model().encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)


def encode_text(text: str) -> np.ndarray:
    return encode_texts([text])[0]


async def encode_texts_async(texts: list[str]) -> np.ndarray:
    return await asyncio.to_thread(encode_texts, texts)


async def encode_text_async(text: str) -> np.ndarray:
    return await encode_texts_async([text])
