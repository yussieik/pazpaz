# Phase 3: Multi-Provider Support & US Market Expansion

**Duration:** 2-3 weeks
**Prerequisites:** Phase 1-2 complete (PayPlus working, receipts/reports built)
**Goal:** Add Stripe for US market expansion and Meshulam as PayPlus alternative for Israel

---

## Overview

Phase 3 expands payment provider options to support:
1. **Stripe** - For US therapists (HIPAA-compliant with BAA)
2. **Meshulam (Grow)** - Alternative to PayPlus for Israeli therapists
3. **Provider switching** - Allow therapists to change providers without losing data

**Key Principle:** Leverage existing payment provider abstraction. Most code already exists; just add new implementations.

---

## Deliverables Checklist

### **Week 1: Stripe Integration (US Market)**

#### **1.1 Stripe Provider Implementation**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **1.1.1** Research Stripe API documentation
  - Read: https://stripe.com/docs/payments/payment-links
  - Document: Payment Links API
  - Document: Webhook events (checkout.session.completed, etc.)
  - Document: Webhook signature verification
  - **Deliverable:** Notes in `/docs/payment_providers/stripe_api_notes.md`

- [ ] **1.1.2** Sign Stripe Business Associate Agreement (BAA)
  - Required for HIPAA compliance in US
  - https://stripe.com/legal/baa
  - **Deliverable:** BAA signed and documented

- [ ] **1.1.3** Implement Stripe provider class
  - Extend `PaymentProvider` abstract base
  - Implement `create_payment_link()` using Stripe Payment Links API
  - Implement `verify_webhook()` using Stripe's signature verification
  - Implement `parse_webhook_payment()` for Stripe webhook events
  - Handle currency conversion (cents ↔ USD)
  - **Deliverable:** `src/pazpaz/payments/providers/stripe_provider.py`

- [ ] **1.1.4** Add Stripe dependency with async support
  - Install: `uv add "stripe[async]"` (includes httpx for async requests)
  - Alternatively: `uv add stripe` (httpx will be auto-added if needed)
  - Official Stripe Python library v13.0.0+ with robust async support
  - **Deliverable:** Updated `pyproject.toml`

**Implementation example:**
```python
# src/pazpaz/payments/providers/stripe_provider.py

import stripe
from decimal import Decimal
from datetime import datetime, timezone

from pazpaz.payments.base import (
    PaymentProvider, PaymentLinkRequest, PaymentLinkResponse,
    WebhookPaymentData, PaymentProviderError
)

class StripeProvider(PaymentProvider):
    """Stripe payment provider for US market (HIPAA-compliant with BAA)."""

    def __init__(self, config: dict):
        super().__init__(config)
        stripe.api_key = self.config["api_key"]

    async def create_payment_link(
        self, request: PaymentLinkRequest
    ) -> PaymentLinkResponse:
        """Create Stripe Payment Link (async)."""

        try:
            # Stripe requires amount in cents (1 USD = 100 cents)
            amount_cents = int(request.amount * 100)

            # ✅ CORRECT: Use async API method (create_async)
            payment_link = await stripe.PaymentLink.create_async(
                line_items=[{
                    "price_data": {
                        "currency": request.currency.lower(),
                        "product_data": {
                            "name": request.description,
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }],
                after_completion={
                    "type": "redirect",
                    "redirect": {"url": request.success_url or "https://pazpaz.app/payment/success"},
                },
                metadata=request.metadata or {},
                customer_creation="always",  # Create customer record
            )

            return PaymentLinkResponse(
                payment_link_url=payment_link.url,
                provider_transaction_id=payment_link.id,
                expires_at=None,  # Stripe Payment Links don't expire
            )

        except stripe.StripeError as e:
            raise PaymentProviderError(f"Stripe API error: {e}")

    async def verify_webhook(self, payload: bytes, headers: dict) -> bool:
        """Verify Stripe webhook signature."""

        signature = headers.get("stripe-signature", "")
        webhook_secret = self.config["webhook_secret"]

        try:
            stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return True
        except stripe.SignatureVerificationError:
            return False

    async def parse_webhook_payment(self, payload: dict) -> WebhookPaymentData:
        """Parse Stripe webhook data."""

        event_type = payload["type"]
        data = payload["data"]["object"]

        # Map Stripe events to payment status
        status_map = {
            "checkout.session.completed": "completed",
            "charge.failed": "failed",
            "charge.refunded": "refunded",
        }

        status = status_map.get(event_type, "pending")

        # Convert cents to dollars
        amount = Decimal(str(data.get("amount_total", 0))) / 100
        currency = data.get("currency", "usd").upper()

        return WebhookPaymentData(
            provider_transaction_id=data["id"],
            status=status,
            amount=amount,
            currency=currency,
            completed_at=(
                datetime.fromtimestamp(data["created"], tz=timezone.utc)
                if status == "completed"
                else None
            ),
            failure_reason=data.get("failure_message") if status == "failed" else None,
            metadata=data.get("metadata"),
        )

    async def get_payment_status(
        self, provider_transaction_id: str
    ) -> WebhookPaymentData:
        """Poll Stripe payment status (fallback for missed webhooks)."""

        try:
            # ✅ CORRECT: Use async API method (retrieve_async)
            session = await stripe.checkout.Session.retrieve_async(provider_transaction_id)

            # Convert to webhook format for consistency
            fake_webhook = {
                "type": (
                    "checkout.session.completed"
                    if session.payment_status == "paid"
                    else "charge.failed"
                ),
                "data": {"object": session},
            }

            return await self.parse_webhook_payment(fake_webhook)

        except stripe.StripeError as e:
            raise PaymentProviderError(f"Stripe API error: {e}")
```

