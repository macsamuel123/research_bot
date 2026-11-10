"""Integer-cent run cost (INV-1). Only int arithmetic and a single ceiling division."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings

MTOK = 1_000_000
#: A search is priced per 1K searches; scaling by 1K more puts it on the per-MTok scale.
SEARCH_SCALE = 1_000


@dataclass(frozen=True)
class Prices:
    input_cents_per_mtok: int
    output_cents_per_mtok: int
    search_cents_per_1k: int

    @classmethod
    def from_settings(cls, settings: Settings) -> Prices:
        return cls(
            input_cents_per_mtok=settings.price_input_cents_per_mtok,
            output_cents_per_mtok=settings.price_output_cents_per_mtok,
            search_cents_per_1k=settings.price_search_cents_per_1k,
        )


def compute(input_tokens: int, output_tokens: int, search_calls: int, prices: Prices) -> int:
    """Total cost in whole cents, rounded up.

    Everything is scaled to "cent-millionths": tokens are priced per million, and a search
    priced per thousand is scaled by another thousand. One ceiling division gives cents.
    """
    numerator = (
        input_tokens * prices.input_cents_per_mtok
        + output_tokens * prices.output_cents_per_mtok
        + search_calls * prices.search_cents_per_1k * SEARCH_SCALE
    )
    return -(-numerator // MTOK)
