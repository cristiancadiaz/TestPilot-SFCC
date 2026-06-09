"""Flow sub-package — wave-1 checkout flows (catalog v2).

Each flow module exposes a coroutine ``run(page, config, env, run_id,
profile_id) -> FlowResult``. The runner dispatches via the FLOW_REGISTRY
(never via if/else on flow name — invariant #2).
"""

from src.executor.flows import (
    browse_discounted_products,
    cart_review,
    checkout_card_declined,
    checkout_full,
    pdp_validation,
    search_and_filter,
)

__all__ = [
    "checkout_full",
    "checkout_card_declined",
    "search_and_filter",
    "browse_discounted_products",
    "pdp_validation",
    "cart_review",
]