#### **1.2 Update Payment Provider Factory**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **1.2.1** Add Stripe to provider factory
  - Update `get_payment_provider()` to handle "stripe" provider
  - **Deliverable:** Updated `src/pazpaz/payments/factory.py`

```python
# src/pazpaz/payments/factory.py (update)

from pazpaz.payments.providers.stripe_provider import StripeProvider

def get_payment_provider(workspace: Workspace) -> PaymentProvider:
    """Factory to instantiate correct payment provider for workspace."""

    provider_name = workspace.payment_provider

    if not provider_name:
        raise PaymentProviderError("Payment provider not configured for workspace")

    config = workspace.payment_provider_config or {}

    if provider_name == "payplus":
        return PayPlusProvider(config)
    elif provider_name == "stripe":
        return StripeProvider(config)
    elif provider_name == "meshulam":
        return MesshulamProvider(config)
    else:
        raise PaymentProviderError(f"Unknown payment provider: {provider_name}")
```

#### **1.3 Stripe Testing**
**Owner:** You + `backend-qa-specialist` agent

- [ ] **1.3.1** Create Stripe test account
  - Sign up for Stripe test mode account
  - Get test API keys
  - Configure webhook endpoint
  - **Deliverable:** Test account credentials documented

- [ ] **1.3.2** Test Stripe payment flow in sandbox
  - Configure workspace with Stripe test credentials
  - Create payment request
  - Complete payment in Stripe Checkout
  - Verify webhook received
  - Verify appointment marked as paid
  - **Deliverable:** Manual test checklist completed

- [ ] **1.3.3** Unit tests for Stripe provider
  - Mock Stripe API calls
  - Test `create_payment_link()` success/failure
  - Test webhook signature verification
  - Test currency conversion (cents ↔ USD)
  - **Deliverable:** `tests/test_payments/test_stripe_provider.py`

---

### **Week 2: Meshulam Alternative (Israel Market)**

#### **2.1 Meshulam Provider Implementation**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **2.1.1** Research Meshulam (Grow) API documentation
  - Read: https://grow-il.readme.io/
  - Document: Payment Page API
  - Document: Webhook format
  - Compare with PayPlus (differences, similarities)
  - **Deliverable:** Notes in `/docs/payment_providers/meshulam_api_notes.md`

- [ ] **2.1.2** Implement Meshulam provider class
  - Extend `PaymentProvider` abstract base
  - Implement `create_payment_link()`
  - Implement `verify_webhook()`
  - Implement `parse_webhook_payment()`
  - Handle agorot conversion (1 ILS = 100 agorot)
  - **Deliverable:** `src/pazpaz/payments/providers/meshulam_provider.py`

**Implementation notes:**
- Very similar to PayPlus provider (both Israeli providers)
- Main difference: Meshulam uses agorot (amount * 100), PayPlus uses ILS directly
- Webhook signature format may differ slightly

