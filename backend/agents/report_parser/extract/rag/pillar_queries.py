"""Fixed pillar query strings for text-first RAG retrieval."""

from __future__ import annotations

from models.schemas import EsgPillar

PILLAR_QUERIES: dict[EsgPillar, str] = {
    "environment": (
        "Environmental sustainability claims: carbon emissions reduction targets, "
        "net zero commitments, renewable energy usage, energy efficiency, water "
        "conservation, waste reduction and recycling, biodiversity protection, "
        "green building certifications, low-carbon materials, climate action plans."
    ),
    "social": (
        "Social responsibility claims: employee health and safety, worker welfare, "
        "diversity equity and inclusion, community engagement, human rights, "
        "training and development, local employment, stakeholder relations, "
        "supply chain labor standards."
    ),
    "governance": (
        "Governance and ethics claims: board composition and independence, "
        "anti-corruption policies, compliance and audit practices, risk management, "
        "transparency and disclosure, whistleblower protection, executive "
        "compensation linked to ESG, regulatory compliance."
    ),
}

PILLARS: tuple[EsgPillar, ...] = ("environment", "social", "governance")
