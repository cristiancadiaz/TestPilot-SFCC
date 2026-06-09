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

    PDP_GALLERY: str = ".product-detail .primary-images img.d-block"
    """Primary product image in the PDP gallery."""

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

    CART_QUANTITY_INPUT: str = ".cart-page .quantity-form .quantity"
    """Quantity selector/input for a line item on the cart page."""

    CART_SUBTOTAL: str = ".cart-page .sub-total"
    """Cart subtotal amount on the cart page."""

    # ------------------------------------------------------------------
    # GROUP: PLP_* — product listing / search results page (U5 journey)
    # ------------------------------------------------------------------

    PLP_RESULT_COUNT: str = ".search-results .result-count"
    """Result-count label on a PLP / search results page."""

    PLP_REFINEMENT_CATEGORY: str = ".refinement.category a"
    """A category refinement link in the PLP refinements bar."""

    PLP_REFINEMENT_PRICE: str = ".refinement.price a"
    """A price-range refinement link in the PLP refinements bar."""

    PLP_APPLIED_REFINEMENT: str = ".filter-bar .filter-value"
    """An applied-refinement chip shown after a filter is selected."""

    PLP_TILE_PRICE: str = ".product-grid .product .price .sales .value"
    """Per-tile price on a PLP grid item."""

    PLP_TILE_LINK: str = ".product-grid .product a.link"
    """Link from a PLP grid tile to its PDP."""

    # ------------------------------------------------------------------
    # GROUP: PROMOTIONS_* — offers / discounted products (U5 journey)
    # ------------------------------------------------------------------

    PROMOTIONS_NAV: str = "a.nav-link[href*='sale']"
    """Header navigation link to the offers / sale category."""

    PROMOTIONS_DISCOUNT_BADGE: str = ".product .promotion .callout"
    """Promotion / discount badge shown on a discounted product."""

    PROMOTIONS_ORIGINAL_PRICE: str = ".product .price .strike-through .value"
    """Struck-through original price on a discounted product."""

    PROMOTIONS_DISCOUNTED_PRICE: str = ".product .price .sales .value"
    """Current (discounted) sales price on a discounted product."""

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