**Implementation example:**
```python
# src/pazpaz/payments/providers/meshulam_provider.py

import hashlib
import hmac
import httpx
from decimal import Decimal
from datetime import datetime

from pazpaz.payments.base import (
    PaymentProvider, PaymentLinkRequest, PaymentLinkResponse,
    WebhookPaymentData, PaymentProviderError
)

class MesshulamProvider(PaymentProvider):
    """Meshulam (Grow) payment provider for Israel market."""

    BASE_URL = "https://secure.meshulam.co.il/api"

    async def create_payment_link(
        self, request: PaymentLinkRequest
    ) -> PaymentLinkResponse:
        """Create Meshulam payment page link."""

        api_key = self.config["api_key"]
        terminal_id = self.config["terminal_id"]

        # Meshulam requires amount in agorot (1 ILS = 100 agorot)
        amount_agorot = int(request.amount * 100)

        payload = {
            "apiKey": api_key,
            "userId": terminal_id,
            "sum": amount_agorot,
            "description": request.description,
            "email": request.customer_email,
            "successUrl": request.success_url or "",
            "cancelUrl": request.cancel_url or "",
            "customFields": request.metadata or {},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/createPaymentPage",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("status") != "success":
                    raise PaymentProviderError(
                        f"Meshulam API error: {data.get('error', 'Unknown')}"
                    )

                return PaymentLinkResponse(
                    payment_link_url=data["url"],
                    provider_transaction_id=data["transactionId"],
                    expires_at=None,
                )

            except httpx.HTTPError as e:
                raise PaymentProviderError(f"HTTP error calling Meshulam: {e}")

    async def verify_webhook(self, payload: bytes, headers: dict) -> bool:
        """Verify Meshulam webhook signature."""

        signature = headers.get("x-meshulam-signature", "")
        webhook_secret = self.config["webhook_secret"]

        expected_signature = hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    async def parse_webhook_payment(self, payload: dict) -> WebhookPaymentData:
        """Parse Meshulam webhook data."""

        status_map = {
            "approved": "completed",
            "declined": "failed",
            "refunded": "refunded",
        }

        status = status_map.get(payload.get("status"), "failed")

        # Convert agorot to ILS
        amount = Decimal(str(payload.get("sum", 0))) / 100

        return WebhookPaymentData(
            provider_transaction_id=payload["transactionId"],
            status=status,
            amount=amount,
            currency="ILS",
            completed_at=(
                datetime.fromisoformat(payload["completedAt"])
                if status == "completed"
                else None
            ),
            failure_reason=payload.get("declineReason") if status == "failed" else None,
            metadata=payload.get("customFields"),
        )
```

#### **2.2 Update Provider Factory**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **2.2.1** Add Meshulam to provider factory
  - Import `MesshulamProvider`
  - Add to factory function
  - **Deliverable:** Updated factory

#### **2.3 Meshulam Testing**
**Owner:** You + `backend-qa-specialist` agent

- [ ] **2.3.1** Get Meshulam test account
  - Sign up for Meshulam test environment
  - Get test API credentials
  - **Deliverable:** Test account credentials documented

- [ ] **2.3.2** Test Meshulam payment flow
  - Configure workspace with Meshulam
  - Create payment request
  - Complete payment in Meshulam sandbox
  - Verify webhook processing
  - **Deliverable:** Manual test checklist

- [ ] **2.3.3** Unit tests for Meshulam provider
  - Mock Meshulam API calls
  - Test agorot conversion
  - Test webhook verification
  - **Deliverable:** `tests/test_payments/test_meshulam_provider.py`

---

### **Week 3: Provider Switching & Currency Support**

#### **3.1 Provider Switching**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **3.1.1** Implement provider switching API endpoint
  - Endpoint: `POST /api/v1/workspaces/{id}/change-payment-provider`
  - Input: `{new_provider, new_config}`
  - Validate credentials before switching
  - Preserve historical payment transaction data
  - Update workspace `payment_provider` and `payment_provider_config`
  - **Deliverable:** Provider switching endpoint

- [ ] **3.1.2** Add provider switching UI
  - "Change Provider" button in Payment Settings
  - Show warning: "Existing payment links will not work"
  - Confirm before switching
  - **Deliverable:** Provider switching UI in frontend

**Implementation notes:**
- Keep all existing `payment_transactions` (historical data)
- Pending payment links from old provider will break (acceptable)
- New payments will use new provider

#### **3.2 Multi-Currency Support**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **3.2.1** Add currency field to workspace
  - Add `default_currency` to `workspaces` table (migration)
  - Default: "ILS" for Israeli therapists, "USD" for US therapists
  - **Deliverable:** Currency field migration

- [ ] **3.2.2** Update payment creation to use workspace currency
  - Read `workspace.default_currency` instead of hardcoded "ILS"
  - Pass to payment provider
  - **Deliverable:** Currency support in payment service

