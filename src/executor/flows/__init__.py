"""Flow sub-package — wave-1 checkout flows (catalog v2).

Each flow module exposes a coroutine ``run(page, config, env, run_id,
profile_id) -> FlowResult``. The runner dispatches via the FLOW_REGISTRY
(never via if/else on flow name — invariant #2).
"""

from src.executor.flows import checkout_card_declined, checkout_full

__all__ = ["checkout_full", "checkout_card_declined"]
