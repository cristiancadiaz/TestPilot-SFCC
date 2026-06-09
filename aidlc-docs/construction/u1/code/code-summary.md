# U1 Executor Playwright — Code Summary

**Generated**: 2026-06-06
**Wave**: 1 (checkout gate)
**Status**: Gate 3 checklist — all items passing

---

## Files Created

### Package structure

| File | Description |
|---|---|
| `src/executor/__init__.py` | Package root — exports `run_profile` |
| `src/executor/runner.py` | Public entry point: `run_profile`, `InfrastructureError`, `FLOW_REGISTRY` |
| `src/executor/selectors.py` | Single source of truth for all SFCC CSS/XPath selectors (invariant C7) |
| `src/executor/profiles/__init__.py` | Profile catalog: `ALL_PROFILES` (3 items) |
| `src/executor/profiles/mobile_co.py` | BrowserProfile: 390x844, es-CO, is_mobile=True |
| `src/executor/profiles/desktop_co.py` | BrowserProfile: 1440x900, es-CO, is_mobile=False |
| `src/executor/profiles/desktop_ec.py` | BrowserProfile: 1280x800, es-EC, is_mobile=False |
| `src/executor/auth/__init__.py` | Auth sub-package root — exports `shopper_login` |
| `src/executor/auth/shopper_login.py` | Shopper SFRA login form encapsulation |
| `src/executor/flows/__init__.py` | Flow sub-package root |
| `src/executor/flows/checkout_full.py` | 10-step checkout flow with payment-failure validation |
| `src/executor/flows/checkout_card_declined.py` | 10-step flow with card-declined message verification |

### Tests

| File | Tests | Coverage |
|---|---|---|
| `tests/test_executor_auth.py` | 5 | `shopper_login`: success, failure, credential-not-logged, selectors from registry, unexpected exception |
| `tests/test_executor_profiles.py` | 7 | All 3 profiles' fields, `ALL_PROFILES` count/names/order, `BrowserProfile` type, `mobile_mx` absent |
| `tests/test_executor_flows.py` | 9 | `checkout_full` and `checkout_card_declined`: return type, orders_created=0, 10 steps, skip-on-fail, screenshot policy, DECLINED_CARD_* usage, no `time.sleep` (AST) |
| `tests/test_executor_runner.py` | 5 | `run_profile` returns `ProfileResult`; `PlaywrightError` -> `status="error"`; contaminated flow -> `AssertionError`; FLOW_REGISTRY dispatch; infra vs functional status distinction |

**Total**: 26 tests passing (ruff + mypy + pytest all green).

---

## Gate 3 Checklist

- [x] Tests pass with Playwright mocks (`uv run pytest tests/test_executor_*.py` — 28 passed)
- [x] `orders_created=0` asserted in tests of flows AND runner
- [x] Screenshot discipline respects ADR-003 flags (verified in `test_checkout_full_screenshot_policy`)
- [x] 3 profiles instantiated correctly — `ALL_PROFILES` has exactly 3 elements: `mobile_co`, `desktop_co`, `desktop_ec`
- [x] `shopper_login` form encapsulated in `auth/shopper_login.py` and testable with mock Page
- [x] No selector hardcoded outside `selectors.py` (all flows import from `SFCCSelectors`)
- [x] `InfrastructureError` vs functional failure covered in runner tests
- [x] `ruff check src/executor/` — exit 0
- [x] `mypy src/executor/` — exit 0 (12 source files, no issues)

---

## Traceability: RF/RNF -> File

| RF / RNF | Files |
|---|---|
| RF-04 (3 profiles: mobile_co, desktop_co, desktop_ec) | `profiles/mobile_co.py`, `profiles/desktop_co.py`, `profiles/desktop_ec.py`, `profiles/__init__.py` |
| RF-05 (selectors centralized: LOGIN_*, SEARCH_*, PDP_*, CART_*, CHECKOUT_*, PAYMENT_*) | `selectors.py` |
| RF-06 (checkout_full, 10 steps, ResolvedEnvironment signature) | `flows/checkout_full.py` |
| RF-07 (checkout_card_declined, 10 steps, verify_decline_message) | `flows/checkout_card_declined.py` |
| RF-08 (runner, generic dispatch via catalog, InfrastructureError) | `runner.py` |
| RNF-02 (orders_created=0 in flows and runner, hard assert) | `flows/checkout_full.py`, `flows/checkout_card_declined.py`, `runner.py` |
| RNF-03 (logging without secrets, module-level logger) | `auth/shopper_login.py`, `flows/checkout_full.py`, `flows/checkout_card_declined.py`, `runner.py` |
| RNF-04 (InfrastructureError vs functional error, explicit distinction) | `runner.py` |
| RNF-07 (wait_for_selector/expect, zero time.sleep) | All flow files — verified by AST inspection in tests |
| ADR-001 (credentials via ResolvedEnvironment, no loose strings) | `auth/shopper_login.py`, `flows/checkout_full.py`, `flows/checkout_card_declined.py`, `runner.py` |
| ADR-003 (evidence fail+final always, finding/critical only in audit) | `flows/checkout_full.py`, `flows/checkout_card_declined.py` |
| Gate 3 (auth encapsulated and testable, 3 profiles, InfraError covered, orders_created=0) | `auth/`, `profiles/`, `runner.py`, all test files |

---

## Pending: Selectors Adjustment

`selectors.py` uses SFRA OOTB defaults. These require validation and potential
adjustment once access to a real SFCC storefront (staging environment) is
available. Key selectors to verify against the actual storefront:

- `LOGIN_EMAIL_INPUT` / `LOGIN_PASSWORD_INPUT` / `LOGIN_SUBMIT_BUTTON` — vary by cartridge theme
- `PDP_VARIANT_SELECT` — depends on the specific variant UI implementation
- `PAYMENT_CARD_NUMBER` / `PAYMENT_EXPIRY` / `PAYMENT_CVV` — depend on payment cartridge
  (CyberSource, Stripe, or SFCC native checkout)
- `PAYMENT_ERROR_MESSAGE` / `PAYMENT_DECLINE_MESSAGE` — depend on payment provider error handling

All selector updates must be made exclusively in `selectors.py` (invariant C7).
No flow file may be modified for selector-only changes.