- [ ] **3.2.3** Add currency selector to workspace settings
  - Dropdown: ILS, USD, EUR, GBP, CAD, AUD
  - Only allow currency change if no existing payments
  - **Deliverable:** Currency selector in frontend

**Note:** For V1, keep it simple:
- One currency per workspace (can't mix ILS and USD in same workspace)
- No exchange rate conversions
- Multi-currency invoicing is future feature (Phase 4+)

---

### **Week 3: Testing & Documentation**

#### **4.1 Comprehensive Testing**
**Owner:** `backend-qa-specialist` agent

- [ ] **4.1.1** Test all three providers
  - PayPlus payment flow
  - Stripe payment flow
  - Meshulam payment flow
  - Verify all webhooks processed correctly
  - **Deliverable:** Multi-provider integration tests

- [ ] **4.1.2** Test provider switching
  - Switch from PayPlus to Stripe
  - Verify historical data preserved
  - Verify new payments use new provider
  - **Deliverable:** Provider switching tests

- [ ] **4.1.3** Test currency support
  - Create payment in USD (Stripe)
  - Create payment in ILS (PayPlus/Meshulam)
  - Verify amounts calculated correctly
  - **Deliverable:** Currency tests

#### **4.2 Documentation**
**Owner:** You

- [ ] **4.2.1** Document all payment providers
  - PayPlus setup guide
  - Stripe setup guide (including BAA)
  - Meshulam setup guide
  - Provider comparison table
  - **Deliverable:** `/docs/payment_providers/README.md`

- [ ] **4.2.2** Update user guides
  - How to choose payment provider
  - How to switch providers
  - Currency selection guide
  - **Deliverable:** Updated user guides

- [ ] **4.2.3** Create provider comparison table for therapists
  - Fees: PayPlus vs Meshulam vs Stripe
  - Geographic availability
  - Features
  - Recommendation by use case
  - **Deliverable:** Provider comparison document

**Provider Comparison Table:**
```markdown
| Feature | PayPlus (Israel) | Meshulam (Israel) | Stripe (US) |
|---------|------------------|-------------------|-------------|
| Transaction Fee | ~2.7% | ~2.5% | 2.9% + $0.30 |
| Market | Israel | Israel | US, Global |
| HIPAA Support | N/A | N/A | ✅ (with BAA) |
| Currency | ILS | ILS | USD, EUR, 30+ |
| Setup Difficulty | Easy | Medium | Easy |
| Documentation | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Recommendation | Israel (default) | Israel (alternative) | US only |
```

---

## Acceptance Criteria

**Phase 3 is complete when:**

✅ **Stripe working** - US therapists can accept USD payments via Stripe
✅ **Meshulam working** - Israeli therapists have alternative to PayPlus
✅ **Provider switching working** - Can change providers without losing data
✅ **Multi-currency support** - Payments work in ILS and USD
✅ **All tests passing** - Unit, integration, and manual tests pass
✅ **Documentation complete** - Provider setup guides and comparison table
✅ **Stripe BAA signed** - HIPAA compliance for US market

---

## Risk Mitigation

### **Risk:** Stripe BAA delays
**Mitigation:**
- Start BAA process early (Week 1)
- Stripe typically processes in 3-5 business days
- Can test in Stripe sandbox while waiting for BAA

### **Risk:** Provider API rate limits
**Mitigation:**
- Implement exponential backoff for API calls
- Cache provider responses where appropriate
- Monitor rate limit headers in responses

### **Risk:** Currency conversion errors
**Mitigation:**
- Use provider's native currency (don't convert ourselves)
- Store amounts in original currency
- Extensive unit tests for cent/agorot conversions

### **Risk:** Therapists confused about which provider to choose
**Mitigation:**
- Clear recommendation in UI: "Israel → PayPlus, US → Stripe"
- Provider comparison table
- Default based on workspace location (if available)

---

## Optional Phase 4 Features (Future)

After Phase 3, consider these advanced features:
- **GreenInvoice/Morning integration** - Full Israeli Tax Authority compliance
- **Recurring billing** - Monthly retainers
- **Payment plans** - Installments for large treatments
- **Multi-currency workspace** - Support both ILS and USD in same workspace
- **Dynamic currency conversion** - Real-time exchange rates

---

## Notes

- **Stripe BAA is critical** - Cannot launch US without it
- **Provider abstraction pays off** - Adding providers is now straightforward
- **Keep currency support simple** - One currency per workspace is sufficient for V1
- **Test all providers thoroughly** - Each has unique quirks and edge cases
- **Document provider setup clearly** - Therapists need step-by-step guides
