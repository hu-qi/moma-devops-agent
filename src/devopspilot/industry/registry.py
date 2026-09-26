"""In-memory registry for Industry Engineering Packs."""

from __future__ import annotations

from devopspilot.contracts.industry import (
    IndustryEngineeringPack,
    IndustryPackRegistry,
)


class InMemoryIndustryPackRegistry(IndustryPackRegistry):
    """In-memory store for registered Industry Engineering Packs."""

    def __init__(self) -> None:
        self._packs: dict[str, IndustryEngineeringPack] = {}

    def register_pack(self, pack: IndustryEngineeringPack) -> None:
        """Register or update an industry pack."""
        self._packs[pack.pack_id] = pack

    def get_pack(self, pack_id: str) -> IndustryEngineeringPack | None:
        """Retrieve a pack by pack_id."""
        return self._packs.get(pack_id)

    def list_packs(
        self, industry: str | None = None
    ) -> tuple[IndustryEngineeringPack, ...]:
        """List all packs or filter by industry name."""
        if industry is None:
            return tuple(self._packs.values())
        return tuple(
            p for p in self._packs.values() if p.industry.lower() == industry.lower()
        )
