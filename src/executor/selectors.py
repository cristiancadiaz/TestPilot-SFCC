"""SFCC storefront selectors — the single source of truth (invariant C7).

ALL CSS/XPath selectors for every SFCC flow live here and ONLY here.
No flow, runner, or helper file may define inline selectors.

Selector values are SFRA defaults; they will need adjustment once
access to a real storefront is obtained (see code-summary.md §Pending).

Naming: SCREAMING_SNAKE_CASE. Each constant has a one-line docstring.
"""


class SFCCSelectors:
    """Centralised SFCC SFRA selector registry."""

    # ------------------------------------------------------------------
    # GROUP: LOGIN_* — shopper login form
    # ------------------------------------------------------------------

    LOGIN_EMAIL_INPUT: str = "input[name='loginEmail']"
    """Input field for the shopper's email address on the login form."""

    LOGIN_PASSWORD_INPUT: str = "input[name='loginPassword']"
    """Input field for the shopper's password on the login form."""

    LOGIN_SUBMIT_BUTTON: str = "button[value='login']"
    """Submit button on the shopper login form."""

    LOGIN_ERROR_MESSAGE: str = ".login-form-nav .alert-danger"
    """Error banner shown when login credentials are invalid."""

    LOGIN_REGISTERED_USER: str = "a.nav-link[data-toggle='tab'][href='#login']"
    """Tab or link to switch to the registered user login panel."""

    # ------------------------------------------------------------------
    # GROUP: SEARCH_* — header search bar
    # ------------------------------------------------------------------

    SEARCH_INPUT: str = "input.search-field"
    """Search input field in the storefront header."""

    SEARCH_SUBMIT: str = "button.search-button"
    """Search submit button (magnifier icon) in the header."""

    SEARCH_RESULTS_GRID: str = ".product-grid .product"
    """Product grid container on a search results / PLP page."""

    # ------------------------------------------------------------------
    # GROUP: PDP_* — product detail page
    # ------------------------------------------------------------------

    PDP_PRODUCT_NAME: str = ".product-detail .product-name"
    """Primary product name heading on the PDP."""

    PDP_PRICE: str = ".product-detail .sales .value"
    """Main visible price on the PDP."""

    PDP_VARIANT_SELECT: str = ".attribute .select-size"
    """Variant selector (size / colour) dropdown on the PDP."""

    PDP_ADD_TO_CART: str = "button.add-to-cart"
    """Add-to-cart button on the PDP."""

    # ------------------------------------------------------------------
    # GROUP: CART_* — mini cart and full cart page
    # ------------------------------------------------------------------

    CART_MINI_CART: str = ".minicart-quantity"
    """Mini-cart quantity badge / container in the header."""

    CART_ITEM_COUNT: str = ".minicart .quantity-stepper"
    """Item quantity indicator inside the mini cart."""

    CART_CHECKOUT_BUTTON: str = ".cart-page .checkout-btn"
    """'Proceed to checkout' button on the full cart page."""

    CART_ITEM_PRICE: str = ".cart-page .price .sales .value"
    """Per-item price display on the cart page."""

    # ------------------------------------------------------------------
    # GROUP: CHECKOUT_* — checkout flow container
    # ------------------------------------------------------------------

    CHECKOUT_SHIPPING_FORM: str = "#checkout-main .shipping-form"
    """Shipping address form within the checkout flow."""

    CHECKOUT_SHIPPING_NEXT: str = "button.submit-shipping"
    """'Continue to payment' button at the end of the shipping step."""

    CHECKOUT_PAYMENT_SECTION: str = "#checkout-main .payment-form"
    """Payment section container in the checkout flow."""

    # ------------------------------------------------------------------
    # GROUP: PAYMENT_* — payment form fields and messages
    # ------------------------------------------------------------------

    PAYMENT_CARD_NUMBER: str = "input[id='cardNumber']"
    """Credit card number input field."""

    PAYMENT_EXPIRY: str = "input[id='expirationDate']"
    """Card expiry date input field (MM/YY format)."""

    PAYMENT_CVV: str = "input[id='securityCode']"
    """Card CVV / security code input field."""

    PAYMENT_SUBMIT: str = "button.place-order"
    """Submit / 'Place order' button that triggers payment processing."""

    PAYMENT_ERROR_MESSAGE: str = ".error-message .alert-danger"
    """Generic payment error banner shown on payment failure."""

    PAYMENT_DECLINE_MESSAGE: str = ".card-number-wrapper .alert-danger"
    """Specific card-declined message shown when the card is rejected."""

    # ------------------------------------------------------------------
    # Test data constants (NOT CSS selectors — synthetic data values)
    # ------------------------------------------------------------------

    # Zero-contamination invariant #1: the test card ALWAYS fails at
    # the final payment step. A real order is NEVER created.
    TEST_CARD_NUMBER: str = "4111111111111111"
    """Test card number — always triggers payment failure (invariant #1)."""

    TEST_CARD_EXPIRY: str = "12/26"
    """Expiry date for the test card."""

    TEST_CARD_CVV: str = "123"
    """CVV for the test card."""

    # Used specifically in checkout_card_declined flow.
    DECLINED_CARD_NUMBER: str = "4000000000000002"
    """Card number that triggers an explicit 'card declined' UI message."""

    DECLINED_CARD_EXPIRY: str = "12/26"
    """Expiry date for the declined test card."""

    DECLINED_CARD_CVV: str = "123"
    """CVV for the declined test card."""

    # Synthetic shipping data — used to fill the shipping form.
    TEST_SHIPPING: dict[str, str] = {
        "first_name": "Testpilot",
        "last_name": "Synthetic",
        "address": "Calle Falsa 123",
        "city": "Bogota",
        "phone": "3001234567",
    }
    """Shipping address data for synthetic checkout runs."""
