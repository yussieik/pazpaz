# Payment Integration Plan

**Status:** Active - Ready for Implementation
**Created:** October 29, 2025
**Last Updated:** October 30, 2025 (Added Tax Compliance)
**Owner:** Product Team

---

## Recent Updates (October 30, 2025)

**Key Changes:**
1. **Provider Recommendation Updated:** PayPlus now recommended over Meshulam (better docs, simpler API)
2. **Phase 2 Added:** Tax compliance & financial reporting (receipts, VAT tracking, manual payments, Excel export)
3. **Database Schema Enhanced:** Added VAT breakdown (base_amount, vat_amount, total_amount), receipt tracking, business/tax details
4. **Feature Flag Design Added:** Payments are opt-in per workspace - see `/docs/PAYMENT_FEATURE_FLAG_DESIGN.md`
5. **Complete Tax-Compliant Schema:** See `/docs/PAYMENT_SCHEMA_TAX_COMPLIANT.sql` for full database design
6. **Research Document Added:** See `/docs/PAYMENT_INTEGRATION_RESEARCH_2025.md` for detailed 2025-2026 best practices

**Implementation Timeline:**
- **Phase 1 (Weeks 1-7):** Automated payment links (PayPlus integration)
- **Phase 2 (Weeks 8-12):** Tax receipts + financial reporting
- **Phase 3 (Months 4-5):** Optional third-party tax service (GreenInvoice/Morning)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Market Context](#market-context)
3. [Strategic Goals](#strategic-goals)
4. [Technical Approach](#technical-approach)
5. [Phased Implementation](#phased-implementation)
6. [Architecture Design](#architecture-design)
7. [Security & Compliance](#security--compliance)
8. [Risk Analysis](#risk-analysis)
9. [Success Metrics](#success-metrics)
10. [Open Questions](#open-questions)

---

## Executive Summary

### Problem Statement
Therapists need a way to track, request, and receive payments from clients for appointments. Current PazPaz functionality focuses on scheduling and documentation but lacks any payment tracking capabilities.

### Proposed Solution
Build a flexible, **optional** payment system that:
- **Opt-In Architecture:** Payments disabled by default, enabled via Settings tab per workspace
- **Automated Payment Flow:** Client receives email with payment link after appointment → pays online → status updated automatically
- **Multiple Payment Providers:** Israel (PayPlus/Meshulam), US (Stripe)
- **Tax Compliance:** Israeli tax receipts ("מס קבלה"), VAT tracking, financial reporting
- **Manual Payments:** Support cash/bank transfers for complete revenue tracking
- **Conditional UI:** Payment fields only visible when feature enabled (see [Feature Flag Design](/docs/PAYMENT_FEATURE_FLAG_DESIGN.md))
- **Therapist Control:** Optional feature, configurable timing (immediate, end-of-day, end-of-month)
- **Privacy-First:** No PHI sent to payment providers, HIPAA-compliant architecture

### Success Criteria
- **Phase 1 (Automated Payments):** 40%+ of active therapists enable automated payments within 2 months of launch
- **Phase 1 (Payment Completion):** >70% payment completion rate (payments sent → payments received)
- **Phase 2 (Tax Compliance):** >90% of therapists use receipt generation for paid appointments
- **Phase 2 (Financial Reporting):** >60% of therapists export revenue reports monthly/quarterly
- **Phase 3 (Advanced Features):** <5% payment failure rate, <2% support tickets related to payments

---

## Market Context

### Israel Payment Landscape (Primary Launch Market)

**Key Characteristics:**
- No Stripe availability
- Dominated by credit card clearing companies (Tranzila, Cardcom)
- Growing fintech scene with modern APIs (Meshulam, PayPlus)
- Tax receipt requirements ("מס קבלה") for business expenses
- Cash and bank transfers still common for healthcare services

**Primary Options:**

| Provider | API Quality | Market Share | Healthcare Usage | Notes |
|----------|-------------|--------------|------------------|-------|
| **Meshulam** | ⭐⭐⭐⭐⭐ | Medium | Growing | Modern REST API, webhook support, used by SaaS products |
| **PayPlus** | ⭐⭐⭐⭐ | Medium | Moderate | Good API, reliable, healthcare-friendly |
| **Tranzila** | ⭐⭐⭐ | High | High | Established, clunky API, widely trusted |
| **Cardcom** | ⭐⭐ | High | High | Legacy API, enterprise-focused |

**Recommendation for Phase 1:** Start with **PayPlus** (Updated Oct 30, 2025)
- **Best Documentation:** docs.payplus.co.il (more polished than Meshulam's grow-il.readme.io)
- **Simpler API:** Amount in ILS (not agorot conversion), Bearer token authentication
- **More Established:** Tens of thousands of merchants (lower risk of service disruption)
- **PCI DSS Level 1:** Highest security certification
- **Active GitHub:** github.com/PayPlus-Gateway with sample code
- **Transaction Fee:** ~2.7% (vs Meshulam's ~2.5%, difference of ₪3 on ₪150 payment)
- **Alternative:** Meshulam (Grow) has slightly lower fees but less polished developer experience

**Note:** Meshulam's original documentation site (doc.meshulam.co.il) is suspended. New docs at grow-il.readme.io are functional but less comprehensive than PayPlus.

### US Payment Landscape (Future Expansion)

**Key Characteristics:**
- Stripe dominates healthcare/SaaS space
- Strict HIPAA compliance requirements (BAA required)
- Payment Link and Checkout products simplify integration
- Established therapist expectations for online payments

**Primary Options:**

| Provider | HIPAA Support | Healthcare Usage | Notes |
|----------|---------------|------------------|-------|
| **Stripe** | ✅ (with BAA) | Very High | Industry standard, excellent docs |
| **Square Health** | ✅ | High | Healthcare-specific, higher fees |
| **Authorize.net** | ✅ | Medium | Legacy API, enterprise-focused |

**Recommendation for US Expansion:** **Stripe** (non-negotiable)
- Sign Business Associate Agreement (BAA) for HIPAA compliance
- Use Stripe Payment Links (simplest integration)
- Excellent documentation and developer experience
- Expected by US therapists

### Competitive Analysis

**Existing Practice Management Software:**

| Product | Payment Support | Geographic Focus | Integration Approach |
|---------|-----------------|------------------|----------------------|
| SimplePractice | Stripe only | US | 2.9% + $0.30/transaction |
| Jane App | Stripe, Square | US, Canada | Multiple providers |
| Cliniko | Stripe | Australia, US | Single provider |
| **PazPaz** | None (yet) | Israel → US | Multi-provider from start |

**Competitive Advantage:**
- **No strong Israel-focused competitor** with modern payment integration
- Multi-provider architecture allows geographic flexibility
- Optional feature (doesn't force therapists into online payments)

---

## Strategic Goals

### Primary Objectives

1. **Validate Demand (Phase 1)**
   - Launch manual payment tracking to test therapist interest
   - Learn payment patterns (timing, amounts, methods)
   - Identify which therapists need automated features

2. **Enable Israel Market (Phase 2)**
   - Integrate Meshulam for automated payment requests
   - Support ILS currency and Israeli tax requirements
   - Reduce therapist administrative burden

3. **Prepare for US Expansion (Phase 2+)**
   - Build multi-provider architecture from the start
   - Design data model that supports multiple currencies
   - Plan for Stripe integration when US users arrive

4. **Differentiate from Competitors (Phase 3)**
   - Payment plans (installments for large treatments)
   - Recurring billing (monthly retainers)
   - Advanced analytics (revenue tracking, outstanding balances)

### Non-Goals (V1 - Phase 1)

- ❌ Insurance claim processing/billing (US-specific, future consideration)
- ❌ Split payments across multiple parties
- ❌ Cryptocurrency payments
- ❌ Point-of-sale (POS) hardware integration
- ❌ Direct accounting software integrations (QuickBooks, Xero) - use export to Excel instead
- ❌ Multi-currency invoicing (single currency per workspace initially)
- ❌ Custom Israel Tax Authority API integration (use third-party service like GreenInvoice instead)

### Phase 2 Goals (Tax Compliance)

- ✅ Manual payment tracking (cash, bank transfers, checks) - needed for complete revenue picture
- ✅ Basic receipt generation (PDF with therapist branding)
- ✅ VAT tracking (base amount + VAT calculation)
- ✅ Financial reporting (monthly/quarterly revenue summaries)
- ✅ Export to Excel/CSV for accountant

---

## Technical Approach

### Core Principles

1. **Provider Abstraction:** Abstract payment provider interface so we can swap providers without changing business logic
2. **Workspace Flexibility:** Payment configuration lives at workspace level (each therapist chooses their provider)
3. **Optional Feature:** Payments are entirely optional; therapists can ignore this feature
4. **Audit Trail:** All payment events logged for financial compliance
5. **No Card Data:** Never store credit card numbers (PCI compliance avoidance)

### Technology Stack

**Backend:**
- SQLAlchemy models for payment data
- Abstract `PaymentProvider` base class
- Provider-specific implementations (Meshulam, Stripe)
- Webhook handlers for payment status updates
- PDF invoice generation (ReportLab or WeasyPrint)

**Frontend:**
- Payment settings in workspace configuration
- Payment status UI in appointment details
- Invoice preview and email sending
- Payment analytics dashboard (Phase 3)

**External Services:**
- Meshulam API (Israel)
- Stripe API (US)
- Email service (existing infrastructure)

---

## Phased Implementation

### Phase 1: Automated Payment Flow (Weeks 1-7)

**Goal:** Implement fully automated payment collection with payment provider integration.

**Architecture:** Opt-in feature flag system (see [Feature Flag Design](/docs/PAYMENT_FEATURE_FLAG_DESIGN.md))

**User Flow:**
1. Therapist **enables payments** in Settings tab (one-time setup)
2. Therapist sets price on appointment (new field visible only when payments enabled)
3. Therapist marks appointment as "Completed"
4. **IF** payment_auto_send enabled → PazPaz generates payment link via PayPlus API
5. Email sent to client with payment link
6. Client clicks link → pays on PayPlus hosted page (enters card details)
7. PayPlus sends webhook to PazPaz with payment confirmation
8. PazPaz verifies webhook signature → updates appointment status to "Paid"
9. Therapist sees "Paid ✅" badge in appointment list AND calendar view
10. Payment tracked in `payment_transactions` table with VAT breakdown

**Key Features (Phase 1):**
- ✅ **Feature Flag Infrastructure:** Payments disabled by default, opt-in via Settings
- ✅ **Conditional UI:** Payment fields only render when `workspace.payment_provider` is set
- ✅ Payment link generation (PayPlus integration)
- ✅ Webhook handling with signature verification + idempotency
- ✅ Automated email to client with payment link
- ✅ Payment status tracking ("unpaid", "pending", "paid", "failed")
- ✅ VAT calculation and tracking (if workspace is VAT-registered)
- ✅ Workspace payment configuration UI (5-step onboarding)
- ✅ Payment history view (per appointment)
- ✅ Calendar indicators (💵 Paid, 🔄 Pending)
- ✅ Audit logging for all payment events

#### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      PazPaz Backend                         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PaymentService                                      │  │
│  │  - create_payment_request()                          │  │
│  │  - process_webhook()                                 │  │
│  │  - generate_invoice_pdf()                            │  │
│  └──────────────┬───────────────────────────────────────┘  │
│                 │                                           │
│  ┌──────────────▼───────────────────────────────────────┐  │
│  │  PaymentProvider (Abstract Interface)               │  │
│  │  - create_payment_link()                            │  │
│  │  - verify_webhook()                                 │  │
│  │  - parse_webhook_payment()                          │  │
│  └──────────────┬───────────────────────────────────────┘  │
│                 │                                           │
│     ┌───────────┼──────────┐                                │
│     │           │          │                                │
│  ┌──▼───────┐ ┌▼──────────▼┐                               │
│  │ Meshulam │ │   Stripe    │  (Future providers...)        │
│  │ Provider │ │  Provider   │                               │
│  └──────────┘ └─────────────┘                               │
└─────────────────────────────────────────────────────────────┘
         │                       │
         │ Webhook               │ Webhook
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  Meshulam API   │     │   Stripe API    │
└─────────────────┘     └─────────────────┘
```

#### Database Schema Additions

**New Table: `payment_transactions`**
```python
class PaymentTransaction(Base):
    """Immutable payment event log"""
    __tablename__ = "payment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
        index=True
    )

    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointments.id"),
        nullable=True,  # Null for manual payments not tied to appointment
        index=True
    )

    # Payment details (with VAT breakdown for tax compliance)
    base_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    # Amount before VAT (מחיר לפני מע"מ)

    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=0,
        nullable=False
    )
    # VAT portion (מע"מ). 0 if workspace is VAT-exempt.

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    # Base + VAT

    currency: Mapped[str] = mapped_column(
        String(3),
        default="ILS",
        nullable=False
    )

    # Payment method
    payment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    # Options: "online_card", "cash", "bank_transfer", "check"

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )
    # Options: "pending", "completed", "failed", "refunded", "cancelled"

    # Provider details (for online payments)
    provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    # Options: "payplus", "meshulam", "stripe", "manual"

    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True  # For webhook lookups
    )

    provider_payment_link: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )

    failed_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )
    # Store provider-specific data (invoice PDF URL, customer email, etc.)

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="payment_transactions")
    appointment: Mapped["Appointment"] = relationship(back_populates="payment_transactions")
```

**Receipt Tracking (Added to PaymentTransaction):**
```python
# Receipt details
receipt_number: Mapped[str | None] = mapped_column(
    String(50),
    nullable=True
)
# Auto-generated sequential number: "2025-001234"

receipt_issued: Mapped[bool] = mapped_column(
    default=False,
    nullable=False
)

receipt_issued_at: Mapped[datetime | None] = mapped_column(
    nullable=True
)

receipt_pdf_url: Mapped[str | None] = mapped_column(
    Text,
    nullable=True
)
# S3/MinIO link to PDF receipt

notes: Mapped[str | None] = mapped_column(
    Text,
    nullable=True
)
# For manual payments: "Client paid cash at end of session"
```

**Workspace Configuration:**
```python
# Add to Workspace model

# Business details (for tax receipts)
business_name: Mapped[str | None] = mapped_column(String(255))
business_name_hebrew: Mapped[str | None] = mapped_column(String(255))  # שם העסק בעברית
tax_id: Mapped[str | None] = mapped_column(String(20))  # ת.ז. or ח.פ.
business_license: Mapped[str | None] = mapped_column(String(50))  # רישיון עסק
business_address: Mapped[str | None] = mapped_column(Text)

# VAT configuration
vat_registered: Mapped[bool] = mapped_column(default=False)  # עוסק מורשה
vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=17.00)  # Israel: 17%
receipt_counter: Mapped[int] = mapped_column(Integer, default=0)  # Auto-increment

# Payment provider configuration
payment_provider: Mapped[str | None] = mapped_column(
    String(50),
    nullable=True,
    default=None
)
# Options: None, "payplus", "meshulam", "stripe"

payment_provider_config: Mapped[dict | None] = mapped_column(
    JSONB,
    nullable=True
)
# Encrypted JSON blob containing:
# {
#   "api_key": "encrypted_key",
#   "payment_page_uid": "...",  (PayPlus-specific)
#   "webhook_secret": "encrypted_secret"
# }

payment_auto_send: Mapped[bool] = mapped_column(
    default=False,
    nullable=False
)
# Auto-send payment request after appointment completion

payment_send_timing: Mapped[str] = mapped_column(
    String(20),
    default="immediately",
    nullable=False
)
# Options: "immediately", "end_of_day", "end_of_month", "manual"

payment_email_template: Mapped[str | None] = mapped_column(
    Text,
    nullable=True
)
# Custom email template for payment requests (optional)
```

#### Payment Provider Abstraction

**Base Interface:**
```python
# src/pazpaz/payments/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

@dataclass
class PaymentLinkRequest:
    """Request to create a payment link"""
    amount: Decimal
    currency: str  # ISO 4217 code (ILS, USD)
    description: str
    customer_email: str
    customer_name: str | None = None
    metadata: dict | None = None  # Internal tracking data
    success_url: str | None = None  # Redirect after payment
    cancel_url: str | None = None

@dataclass
class PaymentLinkResponse:
    """Response from payment link creation"""
    payment_link_url: str
    provider_transaction_id: str
    expires_at: datetime | None = None

@dataclass
class WebhookPaymentData:
    """Parsed payment data from webhook"""
    provider_transaction_id: str
    status: str  # "completed", "failed", "refunded"
    amount: Decimal
    currency: str
    completed_at: datetime | None = None
    failure_reason: str | None = None
    metadata: dict | None = None

class PaymentProvider(ABC):
    """Abstract base class for payment provider integrations"""

    def __init__(self, config: dict):
        """
        Initialize provider with configuration.

        Args:
            config: Provider-specific configuration (API keys, etc.)
        """
        self.config = config

    @abstractmethod
    async def create_payment_link(
        self,
        request: PaymentLinkRequest
    ) -> PaymentLinkResponse:
        """
        Generate a payment link for the customer.

        Returns:
            PaymentLinkResponse with URL and transaction ID

        Raises:
            PaymentProviderError: If link creation fails
        """
        pass

    @abstractmethod
    async def verify_webhook(
        self,
        payload: bytes,
        headers: dict
    ) -> bool:
        """
        Verify webhook authenticity using signature.

        Args:
            payload: Raw webhook body
            headers: HTTP headers (including signature)

        Returns:
            True if webhook is authentic
        """
        pass

    @abstractmethod
    async def parse_webhook_payment(
        self,
        payload: dict
    ) -> WebhookPaymentData:
        """
        Extract payment data from webhook payload.

        Args:
            payload: Parsed JSON webhook body

        Returns:
            Structured payment data
        """
        pass

    @abstractmethod
    async def get_payment_status(
        self,
        provider_transaction_id: str
    ) -> WebhookPaymentData:
        """
        Poll payment status (fallback for missed webhooks).

        Args:
            provider_transaction_id: External transaction ID

        Returns:
            Current payment status
        """
        pass

class PaymentProviderError(Exception):
    """Base exception for payment provider errors"""
    pass
```

**Meshulam Provider Implementation:**
```python
# src/pazpaz/payments/providers/meshulam.py
import hashlib
import hmac
from decimal import Decimal
from datetime import datetime
import httpx

from pazpaz.payments.base import (
    PaymentProvider,
    PaymentLinkRequest,
    PaymentLinkResponse,
    WebhookPaymentData,
    PaymentProviderError,
)

class MesshulamProvider(PaymentProvider):
    """
    Meshulam payment provider for Israel market.

    API Documentation: https://meshulamapi.com/docs
    """

    BASE_URL = "https://secure.meshulam.co.il/api"

    async def create_payment_link(
        self,
        request: PaymentLinkRequest
    ) -> PaymentLinkResponse:
        """Create Meshulam payment page link"""

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

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/createPaymentPage",
                    json=payload,
                    timeout=10.0,
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
                    expires_at=None,  # Meshulam links don't expire
                )

            except httpx.HTTPError as e:
                raise PaymentProviderError(f"HTTP error calling Meshulam: {e}")

    async def verify_webhook(
        self,
        payload: bytes,
        headers: dict
    ) -> bool:
        """Verify Meshulam webhook signature"""

        signature = headers.get("X-Meshulam-Signature", "")
        webhook_secret = self.config["webhook_secret"]

        # Meshulam uses HMAC-SHA256
        expected_signature = hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    async def parse_webhook_payment(
        self,
        payload: dict
    ) -> WebhookPaymentData:
        """Parse Meshulam webhook data"""

        status_map = {
            "approved": "completed",
            "declined": "failed",
            "refunded": "refunded",
        }

        status = status_map.get(payload.get("status"), "failed")

        # Convert agorot to ILS
        amount = Decimal(payload.get("sum", 0)) / 100

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

    async def get_payment_status(
        self,
        provider_transaction_id: str
    ) -> WebhookPaymentData:
        """Poll Meshulam payment status"""

        api_key = self.config["api_key"]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/transactions/{provider_transaction_id}",
                params={"apiKey": api_key},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            return await self.parse_webhook_payment(data)
```

**Stripe Provider Implementation:**
```python
# src/pazpaz/payments/providers/stripe.py
import stripe
from decimal import Decimal
from datetime import datetime, timezone

from pazpaz.payments.base import (
    PaymentProvider,
    PaymentLinkRequest,
    PaymentLinkResponse,
    WebhookPaymentData,
    PaymentProviderError,
)

class StripeProvider(PaymentProvider):
    """
    Stripe payment provider for US market.

    API Documentation: https://stripe.com/docs/api
    """

    def __init__(self, config: dict):
        super().__init__(config)
        stripe.api_key = self.config["api_key"]

    async def create_payment_link(
        self,
        request: PaymentLinkRequest
    ) -> PaymentLinkResponse:
        """Create Stripe Payment Link"""

        try:
            # Stripe requires amount in cents (1 USD = 100 cents)
            amount_cents = int(request.amount * 100)

            # Create Payment Link
            payment_link = stripe.PaymentLink.create(
                line_items=[
                    {
                        "price_data": {
                            "currency": request.currency.lower(),
                            "product_data": {
                                "name": request.description,
                            },
                            "unit_amount": amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                after_completion={
                    "type": "redirect",
                    "redirect": {"url": request.success_url or ""},
                },
                metadata=request.metadata or {},
            )

            return PaymentLinkResponse(
                payment_link_url=payment_link.url,
                provider_transaction_id=payment_link.id,
                expires_at=None,  # Stripe Payment Links don't expire
            )

        except stripe.StripeError as e:
            raise PaymentProviderError(f"Stripe API error: {e}")

    async def verify_webhook(
        self,
        payload: bytes,
        headers: dict
    ) -> bool:
        """Verify Stripe webhook signature"""

        signature = headers.get("Stripe-Signature", "")
        webhook_secret = self.config["webhook_secret"]

        try:
            stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return True
        except stripe.SignatureVerificationError:
            return False

    async def parse_webhook_payment(
        self,
        payload: dict
    ) -> WebhookPaymentData:
        """Parse Stripe webhook data"""

        event_type = payload["type"]
        data = payload["data"]["object"]

        status_map = {
            "checkout.session.completed": "completed",
            "charge.failed": "failed",
            "charge.refunded": "refunded",
        }

        status = status_map.get(event_type, "pending")

        # Convert cents to dollars
        amount = Decimal(data.get("amount", 0)) / 100
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
        self,
        provider_transaction_id: str
    ) -> WebhookPaymentData:
        """Poll Stripe payment status"""

        try:
            session = stripe.checkout.Session.retrieve(provider_transaction_id)

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

**Provider Factory:**
```python
# src/pazpaz/payments/factory.py
from pazpaz.payments.base import PaymentProvider, PaymentProviderError
from pazpaz.payments.providers.meshulam import MesshulamProvider
from pazpaz.payments.providers.stripe import StripeProvider
from pazpaz.models import Workspace

def get_payment_provider(workspace: Workspace) -> PaymentProvider:
    """
    Factory to instantiate correct payment provider for workspace.

    Args:
        workspace: Workspace with payment configuration

    Returns:
        Configured PaymentProvider instance

    Raises:
        PaymentProviderError: If provider is unknown or not configured
    """
    provider_name = workspace.payment_provider

    if not provider_name:
        raise PaymentProviderError("Payment provider not configured for workspace")

    config = workspace.payment_provider_config or {}

    if provider_name == "meshulam":
        return MesshulamProvider(config)
    elif provider_name == "stripe":
        return StripeProvider(config)
    else:
        raise PaymentProviderError(f"Unknown payment provider: {provider_name}")
```

#### Payment Service Layer

```python
# src/pazpaz/services/payment_service.py
from decimal import Decimal
from datetime import datetime, timezone
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from pazpaz.models import Workspace, Appointment, PaymentTransaction
from pazpaz.payments.factory import get_payment_provider
from pazpaz.payments.base import PaymentLinkRequest, PaymentProviderError

class PaymentService:
    """Business logic for payment operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payment_request(
        self,
        workspace: Workspace,
        appointment: Appointment,
        customer_email: str,
    ) -> PaymentTransaction:
        """
        Create payment request and generate payment link.

        Args:
            workspace: Therapist's workspace
            appointment: Appointment to create payment for
            customer_email: Client's email address

        Returns:
            PaymentTransaction record with payment link
        """

        # Get payment provider
        try:
            provider = get_payment_provider(workspace)
        except PaymentProviderError as e:
            raise ValueError(f"Payment provider not configured: {e}")

        # Determine amount (from appointment service price or custom)
        amount = appointment.payment_amount or appointment.service.price
        currency = appointment.payment_currency or workspace.default_currency or "ILS"

        # Create payment link request
        link_request = PaymentLinkRequest(
            amount=amount,
            currency=currency,
            description=f"Appointment on {appointment.start_time.strftime('%Y-%m-%d %H:%M')}",
            customer_email=customer_email,
            customer_name=appointment.client.full_name,
            metadata={
                "workspace_id": str(workspace.id),
                "appointment_id": str(appointment.id),
            },
            success_url=f"https://pazpaz.app/payment/success",
            cancel_url=f"https://pazpaz.app/payment/cancelled",
        )

        # Call provider API
        try:
            link_response = await provider.create_payment_link(link_request)
        except PaymentProviderError as e:
            # Log error and create failed transaction
            transaction = PaymentTransaction(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                appointment_id=appointment.id,
                amount=amount,
                currency=currency,
                status="failed",
                provider=workspace.payment_provider,
                failed_at=datetime.now(timezone.utc),
                failure_reason=str(e),
            )
            self.db.add(transaction)
            await self.db.commit()
            raise

        # Create pending transaction
        transaction = PaymentTransaction(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            appointment_id=appointment.id,
            amount=amount,
            currency=currency,
            status="pending",
            provider=workspace.payment_provider,
            provider_transaction_id=link_response.provider_transaction_id,
            provider_payment_link=link_response.payment_link_url,
            created_at=datetime.now(timezone.utc),
            metadata={
                "customer_email": customer_email,
                "expires_at": (
                    link_response.expires_at.isoformat()
                    if link_response.expires_at
                    else None
                ),
            },
        )

        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)

        return transaction

    async def process_webhook(
        self,
        workspace: Workspace,
        payload: bytes,
        headers: dict,
    ) -> PaymentTransaction:
        """
        Process payment webhook from provider.

        Args:
            workspace: Workspace that owns this payment
            payload: Raw webhook body
            headers: HTTP headers (including signature)

        Returns:
            Updated PaymentTransaction
        """

        # Get provider and verify webhook
        provider = get_payment_provider(workspace)

        is_valid = await provider.verify_webhook(payload, headers)
        if not is_valid:
            raise ValueError("Invalid webhook signature")

        # Parse webhook data
        import json
        webhook_data = await provider.parse_webhook_payment(json.loads(payload))

        # Find existing transaction
        stmt = select(PaymentTransaction).where(
            PaymentTransaction.provider_transaction_id == webhook_data.provider_transaction_id,
            PaymentTransaction.workspace_id == workspace.id,
        )
        result = await self.db.execute(stmt)
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise ValueError(f"Transaction not found: {webhook_data.provider_transaction_id}")

        # Update transaction status
        transaction.status = webhook_data.status

        if webhook_data.status == "completed":
            transaction.completed_at = webhook_data.completed_at

            # Update appointment payment status
            if transaction.appointment:
                transaction.appointment.payment_status = "paid"
                transaction.appointment.payment_date = webhook_data.completed_at

        elif webhook_data.status == "failed":
            transaction.failed_at = datetime.now(timezone.utc)
            transaction.failure_reason = webhook_data.failure_reason

        await self.db.commit()
        await self.db.refresh(transaction)

        return transaction
```

#### API Endpoints

```python
# src/pazpaz/api/v1/payments.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
import uuid

from pazpaz.db import get_db
from pazpaz.dependencies import get_current_workspace
from pazpaz.models import Workspace, Appointment, PaymentTransaction
from pazpaz.services.payment_service import PaymentService

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

class CreatePaymentRequestRequest(BaseModel):
    appointment_id: uuid.UUID
    customer_email: EmailStr

class PaymentTransactionResponse(BaseModel):
    id: uuid.UUID
    appointment_id: uuid.UUID | None
    amount: str  # Decimal as string
    currency: str
    status: str
    provider: str
    payment_link: str | None
    created_at: str
    completed_at: str | None

@router.post("/create", response_model=PaymentTransactionResponse)
async def create_payment_request(
    request: CreatePaymentRequestRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a payment request and generate payment link.

    Sends email to client with payment link.
    """

    # Fetch appointment (with workspace isolation)
    appointment = await db.get(Appointment, request.appointment_id)
    if not appointment or appointment.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Create payment request
    service = PaymentService(db)
    try:
        transaction = await service.create_payment_request(
            workspace=workspace,
            appointment=appointment,
            customer_email=request.customer_email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # TODO: Send email with payment link

    return PaymentTransactionResponse(
        id=transaction.id,
        appointment_id=transaction.appointment_id,
        amount=str(transaction.amount),
        currency=transaction.currency,
        status=transaction.status,
        provider=transaction.provider,
        payment_link=transaction.provider_payment_link,
        created_at=transaction.created_at.isoformat(),
        completed_at=(
            transaction.completed_at.isoformat()
            if transaction.completed_at
            else None
        ),
    )

@router.post("/webhook/{provider}")
async def payment_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook endpoint for payment provider callbacks.

    Provider sends payment status updates here.
    """

    # Get raw body and headers
    payload = await request.body()
    headers = dict(request.headers)

    # Extract workspace from metadata (provider-specific)
    # TODO: Implement workspace lookup from webhook payload

    # Process webhook
    service = PaymentService(db)
    try:
        transaction = await service.process_webhook(
            workspace=workspace,  # TODO: Get from payload
            payload=payload,
            headers=headers,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "success", "transaction_id": str(transaction.id)}
```

#### Frontend Changes

**Payment Settings (Workspace Configuration):**
```vue
<!-- src/components/settings/PaymentSettings.vue -->
<template>
  <div class="payment-settings">
    <h2>Payment Settings</h2>

    <!-- Provider Selection -->
    <div class="form-group">
      <label>Payment Provider</label>
      <select v-model="settings.provider">
        <option value="">None (Manual tracking only)</option>
        <option value="meshulam">Meshulam (Israel)</option>
        <option value="stripe">Stripe (US)</option>
      </select>
    </div>

    <!-- Provider Configuration (conditional) -->
    <div v-if="settings.provider === 'meshulam'" class="provider-config">
      <h3>Meshulam Configuration</h3>
      <input v-model="settings.config.api_key" type="password" placeholder="API Key" />
      <input v-model="settings.config.terminal_id" placeholder="Terminal ID" />
      <input v-model="settings.config.webhook_secret" type="password" placeholder="Webhook Secret" />
    </div>

    <!-- Auto-Send Settings -->
    <div class="form-group">
      <label>
        <input v-model="settings.auto_send" type="checkbox" />
        Automatically send payment requests
      </label>
    </div>

    <div v-if="settings.auto_send" class="form-group">
      <label>Send Timing</label>
      <select v-model="settings.send_timing">
        <option value="immediately">Immediately after appointment</option>
        <option value="end_of_day">End of day (6 PM)</option>
        <option value="end_of_month">End of month</option>
      </select>
    </div>

    <button @click="saveSettings">Save Settings</button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()

const settings = ref({
  provider: '',
  config: {},
  auto_send: false,
  send_timing: 'immediately',
})

async function saveSettings() {
  await workspaceStore.updatePaymentSettings(settings.value)
  // Show success toast
}

onMounted(async () => {
  const workspace = await workspaceStore.fetchCurrent()
  settings.value = {
    provider: workspace.payment_provider || '',
    config: workspace.payment_provider_config || {},
    auto_send: workspace.payment_auto_send || false,
    send_timing: workspace.payment_send_timing || 'immediately',
  }
})
</script>
```

**Send Payment Request (Appointment Detail):**
```vue
<!-- src/components/appointments/AppointmentPayment.vue -->
<template>
  <div class="appointment-payment">
    <h3>Payment</h3>

    <!-- Payment Status Badge -->
    <div class="payment-status">
      <span :class="['badge', statusClass]">
        {{ appointment.payment_status }}
      </span>
    </div>

    <!-- Send Payment Request Button -->
    <button
      v-if="canSendPaymentRequest"
      @click="sendPaymentRequest"
      :disabled="sending"
    >
      {{ sending ? 'Sending...' : 'Send Payment Request' }}
    </button>

    <!-- Payment Link (if exists) -->
    <div v-if="latestTransaction?.payment_link" class="payment-link">
      <label>Payment Link:</label>
      <input
        :value="latestTransaction.payment_link"
        readonly
        @click="copyToClipboard"
      />
    </div>

    <!-- Payment History -->
    <div v-if="transactions.length > 0" class="payment-history">
      <h4>Payment History</h4>
      <ul>
        <li v-for="txn in transactions" :key="txn.id">
          {{ txn.created_at }} - {{ txn.status }} - {{ txn.amount }} {{ txn.currency }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePaymentStore } from '@/stores/payment'
import type { Appointment, PaymentTransaction } from '@/types'

const props = defineProps<{
  appointment: Appointment
}>()

const paymentStore = usePaymentStore()
const sending = ref(false)
const transactions = ref<PaymentTransaction[]>([])

const latestTransaction = computed(() => transactions.value[0])

const canSendPaymentRequest = computed(() => {
  return (
    props.appointment.payment_status === 'unpaid' &&
    props.appointment.status === 'completed'
  )
})

const statusClass = computed(() => {
  const status = props.appointment.payment_status
  return {
    'unpaid': 'badge-warning',
    'paid': 'badge-success',
    'partially_paid': 'badge-info',
    'refunded': 'badge-secondary',
  }[status] || 'badge-default'
})

async function sendPaymentRequest() {
  sending.value = true
  try {
    const transaction = await paymentStore.createPaymentRequest({
      appointment_id: props.appointment.id,
      customer_email: props.appointment.client.email,
    })
    transactions.value.unshift(transaction)
    // Show success toast
  } catch (error) {
    // Show error toast
  } finally {
    sending.value = false
  }
}

function copyToClipboard() {
  navigator.clipboard.writeText(latestTransaction.value.payment_link)
  // Show "Copied!" toast
}

onMounted(async () => {
  transactions.value = await paymentStore.fetchTransactions(props.appointment.id)
})
</script>
```

#### Testing Requirements

**Unit Tests:**
- Payment provider implementations (mock HTTP calls)
- Payment service business logic
- Webhook signature verification
- Currency conversions (agorot ↔ ILS, cents ↔ USD)

**Integration Tests:**
- Create payment request (end-to-end)
- Process webhook (mock provider webhook)
- Update appointment payment status
- Workspace isolation (therapist A cannot access therapist B's payments)

**Manual Testing Checklist:**
- [ ] Configure Meshulam provider in workspace settings
- [ ] Send payment request for completed appointment
- [ ] Receive email with payment link
- [ ] Complete payment on Meshulam test environment
- [ ] Verify webhook updates payment status
- [ ] Check appointment shows "paid" status

#### Success Metrics

- **Adoption Rate:** % of therapists with manual tracking who enable automated payments
- **Completion Rate:** % of payment requests that result in successful payment
- **Time to Payment:** Average time from appointment completion to payment received
- **Error Rate:** % of payment requests that fail (API errors, invalid config)

**Decision Point:** If <50% of therapists enable automated payments after 2 months, investigate barriers (technical issues, trust, pricing).

---

### Phase 2: Tax Compliance & Financial Reporting (Weeks 8-12)

**Goal:** Enable therapists to generate tax-compliant receipts and aggregate payment data for accounting/tax purposes.

**Key Features:**
- ✅ Manual payment entry (cash, bank transfers, checks)
- ✅ Israeli tax receipt generation ("מס קבלה") with VAT breakdown
- ✅ Receipt PDF generation with therapist branding
- ✅ Financial reporting dashboard (monthly/quarterly revenue)
- ✅ Export to Excel/CSV for accountant
- ✅ Outstanding payments tracking

#### Week 8-9: Receipt Generation

**Database Schema Enhancements:**
```sql
-- Add business/tax details to Workspace (already in schema above)
-- Add receipt tracking to PaymentTransaction (already in schema above)

-- New table: tax_receipts (optional, for advanced tax compliance)
CREATE TABLE tax_receipts (
    id UUID PRIMARY KEY,
    workspace_id UUID REFERENCES workspaces(id),
    payment_transaction_id UUID REFERENCES payment_transactions(id),
    receipt_number VARCHAR(50) UNIQUE,
    receipt_date DATE,
    fiscal_year INTEGER,
    base_amount NUMERIC(10, 2),
    vat_amount NUMERIC(10, 2),
    total_amount NUMERIC(10, 2),
    pdf_url TEXT,
    -- Israel Tax Authority fields
    allocation_number VARCHAR(50),  -- For invoices >₪10,000
    tax_authority_status VARCHAR(20),
    -- Third-party integration
    external_invoice_id VARCHAR(255),  -- GreenInvoice/Morning ID
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Backend Implementation:**
```python
# Receipt generation service
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

async def generate_receipt_pdf(transaction: PaymentTransaction) -> str:
    """Generate PDF receipt and upload to S3."""
    workspace = transaction.workspace

    # Auto-increment receipt counter
    async with db.begin():
        workspace.receipt_counter += 1
        receipt_number = f"{datetime.now().year}-{workspace.receipt_counter:06d}"

    # Generate PDF
    pdf = canvas.Canvas(f"/tmp/receipt_{receipt_number}.pdf", pagesize=A4)

    # Therapist details
    pdf.drawString(100, 750, f"{workspace.business_name}")
    pdf.drawString(100, 730, f"Tax ID: {workspace.tax_id}")

    # Receipt details
    pdf.drawString(100, 700, f"Receipt #: {receipt_number}")
    pdf.drawString(100, 680, f"Date: {transaction.completed_at.strftime('%d/%m/%Y')}")

    # Financial breakdown
    if workspace.vat_registered:
        pdf.drawString(100, 620, f"Base Amount: ₪{transaction.base_amount:.2f}")
        pdf.drawString(100, 600, f"VAT (17%): ₪{transaction.vat_amount:.2f}")
        pdf.drawString(100, 580, f"Total: ₪{transaction.total_amount:.2f}")
    else:
        pdf.drawString(100, 620, f"Amount: ₪{transaction.total_amount:.2f}")
        pdf.drawString(100, 600, "VAT Exempt (פטור ממע\"מ)")

    pdf.save()

    # Upload to S3/MinIO
    pdf_url = await storage.upload_file(f"receipts/{receipt_number}.pdf", pdf)

    # Update transaction
    transaction.receipt_number = receipt_number
    transaction.receipt_issued = True
    transaction.receipt_issued_at = datetime.now(timezone.utc)
    transaction.receipt_pdf_url = pdf_url

    await db.commit()

    return pdf_url
```

**API Endpoints:**
```python
# Generate receipt for payment
POST /api/v1/payments/{transaction_id}/receipt
Response: {receipt_number, pdf_url}

# Download receipt PDF
GET /api/v1/receipts/{receipt_number}/download
Response: PDF file stream

# Resend receipt email to client
POST /api/v1/receipts/{receipt_number}/resend-email
```

#### Week 10-11: Financial Reporting & Manual Payments

**Financial Reports API:**
```python
GET /api/v1/workspaces/{workspace_id}/reports/revenue
Query params:
  ?start_date=2025-01-01
  &end_date=2025-12-31
  &group_by=month  # or 'week', 'quarter', 'year'

Response: {
  "total_revenue": 45000.00,
  "total_vat": 7650.00,
  "total_net": 37350.00,
  "by_period": [
    {"period": "2025-01", "revenue": 3500.00, "vat": 595.00, "net": 2905.00, "payment_count": 28},
    ...
  ],
  "by_payment_method": {
    "online_card": 38000.00,
    "cash": 5000.00,
    "bank_transfer": 2000.00
  },
  "outstanding": 1200.00  // Pending online payments
}

# Export to Excel
GET /api/v1/workspaces/{workspace_id}/reports/export?format=xlsx
Response: Excel file download with tabs: Summary, Monthly, Transactions
```

**Manual Payment Entry:**
```python
# Add manual payment (cash, bank transfer, check)
POST /api/v1/appointments/{appointment_id}/manual-payment
Body: {
  "total_amount": 150.00,
  "payment_method": "cash",  # or 'bank_transfer', 'check'
  "payment_date": "2025-10-29",
  "notes": "Client paid in cash at end of session",
  "vat_included": true  # If workspace is VAT-registered
}

# Creates PaymentTransaction with:
# - provider = "manual"
# - status = "completed"
# - base_amount = 128.21 (if VAT-registered: total / 1.17)
# - vat_amount = 21.79
# - total_amount = 150.00
```

**Frontend: Financial Dashboard**
```vue
<template>
  <div class="financial-dashboard">
    <h2>Financial Reports</h2>

    <DateRangePicker v-model="dateRange" />
    <button @click="exportToExcel">Export to Excel</button>

    <div class="summary-cards">
      <Card title="Total Revenue" :value="`₪${totalRevenue}`" />
      <Card title="Paid Sessions" :value="paidCount" />
      <Card title="Outstanding" :value="`₪${outstanding}`" />
    </div>

    <RevenueChart :data="revenueByMonth" />
    <PaymentMethodBreakdown :data="byPaymentMethod" />
    <TransactionTable :transactions="transactions" />
  </div>
</template>
```

#### Week 12: Testing & Polish

**Testing Checklist:**
- [ ] Generate receipt for online payment
- [ ] Generate receipt for manual cash payment
- [ ] VAT calculation correct (17% for registered, 0% for exempt)
- [ ] Receipt PDF includes therapist branding
- [ ] Receipt counter increments correctly
- [ ] Export to Excel includes all transactions
- [ ] Financial reports match raw transaction data
- [ ] Manual payment entry updates appointment status

**Success Metrics:**
- **Receipt Generation:** >90% of paid appointments have receipt generated
- **Manual Payment Usage:** >40% of therapists add at least 1 manual payment
- **Export Usage:** >60% of therapists export revenue report at least quarterly
- **Reporting Accuracy:** 100% match between exported data and database

---

### Phase 3: Advanced Tax Integration (Optional, Future)

**Status:** Not in current implementation scope (Phases 0-3)
**Goal:** Full Israeli Tax Authority compliance via third-party invoice service integration.

**Recommendation:** Integrate with any of: **GreenInvoice**, **Morning**, **Ness**, or other Israeli invoice services

**Why Third-Party Service?**
- ✅ They handle all Israel Tax Authority submission
- ✅ Allocation numbers (for >₪10K invoices) automated
- ✅ Accountants already use these tools (many therapists have existing accounts)
- ✅ Lower legal risk (they ensure compliance)
- ✅ Faster implementation (1-2 weeks vs 3 months custom)

**Architecture Already Supports This:**
- ✅ Database schema includes `tax_service_provider` and `tax_service_config` (workspace level)
- ✅ Database schema includes `external_invoice_id` and `external_invoice_url` (receipt level)
- ✅ Can integrate with ANY invoice service that has an API
- ✅ Therapists can use whatever service they already have (GreenInvoice, Morning, Ness, etc.)

**Integration Approach:**
```python
# When payment completed, sync to GreenInvoice API
async def sync_to_greeninvoice(transaction: PaymentTransaction):
    client = GreenInvoiceClient(api_key=workspace.greeninvoice_api_key)

    invoice = await client.create_invoice(
        client_name=transaction.appointment.client.name,
        amount=transaction.total_amount,
        vat_exempt=not workspace.vat_registered,
        description="Therapy session"
    )

    # Store external invoice ID
    transaction.metadata["greeninvoice_invoice_id"] = invoice.id
    await db.commit()
```

**Phase 3 Features:**
- Full tax authority submission automation
- CPA/accountant dashboard access
- Multi-year tax reporting
- Automatic allocation numbers for large invoices
- VAT returns assistance

---

## Architecture Design

### Data Flow Diagrams

#### Payment Request Flow
```
Therapist                 PazPaz Backend           Payment Provider        Client
    |                           |                         |                    |
    |  1. Mark appointment      |                         |                    |
    |     as completed          |                         |                    |
    |-------------------------->|                         |                    |
    |                           |                         |                    |
    |                           | 2. Create payment       |                    |
    |                           |    request              |                    |
    |                           |------------------------>|                    |
    |                           |                         |                    |
    |                           | 3. Payment link         |                    |
    |                           |<------------------------|                    |
    |                           |                         |                    |
    |                           | 4. Email with link      |                    |
    |                           |------------------------------------------>|
    |                           |                         |                    |
    |                           |                         | 5. Click link      |
    |                           |                         |<-------------------|
    |                           |                         |                    |
    |                           |                         | 6. Enter card      |
    |                           |                         |    details         |
    |                           |                         |<-------------------|
    |                           |                         |                    |
    |                           | 7. Webhook: paid        |                    |
    |                           |<------------------------|                    |
    |                           |                         |                    |
    | 8. Notification: paid     |                         |                    |
    |<--------------------------|                         |                    |
```

#### Webhook Processing Flow
```
Payment Provider          PazPaz Backend              Database
    |                           |                         |
    | 1. POST /webhook          |                         |
    |-------------------------->|                         |
    |                           |                         |
    |                           | 2. Verify signature     |
    |                           |                         |
    |                           | 3. Parse payload        |
    |                           |                         |
    |                           | 4. Find transaction     |
    |                           |------------------------>|
    |                           |                         |
    |                           | 5. Transaction record   |
    |                           |<------------------------|
    |                           |                         |
    |                           | 6. Update status        |
    |                           |------------------------>|
    |                           |                         |
    |                           | 7. Update appointment   |
    |                           |------------------------>|
    |                           |                         |
    | 8. 200 OK                 |                         |
    |<--------------------------|                         |
```

### Database Schema (ERD)

```
┌─────────────────────┐         ┌─────────────────────┐
│   Workspace         │         │   Appointment       │
├─────────────────────┤         ├─────────────────────┤
│ id                  │         │ id                  │
│ name                │         │ workspace_id (FK)   │
│ ...                 │         │ client_id (FK)      │
│ payment_provider    │         │ ...                 │
│ payment_provider_   │         │ payment_status      │
│   config (JSONB)    │         │ payment_amount      │
│ payment_auto_send   │         │ payment_currency    │
│ payment_send_timing │         │ payment_method      │
└──────────┬──────────┘         │ payment_date        │
           │                     │ payment_notes       │
           │                     └──────────┬──────────┘
           │                                │
           │                                │
           │                     ┌──────────▼──────────┐
           │                     │ PaymentTransaction  │
           │                     ├─────────────────────┤
           │                     │ id                  │
           └─────────────────────┤ workspace_id (FK)   │
                                 │ appointment_id (FK) │
                                 │ amount              │
                                 │ currency            │
                                 │ status              │
                                 │ provider            │
                                 │ provider_txn_id     │
                                 │ provider_link       │
                                 │ created_at          │
                                 │ completed_at        │
                                 │ failed_at           │
                                 │ failure_reason      │
                                 │ metadata (JSONB)    │
                                 └─────────────────────┘
```

### Key Design Decisions

#### 1. Why separate `PaymentTransaction` table?

**Rationale:**
- Appointments can have multiple payment attempts (failed then succeeded)
- Refunds create new transaction records (negative amount)
- Immutable audit trail for financial compliance
- Easier to generate financial reports

**Alternative (rejected):** Store all payment data in `Appointment` table
- **Cons:** Can't track payment history, can't handle multiple attempts

#### 2. Why provider abstraction layer?

**Rationale:**
- Geographic flexibility (Israel uses Meshulam, US uses Stripe)
- Easy to add new providers without refactoring business logic
- Testability (can mock providers in unit tests)

**Alternative (rejected):** Hard-code Meshulam initially, add Stripe later
- **Cons:** Requires major refactoring when adding second provider

#### 3. Why workspace-level payment configuration?

**Rationale:**
- Each therapist chooses their own payment provider
- Multi-tenant SaaS (thousands of therapists, different providers)
- Compliance (each therapist's payment data stays isolated)

**Alternative (rejected):** Global payment provider for all therapists
- **Cons:** Doesn't work for multi-country deployment

#### 4. Why store payment links in database?

**Rationale:**
- Therapist can resend link if client loses email
- Can track link expiration
- Audit trail (when was link generated?)

**Alternative (rejected):** Generate new link each time
- **Cons:** Creates duplicate transactions, harder to track

---

## Security & Compliance

### HIPAA Considerations

**PHI vs Non-PHI in Payments:**

| Data Element | Is PHI? | Storage Strategy |
|--------------|---------|------------------|
| Payment amount | ❌ No | Store in plaintext |
| Client name | ✅ Yes | Already encrypted (existing PHI encryption) |
| Client email | ✅ Yes | Already encrypted |
| Appointment details | ✅ Yes | Already encrypted (SOAP notes) |
| Treatment description | ✅ Yes | Send generic description to provider |

**Payment Provider Integration:**
- ✅ **DO:** Send generic descriptions ("Therapy session on 2025-10-29")
- ❌ **DON'T:** Send treatment details ("Lower back pain massage with hot stones")

**Stripe BAA Requirement:**
- Must sign Stripe Business Associate Agreement for US deployment
- [https://stripe.com/legal/baa](https://stripe.com/legal/baa)

### PCI Compliance

**Strategy:** **Never touch card data**
- Use provider-hosted payment pages (Meshulam Payment Page, Stripe Payment Links)
- PazPaz never receives or stores credit card numbers
- No PCI compliance audit required (out of scope)

**What we store:**
- ✅ Payment status (paid/unpaid)
- ✅ Provider transaction ID (tokenized reference)
- ✅ Payment link URL
- ❌ Credit card numbers
- ❌ CVV codes
- ❌ Card expiration dates

### Encryption & Secrets

**Payment Provider Credentials:**
- Store API keys in `workspace.payment_provider_config` (JSONB)
- **Must encrypt** using existing PHI encryption system
- Encryption key managed via `ENCRYPTION_MASTER_KEY` env var

**Example encrypted config:**
```python
# Before encryption
config = {
    "api_key": "sk_live_abc123...",
    "terminal_id": "12345",
    "webhook_secret": "whsec_xyz789..."
}

# After encryption (stored in database)
encrypted_config = encrypt_json(config)  # Uses PHI encryption
```

**Webhook Signature Verification:**
- **Always verify** webhook signatures before processing
- Prevents webhook spoofing attacks
- Use `hmac.compare_digest()` to prevent timing attacks

### Audit Logging

**Payment Events to Log:**
- Payment request created (who, when, amount)
- Payment link generated (provider, transaction ID)
- Payment completed (amount, payment method)
- Payment failed (reason)
- Refund issued (amount, reason)
- Payment configuration changed (provider, auto-send settings)

**Audit Log Format:**
```python
{
    "event_type": "payment.completed",
    "workspace_id": "uuid",
    "user_id": "uuid",  # Therapist
    "appointment_id": "uuid",
    "transaction_id": "uuid",
    "amount": "150.00",
    "currency": "ILS",
    "provider": "meshulam",
    "timestamp": "2025-10-29T14:32:00Z"
}
```

---

## Risk Analysis

### Technical Risks

#### Risk 1: Payment Provider API Changes
**Likelihood:** Medium
**Impact:** High
**Mitigation:**
- Abstract provider interface (already planned)
- Version provider implementations (e.g., `MesshulamV1Provider`, `MesshulamV2Provider`)
- Monitor provider changelogs
- Automated integration tests that fail if API changes

#### Risk 2: Webhook Delivery Failures
**Likelihood:** Medium (network issues, downtime)
**Impact:** High (payment completed but status not updated)
**Mitigation:**
- Implement webhook retry queue (Redis-backed)
- Polling fallback (check payment status every 24h for "pending" transactions)
- Idempotency keys to prevent duplicate processing
- Alert therapist if payment pending >48h

#### Risk 3: Currency Conversion Errors
**Likelihood:** Low
**Impact:** High (incorrect charge amounts)
**Mitigation:**
- Store amounts in original currency + converted amount
- Use provider's currency conversion (don't calculate ourselves)
- Round to 2 decimal places for display
- Unit tests for currency conversions (agorot ↔ ILS, cents ↔ USD)

#### Risk 4: Provider Credential Exposure
**Likelihood:** Low
**Impact:** Critical (financial fraud)
**Mitigation:**
- Encrypt `payment_provider_config` using PHI encryption
- Never log API keys or webhook secrets
- Rotate credentials if breach suspected
- Restrict API access (workspace owners only)

### Business Risks

#### Risk 5: Low Adoption (Therapists Don't Use Payments)
**Likelihood:** Medium
**Impact:** High (wasted development effort)
**Mitigation:**
- **Opt-in architecture** (see [Feature Flag Design](/docs/PAYMENT_FEATURE_FLAG_DESIGN.md))
- Feature entirely optional - defaults to disabled
- No impact on non-payment users (PazPaz works exactly as before)
- Target metric: >40% of therapists enable payments within 2 months
- User interviews to understand barriers

#### Risk 6: Therapists Don't Trust Online Payments
**Likelihood:** Medium (especially in Israel)
**Impact:** Medium
**Mitigation:**
- Education: Blog posts on payment security
- Trust signals: "Secured by Meshulam" badges
- Testimonials from early adopters
- Support for cash/bank transfers (manual tracking)

#### Risk 7: Payment Provider Pricing Changes
**Likelihood:** Medium
**Impact:** Medium (affects monetization strategy)
**Mitigation:**
- Monitor provider pricing regularly
- Have backup provider options (Meshulam → PayPlus)
- Build multi-provider support from day 1
- Pass-through model (therapist pays provider directly)

### Compliance Risks

#### Risk 8: HIPAA Violation (PHI Exposure to Provider)
**Likelihood:** Low
**Impact:** Critical (legal liability)
**Mitigation:**
- Send only generic descriptions to payment providers
- Sign Stripe BAA before US launch
- Audit payment request payloads (automated tests)
- Legal review of provider data sharing

#### Risk 9: Tax Compliance (Israel Receipt Requirements)
**Likelihood:** Medium
**Impact:** High (legal issues for therapists)
**Mitigation:**
- Auto-generate tax receipts ("מס קבלה") in Phase 2
- Consult Israeli tax accountant on receipt format
- Make receipts downloadable/printable
- Support both tax receipt and regular invoice formats

---

## Success Metrics

### Phase 1 (Automated Payments)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Feature Adoption | >40% | % of active therapists who enable automated payments |
| Payment Completion Rate | >70% | % of payment requests that result in successful payment |
| Time to Payment | <7 days | Average time from appointment completion to payment received |
| Error Rate | <5% | % of payment requests that fail (API errors, invalid config) |
| Support Tickets | <2% | % of payment transactions that result in support ticket |
| Feature Awareness | >80% | % of therapists who view payment settings page |

### Phase 2 (Advanced Features)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Receipt Downloads | >80% | % of paid appointments where receipt is downloaded |
| Payment Reminders | <10% reminders sent | % of appointments that require overdue reminder |
| Analytics Usage | >60% | % of therapists with payments who view analytics dashboard |
| Refund Rate | <3% | % of payments that are refunded |

### Financial Metrics (Business)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Revenue per Therapist | +$10-15/month | Incremental revenue from payment tier |
| Churn Reduction | -5% | Difference in churn between therapists with/without payments |
| NPS Impact | +10 points | NPS increase for therapists using payment features |
| Customer Acquisition | +20% | Increase in signups mentioning payment features |

---

## Open Questions

### Technical Questions

1. **Invoice PDF Generation:**
   - Which library? (ReportLab, WeasyPrint, or external service like DocRaptor?)
   - Support for therapist logo upload?
   - Multi-language support (Hebrew RTL for Israeli invoices)?

2. **Email Delivery:**
   - Use existing email infrastructure or dedicated transactional email service?
   - Support for custom email templates (therapist branding)?
   - Handle email bounces/spam complaints?

3. **Currency Support:**
   - Support multiple currencies per workspace? (therapist treats both Israeli and US clients)
   - Or enforce single currency per workspace?
   - How to handle exchange rates?

4. **Webhook Endpoint:**
   - Single webhook endpoint for all providers (`/api/v1/payments/webhook/{provider}`)?
   - Or workspace-specific endpoints (`/api/v1/workspaces/{id}/webhook`)?
   - Security implications of each approach?

5. **Failed Payment Retry:**
   - Should PazPaz automatically retry failed payments?
   - Or leave it to therapist to manually resend link?
   - What's the retry policy? (immediately, 1 day later, 3 days later)

### Business Questions

6. **Pricing Model:**
   - Transaction fee (1-2% on top of provider fees)?
   - Feature tier ($15-25/month for unlimited payments)?
   - Hybrid model (low monthly fee + small transaction fee)?

7. **Provider Selection:**
   - Meshulam vs PayPlus vs Tranzila for Israel?
   - Which has best API, lowest fees, best support?
   - Any existing partnerships or referral programs?

8. **Competitive Positioning:**
   - Advertise "payment support" as primary feature or secondary/bonus?
   - Target therapists frustrated with SimplePractice/Jane App?
   - Pricing strategy vs competitors?

9. **International Expansion:**
   - Which markets after Israel and US? (Canada, UK, Australia?)
   - Local payment providers for each market?
   - Or use global providers (Stripe, PayPal)?

10. **Client Experience:**
    - Should clients be able to view payment history?
    - Client portal for downloading receipts?
    - Or keep all payment management therapist-side only?

### Legal/Compliance Questions

11. **Israeli Tax Requirements:**
    - Exact format for "מס קבלה" (tax receipt)?
    - VAT (מע"מ) handling for therapist businesses?
    - Does PazPaz need to report payments to Israeli tax authority?

12. **HIPAA BAA with Payment Providers:**
    - Does Meshulam offer BAA for healthcare?
    - Stripe BAA terms and restrictions?
    - Any limitations on PHI in payment descriptions?

13. **Financial Regulations:**
    - Does PazPaz need money transmitter license?
    - Or does pass-through model avoid this? (payment goes directly to therapist)
    - What about PCI compliance if we add "save card" feature later?

14. **Refund Policy:**
    - Should PazPaz enforce refund policy on therapists?
    - Or let each therapist set their own policy?
    - Dispute handling between therapist and client?

### User Experience Questions

15. **Payment Timing:**
    - What % of therapists want immediate payment requests?
    - What % want end-of-month invoicing?
    - Should we support both in Phase 2 or pick one?

16. **Client Communication:**
    - Who sends payment emails? (PazPaz or therapist's email?)
    - Email from `noreply@pazpaz.app` or `therapist@clinic.com`?
    - Support for custom email templates?

17. **Failed Payment Handling:**
    - Should therapist be notified immediately when payment fails?
    - Or batch notifications (daily digest)?
    - Should we show client why payment failed? (insufficient funds, card declined)

18. **Multi-Session Packages:**
    - Do therapists commonly sell packages (10 sessions for $800)?
    - Should we support prepaid packages in Phase 3?
    - Or is pay-per-session sufficient?

---

## Next Steps

### Immediate Actions (Week 1)

1. **Product Validation:**
   - [ ] User interviews with 5-10 therapists on payment needs
   - [ ] Survey current users: "Would you use payment tracking?"
   - [ ] Analyze competitor payment features (SimplePractice, Jane App)

2. **Technical Validation:**
   - [ ] Research Meshulam API documentation
   - [ ] Research PayPlus API documentation
   - [ ] Compare transaction fees (Meshulam vs PayPlus vs Tranzila)
   - [ ] Test Meshulam sandbox environment

3. **Legal/Compliance:**
   - [ ] Consult Israeli tax accountant on receipt requirements
   - [ ] Review Stripe BAA terms for future US expansion
   - [ ] Document PHI handling in payment flows

4. **Design:**
   - [ ] Sketch payment settings UI
   - [ ] Sketch payment request flow (therapist perspective)
   - [ ] Sketch payment link page (client perspective)

### Decision Points

**Decision 1 (Week 1):** Proceed with implementation?
- **If:** >70% of surveyed therapists express interest in automated payment features
- **Then:** Start Phase 1 implementation (automated payments)
- **Else:** Deprioritize payments, focus on other features

**Decision 2 (Week 2):** Which provider for Israel launch?
- **If:** Meshulam has better API and lower fees than PayPlus
- **Then:** Build Meshulam integration first
- **Else:** Build PayPlus integration

**Decision 3 (Month 2):** Proceed with Phase 2 (Advanced Features)?
- **If:** >40% of therapists enable automated payments AND >70% payment completion rate
- **Then:** Prioritize advanced features (analytics, receipts, reminders)
- **Else:** Focus on improving Phase 1 adoption (marketing, UX improvements, support)

---

## Appendix

### Related Documentation

**Internal Documents:**
- **[Feature Flag Design](/docs/PAYMENT_FEATURE_FLAG_DESIGN.md)** - Detailed opt-in architecture, UI mockups, conditional rendering
- **[Tax-Compliant Schema](/docs/PAYMENT_SCHEMA_TAX_COMPLIANT.sql)** - Complete database schema with triggers, views, indexes
- **[2025-2026 Research](/docs/PAYMENT_INTEGRATION_RESEARCH_2025.md)** - Deep research on payment best practices, security, PCI DSS 4.0.1

**Key Concepts:**
- **Opt-In Architecture:** Payments disabled by default, no impact on existing users
- **Feature Flag:** `workspace.payment_provider` determines if payment UI is shown
- **Conditional Fields:** Payment fields in schema but nullable (no migration when enabling/disabling)
- **Workspace Isolation:** Each therapist controls their own payment settings

### Useful Links

**Payment Providers:**
- **PayPlus:** https://docs.payplus.co.il/ (recommended for Israel)
- **Meshulam (Grow):** https://grow-il.readme.io/ (alternative for Israel)
- **Stripe:** https://stripe.com/docs/api (for US expansion)
- Stripe BAA: https://stripe.com/legal/baa

**Competitors:**
- SimplePractice Payments: https://www.simplepractice.com/payments
- Jane App Payments: https://jane.app/payments
- Cliniko Payments: https://www.cliniko.com/payments

**Compliance:**
- HIPAA Payment Guidance: https://www.hhs.gov/hipaa/for-professionals/faq/3065/index.html
- PCI DSS 4.0.1: https://www.pcisecuritystandards.org/

---

**Document History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2025-10-29 | Product Team | Initial draft |
| 1.0 | 2025-10-30 | Product Team | Added opt-in architecture, tax compliance phase, feature flag design reference |

---

*This is a living document. Please update as decisions are made and implementation progresses.*
