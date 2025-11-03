# Grow Payment Integration - Implementation Plan

**Project:** PazPaz Phase 2 Payment Integration
**Payment Gateway:** Grow (formerly Meshulam)
**Architecture:** Marketplace model (PazPaz master merchant)
**Migration Type:** Clean cut-over (NO backwards compatibility)
**Status:** Ready for implementation

---

## Table of Contents

- [Overview](#overview)
- [Architecture Summary](#architecture-summary)
- [Database Migration](#database-migration)
- [Backend Implementation](#backend-implementation)
- [Frontend Implementation](#frontend-implementation)
- [Testing](#testing)
- [Deployment](#deployment)
- [Post-Launch](#post-launch)

---

## Overview

### Project Goals

1. **Replace manual payment tracking** with automated Grow payment gateway integration
2. **Zero friction for therapists** - PazPaz is master merchant, therapists are sub-accounts
3. **Automated payment status updates** via Grow webhooks
4. **Clean architecture** - Provider abstraction allows future payment gateways

### Migration Strategy

**CLEAN CUT-OVER:**
- NO backwards compatibility
- Remove all Phase 1 manual tracking code
- Migrate payment status values: `not_paid` → `unpaid`, `payment_sent` → `pending`
- Preserve historical data in audit logs

### Key Decisions

- ✅ Marketplace model (PazPaz = master merchant)
- ✅ Free MVP (no platform commission fees initially)
- ✅ Grow API cost: ₪585/month (from testing phase)
- ✅ Break-even: 6 paying therapists @ ₪149/month

### Resources

- **Grow API Documentation:** https://grow-il.readme.io/reference/
  - **API Introduction:** https://grow-il.readme.io/reference/introduction
  - **Create Payment Link:** https://grow-il.readme.io/reference/post_api-light-server-1-0-createpaymentlink
  - **Get Payment Link Info:** https://grow-il.readme.io/reference/post_api-light-server-1-0-getpaymentlinkinfo-2
  - **Webhooks Overview:** https://grow-il.readme.io/docs/overview-7
  - **Server Callback (Payment Links):** https://grow-il.readme.io/reference/server-respons-copy
- **Research Document:** `/GROW_PAYMENT_INTEGRATION_RESEARCH.md`
- **Database Schema Plan:** Completed by database-architect specialist
- **Backend Architecture:** Completed by fullstack-backend-specialist
- **Frontend Migration:** Completed by fullstack-frontend-specialist

### Grow API Endpoints

**Production:**
- Base URL: `https://secure.meshulam.co.il/api/light/server/1.0`
- Credentials provided after website review approval

**Sandbox/Testing:**
- Base URL: `https://sandbox.meshulam.co.il/api/light/server/1.0`
- Test card numbers: `4580458045804580`, `4580000000000000`, `4580111111111121`
- ⚠️ Bit/GooglePay/ApplePay use REAL transactions (no sandbox)

**Key Endpoints:**
- `POST /CreatePaymentLink` - Create payment link
- `POST /GetPaymentLinkInfo` - Get payment link status
- `POST /UpdatePaymentLink` - Update existing payment link
- Webhook callback: `POST {notifyUrl}` (configured by PazPaz)

---

## Architecture Summary

### System Flow

```
1. Therapist enables Grow in Settings
   → Stores grow_user_id, grow_page_code in workspace

2. Therapist sends payment request
   → Backend calls Grow API
   → Creates payment link
   → Stores grow_transaction_code, grow_payment_link
   → Sets payment_status = 'pending'
   → Emails payment link to client

3. Client pays via Grow payment page
   → Grow sends webhook to PazPaz
   → Backend verifies signature
   → Updates payment_status = 'paid'
   → Sets payment_completed_at timestamp

4. If payment fails
   → Grow sends webhook
   → Backend updates payment_status = 'failed'
   → Stores payment_failure_reason
```

### Tech Stack

- **Backend:** FastAPI, SQLAlchemy async, PostgreSQL 16, httpx
- **Frontend:** Vue 3 Composition API, TypeScript, Tailwind CSS
- **Payment Provider:** Grow API (REST + Webhooks)
- **Authentication:** x-api-key header, webhook callbacks (signature method TBD)

---

## Grow API Reference

### API Authentication

**Required Headers:**
```http
POST /api/light/server/1.0/CreatePaymentLink HTTP/1.1
Host: sandboxapi.grow.link
x-api-key: {YOUR_API_KEY}
Content-Type: application/json
```

**Critical Requirements:**
- All requests MUST include `x-api-key` header
- All requests must originate from backend server only (never from client)
- Avoid special characters in API parameters

### Create Payment Link

**Documentation:** https://grow-il.readme.io/reference/post_api-light-server-1-0-createpaymentlink

**Endpoint:**
```http
POST /api/light/server/1.0/CreatePaymentLink
```

**Required Parameters:**
- `userId` (string) - Therapist's Grow account identifier (provided during onboarding)
- `pageCode` (string) - Payment page configuration code (provided by Grow)
- `sum` (number) - Payment amount in ILS
- `notifyUrl` (string) - Webhook URL for payment status callbacks

**Optional Parameters:**
- `companyCommission` (number) - Platform fee in ILS (set to 0 for MVP)
- `description` (string) - Payment description for client
- `payerEmail` (string) - Client email for receipts
- `payerPhone` (string) - Client phone number
- `successUrl` (string) - Redirect URL after successful payment
- `cancelUrl` (string) - Redirect URL if payment cancelled
- `customFields` (object) - Custom metadata (workspace_id, appointment_id)
- `productData` (array) - Line items for invoice

**Example Request:**
```python
import httpx
from decimal import Decimal

async def create_payment_link(
    api_key: str,
    user_id: str,
    page_code: str,
    amount: Decimal,
    notify_url: str,
    customer_email: str,
    metadata: dict,
    use_sandbox: bool = False,
) -> dict:
    """Create payment link via Grow API.

    Args:
        api_key: Platform API key (x-api-key header)
        user_id: Therapist's Grow user ID
        page_code: Payment page configuration code
        amount: Payment amount in ILS
        notify_url: Webhook callback URL (e.g., https://pazpaz.health/api/v1/webhooks/grow)
        customer_email: Client email for receipts
        metadata: Custom metadata (workspace_id, appointment_id)
        use_sandbox: Use sandbox environment (default: False for production)

    Returns:
        dict with payment link URL and transaction identifiers
    """

    # Use correct base URL for environment
    base_url = (
        "https://sandbox.meshulam.co.il/api/light/server/1.0"
        if use_sandbox
        else "https://secure.meshulam.co.il/api/light/server/1.0"
    )
    url = f"{base_url}/CreatePaymentLink"

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "userId": user_id,
        "pageCode": page_code,
        "sum": float(amount),  # Grow expects float, not Decimal
        "description": f"PazPaz appointment payment - {metadata.get('appointment_id', 'N/A')}",
        "payerEmail": customer_email,
        "notifyUrl": notify_url,
        "companyCommission": 0,  # No platform fee for MVP (will add later)
        "customFields": {
            "workspace_id": metadata.get("workspace_id"),
            "appointment_id": metadata.get("appointment_id"),
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()
        return response.json()
```

**Example Response:**
```json
{
  "err": false,
  "status": "success",
  "statusCode": "0",
  "url": "https://grow.link/payment/abc123xyz",
  "paymentLinkProcessId": "12345",
  "paymentLinkProcessToken": "token_abc123",
  "expiresAt": null
}
```

**Response Fields:**
- `err` (boolean) - Error flag (false = success)
- `status` (string) - Status message
- `statusCode` (string) - "0" = success, other values = error codes
- `url` (string) - Payment link URL to send to client
- `paymentLinkProcessId` (string) - Grow's internal transaction ID
- `paymentLinkProcessToken` (string) - Transaction token for future queries

**Note:** Payment link is valid for 10 minutes by default.

### Webhook Callback

**Documentation:** https://grow-il.readme.io/reference/server-respons-copy

**Endpoint:** `POST {notifyUrl}` (configured by PazPaz during payment link creation)

**Webhook Trigger:** Sent when transaction completes (payment successful or failed)

**Webhook Payload:**
```json
{
  "err": false,
  "status": "שולם",
  "statusCode": "2",
  "transactionId": "123456",
  "transactionToken": "token_xyz",
  "paymentLinkProcessId": "12345",
  "paymentLinkProcessToken": "token_abc123",
  "sum": 300.00,
  "paymentDate": "2025-11-03 14:30:00",
  "paymentType": "2",
  "fullName": "John Doe",
  "payerPhone": "0501234567",
  "payerEmail": "client@example.com",
  "cardSuffix": "4242",
  "cardBrand": "2",
  "cardType": "1",
  "cardExp": "12/27",
  "asmachta": "123456",
  "productData": [],
  "customFields": {
    "workspace_id": "abc-123",
    "appointment_id": "def-456"
  }
}
```

**Key Webhook Fields:**
- `statusCode` (string) - Payment status code:
  - `"2"` = Payment successful (שולם = paid)
  - `"0"` = Payment failed
  - Other codes TBD (contact Grow support)
- `transactionId` (string) - Unique transaction identifier
- `paymentLinkProcessId` (string) - Links to original payment request
- `sum` (number) - Amount paid
- `paymentDate` (string) - Payment timestamp (format: "YYYY-MM-DD HH:mm:ss")
- `customFields` (object) - Metadata passed during payment link creation

**Webhook Security:**
⚠️ **IMPORTANT:** Grow's webhook signature verification method is NOT documented in the public API reference. You MUST contact Grow support to obtain:
1. Webhook signature header name
2. Signature algorithm (likely HMAC-SHA256)
3. Signature verification process

**Recommended Implementation (placeholder until confirmed):**
```python
async def verify_grow_webhook(
    payload: bytes,
    headers: dict,
    webhook_secret: str,
) -> bool:
    """Verify Grow webhook signature.

    NOTE: This is a placeholder implementation.
    Contact Grow support for actual verification method.
    """
    # Expected header format (TBD by Grow):
    signature_header = headers.get("x-grow-signature") or headers.get("X-Grow-Signature")

    if not signature_header:
        logger.warning("Missing Grow webhook signature")
        return False

    # Compute HMAC-SHA256 signature (typical pattern)
    import hmac
    import hashlib

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(signature_header, expected_signature)
```

### Get Payment Link Info

**Documentation:** https://grow-il.readme.io/reference/post_api-light-server-1-0-getpaymentlinkinfo-2

**Endpoint:**
```http
POST /api/light/server/1.0/GetPaymentLinkInfo
```

**Use Case:** Query payment status if webhook delivery fails

**Request Parameters:**
- `userId` (string) - Therapist's Grow account ID
- `pageCode` (string) - Payment page code
- `paymentLinkProcessId` (string) - Transaction ID from CreatePaymentLink response

**Example Request:**
```python
async def get_payment_link_info(
    api_key: str,
    user_id: str,
    page_code: str,
    payment_link_process_id: str,
    use_sandbox: bool = False,
) -> dict:
    """Query payment link status.

    Use this endpoint to manually check payment status if webhook delivery fails.
    """

    # Use correct base URL for environment
    base_url = (
        "https://sandbox.meshulam.co.il/api/light/server/1.0"
        if use_sandbox
        else "https://secure.meshulam.co.il/api/light/server/1.0"
    )
    url = f"{base_url}/GetPaymentLinkInfo"

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    payload = {
        "userId": user_id,
        "pageCode": page_code,
        "paymentLinkProcessId": payment_link_process_id,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()
        return response.json()
```

### Error Handling

**HTTP Status Codes:**
- `200 OK` - Request processed (check `err` and `statusCode` in response body)
- `401 Unauthorized` - Invalid or missing x-api-key header
- `400 Bad Request` - Invalid parameters
- `500 Internal Server Error` - Grow API error

**Response Error Format:**
```json
{
  "err": true,
  "status": "error",
  "statusCode": "1001",
  "message": "Invalid userId"
}
```

**Common Error Codes (to be confirmed with Grow support):**
- `"1001"` - Invalid userId
- `"1002"` - Invalid pageCode
- `"1003"` - Invalid amount
- (Contact Grow for complete error code list)

### API Rate Limits

**Rate limits not documented.** Contact Grow support for:
- Requests per second/minute limits
- Burst limit policies
- Rate limit headers (if any)

### Webhook Retry Policy

**Retry policy not documented.** Contact Grow support for:
- Retry attempts (typical: 3-10 retries)
- Retry backoff strategy
- Maximum retry duration
- Webhook delivery timeout

---

## Pre-Implementation: Grow Support Contact Required

⚠️ **CRITICAL:** Before starting implementation, you MUST contact Grow support to clarify the following undocumented aspects:

### 1. Webhook Signature Verification
**Status:** ❌ NOT DOCUMENTED - BLOCKER

**Confirmed from Documentation Review:**
- Webhooks send transaction completion notifications to the `notifyUrl` parameter
- Documentation mentions that merchants should execute `ApproveTransaction` API call upon webhook receipt
- **NO information about signature verification is provided**

**Questions for Grow Support (CRITICAL):**
- What is the webhook signature header name? (e.g., `X-Grow-Signature`, `X-Signature`, etc.)
- What signature algorithm is used? (HMAC-SHA256, HMAC-SHA512, etc.)
- What is the signature format? (hex, base64, prefixed with algorithm name?)
- How is the webhook_secret obtained? (Is it the same as x-api-key or different?)
- Is there a test webhook endpoint for signature verification testing?

**Impact:** Without this information, webhook security cannot be implemented correctly, making the system vulnerable to fraudulent webhooks.

**Documentation References:**
- https://grow-il.readme.io/docs/overview-7 (Webhooks overview - no signature info)
- https://grow-il.readme.io/reference/server-respons-copy (Server callback - no signature info)

### 2. Production API Base URL
**Status:** ✅ DOCUMENTED - RESOLVED

**Production Base URL:** `https://secure.meshulam.co.il/api/light/server/1.0`

**Sandbox Base URL:** `https://sandbox.meshulam.co.il/api/light/server/1.0`

**Important Notes:**
- Production credentials (userId, pageCode, apiKey) are provided AFTER completing website review process
- Website review requirements include: active website, functioning payment page, contact info, terms & conditions, etc.
- Each environment has unique credentials (sandbox credentials ≠ production credentials)

**Documentation Reference:**
- https://grow-il.readme.io/reference/live-environment

### 3. Marketplace/Platform Model Confirmation
**Status:** ⚠️ PARTIALLY DOCUMENTED - NEEDS CLARIFICATION

**Confirmed from Documentation:**
- ✅ `companyCommission` parameter is confirmed and documented
- ✅ Platform can define commission amount per transaction (in ILS, excluding VAT)
- ✅ Each platform request requires unique `apiKey` identifier
- ❌ **NO information about programmatic userId (sub-merchant) creation**

**Questions for Grow Support:**
- How is therapist `userId` created? Is there a programmatic API endpoint? (e.g., `POST /CreateSubMerchant`)
- Or must therapists be onboarded manually through Grow dashboard?
- Can PazPaz create sub-merchant accounts via API?
- What information is required to create a new userId (business name, tax ID, bank details)?

**Impact:** This determines whether PazPaz can offer truly zero-friction therapist onboarding or if therapists must manually sign up with Grow.

**Documentation Reference:**
- https://grow-il.readme.io/reference/api-guidelines-for-platforms-system-integrators

### 4. Status Codes and Error Codes
**Status:** ✅ PARTIALLY DOCUMENTED - ERROR CODES AVAILABLE, WEBHOOK STATUS CODES MISSING

**Confirmed Error Codes (from documentation):**
- **403**: Missing X-API-KEY header
- **54**: Missing required fields (with parameter name)
- **109**: Validate transaction field accuracy
- **300**: Business not authorized for API service
- **701-719**: Payment link errors (expired, invalid, inactive page, etc.)
- **801**: Invalid business identification code (apiKey)
- **812**: Invalid company identification code
- **Complete list available at:** https://grow-il.readme.io/reference/errors

**Webhook Status Codes (from examples):**
- **"2"**: Payment successful (שולם = paid)
- **"0"**: Payment failed
- ❌ **Other status codes NOT documented** (what about "1", "3", "4", etc.?)

**Questions for Grow Support:**
- Complete list of webhook `statusCode` values and their meanings
- Are there pending/processing/refunded statuses? ("1", "3", "4", etc.)
- What status codes indicate partial payments or authorization holds?

**Documentation References:**
- https://grow-il.readme.io/reference/errors (Error codes)
- https://grow-il.readme.io/reference/server-respons-copy (Webhook payload examples)

### 5. Rate Limits and Retry Policies
**Status:** ❌ NOT DOCUMENTED - NEEDS CLARIFICATION

**Confirmed from Documentation Review:**
- Rate limits are NOT mentioned anywhere in the documentation
- Webhook retry policy is NOT documented
- No information about request throttling or concurrent request limits

**Questions for Grow Support:**
- API rate limits (requests per second/minute)
- Webhook retry policy (how many attempts, backoff strategy, retry intervals)
- Recommended concurrent request limits
- Are there burst limits vs sustained rate limits?
- What HTTP headers indicate rate limit status (X-RateLimit-Remaining, etc.)?

**Impact:** Without rate limit information, we risk exceeding limits during high-traffic periods or webhook storms.

### 6. Testing Environment
**Status:** ✅ DOCUMENTED - RESOLVED

**Sandbox Base URL:** `https://sandbox.meshulam.co.il/api/light/server/1.0`

**Test Card Numbers (for sandbox):**
- `4580458045804580` (regular transactions, also for failed multi-payment testing)
- `4580000000000000`
- `4580111111111121`

**Important Limitations:**
- ⚠️ **Bit, GooglePay, and ApplePay do NOT have sandbox environments**
- Transactions with these methods will be REAL transactions even in testing
- Only card-based payments can be fully tested in sandbox

**Credentials:**
- Each environment (sandbox and production) has unique `pageCode` and `userId`
- Sandbox credentials must be requested from Grow support
- Production credentials provided after website review approval

**Webhook Testing:**
- Documentation mentions `updateMyUrl` sandbox endpoint for simulating webhooks
- You can test webhooks with ngrok/localtunnel by providing your tunnel URL as `notifyUrl`

**Questions for Grow Support:**
- How to obtain sandbox credentials (test userId, pageCode, apiKey)?
- Is there a dedicated webhook testing tool beyond `updateMyUrl`?
- Can we test Bit payments in sandbox without real transactions?

**Documentation Reference:**
- https://grow-il.readme.io/reference/testing-environment

### Contact Information

**Grow Support:**
- Email: support@grow.co.il
- Phone: (from Grow website or direct contact)
- Onboarding process initiated

**Recommended Approach:**
1. Schedule call with Grow technical team (not just sales)
2. Share this implementation plan with them
3. Request detailed technical integration guide (if available)
4. Ask for code examples from other platform integrations (if they can share)

---

## Database Migration

### Phase 1: Create Alembic Migration

**File:** `/backend/alembic/versions/XXXX_migrate_to_grow_payments.py`

**Task 1.1:** Create migration file
- [ ] Generate migration: `cd backend && uv run alembic revision -m "migrate_to_grow_payments"`
- [ ] Implement upgrade() function
- [ ] Implement downgrade() function (for rollback safety)

**Task 1.2:** Drop Phase 1 columns (Workspace)
```python
def upgrade():
    # Drop Phase 1 workspace payment columns
    op.drop_column('workspaces', 'bank_account_details')
    op.drop_column('workspaces', 'payment_link_type')
    op.drop_column('workspaces', 'payment_link_template')
```

**Task 1.3:** Add Phase 2 columns (Workspace)
```python
    # Add Grow workspace columns
    op.add_column('workspaces', sa.Column('grow_user_id', sa.String(100), nullable=True))
    op.add_column('workspaces', sa.Column('grow_page_code', sa.String(100), nullable=True))
    op.add_column('workspaces', sa.Column('grow_webhook_key', sa.String(255), nullable=True))

    # Add index for grow_user_id lookups
    op.create_index('idx_workspaces_grow_user_id', 'workspaces', ['grow_user_id'],
                    postgresql_where=sa.text("grow_user_id IS NOT NULL"))
```

**Task 1.4:** Drop Phase 1 columns (Appointments)
```python
    # Drop Phase 1 appointment payment columns
    op.drop_column('appointments', 'payment_method')
    op.drop_column('appointments', 'payment_notes')
    op.drop_column('appointments', 'paid_at')
    op.drop_column('appointments', 'payment_auto_send')
```

**Task 1.5:** Add Phase 2 columns (Appointments)
```python
    # Add Grow appointment columns
    op.add_column('appointments', sa.Column('grow_transaction_code', sa.String(100), nullable=True))
    op.add_column('appointments', sa.Column('grow_payment_link', sa.Text, nullable=True))
    op.add_column('appointments', sa.Column('grow_transaction_token', sa.String(255), nullable=True))
    op.add_column('appointments', sa.Column('payment_requested_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('payment_completed_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('payment_failed_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('payment_failure_reason', sa.Text, nullable=True))

    # Add unique index for grow_transaction_code (CRITICAL for webhook O(1) lookup)
    op.create_unique_index('idx_appointments_grow_transaction_code', 'appointments',
                           ['grow_transaction_code'],
                           postgresql_where=sa.text("grow_transaction_code IS NOT NULL"))
```

**Task 1.6:** Migrate payment_status enum
```python
    # Migrate payment status values
    op.execute("""
        UPDATE appointments
        SET payment_status = CASE
            WHEN payment_status = 'not_paid' THEN 'unpaid'
            WHEN payment_status = 'payment_sent' THEN 'pending'
            ELSE payment_status
        END
        WHERE payment_status IN ('not_paid', 'payment_sent', 'paid', 'waived')
    """)

    # Alter enum type to include new values
    op.execute("ALTER TYPE payment_status_enum RENAME TO payment_status_enum_old")
    op.execute("""
        CREATE TYPE payment_status_enum AS ENUM (
            'unpaid', 'pending', 'paid', 'failed', 'refunded', 'waived'
        )
    """)
    op.execute("""
        ALTER TABLE appointments
        ALTER COLUMN payment_status TYPE payment_status_enum
        USING payment_status::text::payment_status_enum
    """)
    op.execute("DROP TYPE payment_status_enum_old")
```

**Task 1.7:** Copy historical data (optional preservation)
```python
    # Copy paid_at to payment_completed_at for historical appointments
    op.execute("""
        UPDATE appointments
        SET payment_completed_at = paid_at
        WHERE paid_at IS NOT NULL AND payment_status = 'paid'
    """)
```

**Deliverables:**
- ✅ Alembic migration file with upgrade() and downgrade()
- ✅ All Phase 1 fields removed
- ✅ All Phase 2 fields added
- ✅ Critical indexes created
- ✅ Payment status enum migrated

**Verification:**
```bash
# Test migration on development database
cd backend
uv run alembic upgrade head

# Verify schema changes
PGPASSWORD=pazpaz psql -U pazpaz -h localhost -d pazpaz -c "\d workspaces"
PGPASSWORD=pazpaz psql -U pazpaz -h localhost -d pazpaz -c "\d appointments"
PGPASSWORD=pazpaz psql -U pazpaz -h localhost -d pazpaz -c "\d payment_status_enum"
```

---

## Backend Implementation

### Phase 2: Grow Payment Provider

**Task 2.1:** Create Grow provider file structure
- [ ] Create `/backend/src/pazpaz/payments/providers/grow.py`
- [ ] Create `/backend/src/pazpaz/payments/providers/__init__.py` (if not exists)

**Task 2.2:** Implement GrowAPIClient
```python
# /backend/src/pazpaz/payments/providers/grow.py

class GrowAPIClient:
    """Low-level HTTP client for Grow API."""

    def __init__(self, api_key: str, base_url: str = GROW_API_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(...)

    @retry(...)
    async def create_payment_link(
        self, user_id: str, page_code: str, amount: Decimal, ...
    ) -> dict:
        """Create payment link via Grow API."""
        # Implementation from specialist guidance
```

**Task 2.3:** Implement GrowPaymentProvider
```python
class GrowPaymentProvider(PaymentProvider):
    """Grow payment provider implementation."""

    async def create_payment_link(
        self, request: PaymentLinkRequest
    ) -> PaymentLinkResponse:
        """Create payment link via Grow API."""
        # Implementation from specialist guidance

    async def verify_webhook(
        self, payload: bytes, headers: dict
    ) -> bool:
        """Verify Grow webhook signature (HMAC-SHA256)."""
        # Implementation from specialist guidance

    async def parse_webhook_payment(
        self, payload: dict
    ) -> WebhookPaymentData:
        """Parse Grow webhook JSON."""
        # Implementation from specialist guidance
```

**Task 2.4:** Register Grow provider with factory
```python
# At end of grow.py
from pazpaz.payments.factory import register_provider
register_provider("grow", GrowPaymentProvider)
```

**Deliverables:**
- ✅ GrowAPIClient with retry logic
- ✅ GrowPaymentProvider implementing PaymentProvider interface
- ✅ Webhook signature verification (HMAC-SHA256)
- ✅ Provider registered with factory

**Verification:**
```bash
# Run unit tests
cd backend
uv run pytest tests/unit/payments/test_grow_provider.py -v
```

---

### Phase 3: Payment Service Refactor

**Task 3.1:** Refactor PaymentService
- [ ] Open `/backend/src/pazpaz/services/payment_service.py`
- [ ] Remove Phase 1 methods: `mark_as_paid()`, `mark_as_unpaid()`, `update_payment_price()`

**Task 3.2:** Implement create_payment_request()
```python
async def create_payment_request(
    self,
    appointment: Appointment,
    workspace: Workspace,
    user_id: str,
) -> str:
    """Create payment request via Grow and send email.

    Returns:
        Payment link URL
    """
    # Validate appointment has price
    # Validate workspace has grow_user_id/grow_page_code
    # Get payment provider
    # Build PaymentLinkRequest
    # Call provider.create_payment_link()
    # Store grow_transaction_code, grow_payment_link
    # Set payment_status = 'pending', payment_requested_at = now
    # Create audit log
    # Return payment link URL
```

**Task 3.3:** Implement handle_payment_completed()
```python
async def handle_payment_completed(
    self,
    appointment: Appointment,
    completed_at: datetime,
) -> Appointment:
    """Handle successful payment webhook.

    Updates:
        - payment_status = 'paid'
        - payment_completed_at = webhook timestamp
    """
    # Check idempotency (already paid?)
    # Update payment status
    # Commit changes
    # Create audit log (optional)
```

**Task 3.4:** Implement handle_payment_failed()
```python
async def handle_payment_failed(
    self,
    appointment: Appointment,
    failure_reason: str | None,
) -> Appointment:
    """Handle failed payment webhook.

    Updates:
        - payment_status = 'failed'
        - payment_failed_at = now
        - payment_failure_reason = reason from webhook
    """
    # Update payment status
    # Commit changes
    # Create audit log (optional)
```

**Deliverables:**
- ✅ Phase 1 methods removed
- ✅ create_payment_request() implemented
- ✅ handle_payment_completed() implemented
- ✅ handle_payment_failed() implemented

**Verification:**
```bash
# Run service tests
uv run pytest tests/unit/services/test_payment_service.py -v
```

---

### Phase 4: Webhook Endpoint

**Task 4.1:** Create webhook router
- [ ] Create `/backend/src/pazpaz/api/webhooks.py` (or add to existing)

**Task 4.2:** Implement POST /webhooks/grow endpoint
```python
@router.post("/grow", status_code=200)
async def grow_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive and process Grow payment webhooks.

    Security:
        - Verifies HMAC-SHA256 signature before processing
        - Uses constant-time comparison
        - Logs verification failures

    Idempotency:
        - Uses grow_transaction_code as idempotency key
        - Safe to process duplicate webhooks
    """
    # Read raw body (for signature verification)
    # Parse JSON payload
    # Lookup appointment by grow_transaction_code
    # Get payment provider
    # Verify webhook signature
    # Parse webhook payload
    # Process payment status update (completed/failed/refunded)
    # Create audit log
    # Return 200 OK
```

**Task 4.3:** Register webhook router
```python
# /backend/src/pazpaz/main.py
from pazpaz.api.webhooks import router as webhooks_router

app.include_router(webhooks_router, prefix="/api/v1/webhooks", tags=["webhooks"])
```

**Deliverables:**
- ✅ POST /webhooks/grow endpoint
- ✅ Signature verification middleware
- ✅ Idempotency handling via grow_transaction_code
- ✅ Audit logging for webhook events

**Verification:**
```bash
# Run webhook integration tests
uv run pytest tests/integration/api/test_grow_webhooks.py -v
```

---

### Phase 5: Appointment Endpoints Update

**Task 5.1:** Modify POST /appointments/{id}/send-payment-request
- [ ] Open `/backend/src/pazpaz/api/appointments.py`
- [ ] Replace template-based logic with Grow API call

```python
@router.post("/{appointment_id}/send-payment-request")
async def send_payment_request(...):
    """Send payment request via Grow payment link."""
    # Fetch appointment with workspace, client
    # Validate appointment has price
    # Validate client has email
    # Call PaymentService.create_payment_request()
    # Send email with payment link
    # Return success response with payment link
```

**Task 5.2:** Remove GET /appointments/{id}/payment-link (no longer needed)
- [ ] Delete endpoint from appointments router

**Task 5.3:** Update response models
```python
class SendPaymentRequestResponse(BaseModel):
    success: bool
    payment_link: str
    grow_transaction_code: str
    message: str
```

**Deliverables:**
- ✅ send_payment_request endpoint updated for Grow
- ✅ payment-link endpoint removed
- ✅ Response models updated

**Verification:**
```bash
# Run appointment API tests
uv run pytest tests/integration/api/test_appointment_payments.py -v
```

---

### Phase 6: Payment Configuration Endpoints

**Task 6.1:** Update GET /payments/config
- [ ] Open `/backend/src/pazpaz/api/payments.py`
- [ ] Modify response model for Grow fields

```python
class PaymentConfigResponse(BaseModel):
    payment_provider: str | None  # 'grow' or null
    grow_user_id: str | None
    grow_page_code: str | None
    # Don't expose grow_webhook_key or API keys
```

**Task 6.2:** Update PUT /payments/config
```python
class PaymentConfigUpdate(BaseModel):
    payment_provider: Literal['grow'] | None
    grow_user_id: str | None
    grow_page_code: str | None

@router.put("/config")
async def update_payment_config(...):
    """Update workspace Grow configuration."""
    # Validate Grow credentials (if provided)
    # Encrypt API keys in payment_provider_config
    # Store grow_user_id, grow_page_code
    # Update workspace.payment_provider = 'grow'
    # Return updated config
```

**Task 6.3:** Add POST /payments/config/test
```python
@router.post("/config/test")
async def test_payment_config(...):
    """Test Grow payment provider configuration."""
    # Validate workspace has Grow configured
    # Initialize payment provider
    # Test API credentials (optional: test API call)
    # Return success or error
```

**Deliverables:**
- ✅ GET /payments/config updated for Grow
- ✅ PUT /payments/config updated for Grow
- ✅ POST /payments/config/test endpoint added

**Verification:**
```bash
# Run payment config tests
uv run pytest tests/integration/api/test_payment_config.py -v
```

---

### Phase 7: Model Updates

**Task 7.1:** Update Workspace model
- [ ] Open `/backend/src/pazpaz/models/workspace.py`
- [ ] Remove Phase 1 fields: `bank_account_details`, `payment_link_type`, `payment_link_template`
- [ ] Add Phase 2 fields:

```python
class Workspace(Base):
    # ... existing fields ...

    # Phase 2: Grow Integration
    grow_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grow_page_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grow_webhook_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

**Task 7.2:** Update Appointment model
- [ ] Open `/backend/src/pazpaz/models/appointment.py`
- [ ] Remove Phase 1 fields: `payment_method`, `payment_notes`, `paid_at`, `payment_auto_send`
- [ ] Add Phase 2 fields:

```python
class Appointment(Base):
    # ... existing fields ...

    # Phase 2: Grow Integration
    grow_transaction_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grow_payment_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    grow_transaction_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_requested_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    payment_completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    payment_failed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    payment_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Task 7.3:** Update payment_status enum
```python
# Update PaymentStatus enum
class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    WAIVED = "waived"
```

**Deliverables:**
- ✅ Workspace model updated
- ✅ Appointment model updated
- ✅ PaymentStatus enum updated

**Verification:**
```bash
# Run model tests
uv run pytest tests/unit/models/test_workspace.py -v
uv run pytest tests/unit/models/test_appointment.py -v
```

---

### Phase 8: Remove Phase 1 Code

**Task 8.1:** Delete Phase 1 service files
- [ ] Delete `/backend/src/pazpaz/services/payment_link_service.py`
- [ ] Delete `/backend/tests/integration/api/test_manual_payments.py`

**Task 8.2:** Remove Phase 1 utility functions
- [ ] Review `/backend/src/pazpaz/utils/payment_features.py`
- [ ] Remove Phase 1 feature checks (if any)

**Task 8.3:** Clean up imports
- [ ] Search for imports of deleted files
- [ ] Remove unused imports

**Deliverables:**
- ✅ All Phase 1 code deleted
- ✅ No broken imports

**Verification:**
```bash
# Run all backend tests to ensure no broken imports
uv run pytest tests/ -v
```

---

## Frontend Implementation

### Phase 9: Type Definitions Update

**Task 9.1:** Update PaymentStatus type
- [ ] Open `/frontend/src/types/calendar.ts`
- [ ] Update PaymentStatus enum:

```typescript
export type PaymentStatus = 'unpaid' | 'pending' | 'paid' | 'failed' | 'refunded' | 'waived'
```

**Task 9.2:** Remove PaymentMethod type
```typescript
// DELETE this type entirely
// export type PaymentMethod = 'cash' | 'card' | 'bank_transfer' | 'bit' | 'paybox' | 'other'
```

**Task 9.3:** Update AppointmentListItem interface
```typescript
export type AppointmentListItem = Omit<AppointmentListItemBase, 'payment_status'> & {
  payment_price?: string | null
  payment_status: PaymentStatus | string
  // REMOVED: payment_method, payment_notes, paid_at
  // ADDED:
  grow_transaction_code?: string | null
  grow_payment_link?: string | null
  payment_requested_at?: string | null
  payment_completed_at?: string | null
  payment_failed_at?: string | null
  payment_failure_reason?: string | null
}
```

**Task 9.4:** Update AppointmentFormData interface
```typescript
export interface AppointmentFormData {
  client_id: string
  scheduled_start: string
  scheduled_end: string
  location_type: 'clinic' | 'home' | 'online'
  location_details?: string
  notes?: string
  payment_price?: number | null
  payment_status?: PaymentStatus
  // REMOVED: payment_method, payment_notes
  // ADDED:
  payment_requested_at?: string | null
  payment_completed_at?: string | null
  payment_failed_at?: string | null
  payment_failure_reason?: string | null
  grow_transaction_code?: string | null
  grow_payment_link?: string | null
}
```

**Deliverables:**
- ✅ PaymentStatus type updated
- ✅ PaymentMethod type removed
- ✅ AppointmentListItem updated
- ✅ AppointmentFormData updated

**Verification:**
```bash
# Run TypeScript type check
cd frontend
npm run type-check
```

---

### Phase 10: Composable Updates

**Task 10.1:** Update usePayments.ts
- [ ] Open `/frontend/src/composables/usePayments.ts`
- [ ] Update PaymentConfig interface:

```typescript
interface PaymentConfig {
  payment_provider: 'grow' | null
  grow_user_id: string | null
  grow_page_code: string | null
  // REMOVED: payment_mode, bank_account_details, payment_link_type, payment_link_template
}
```

**Task 10.2:** Update paymentsEnabled computed
```typescript
const paymentsEnabled = computed(() => {
  return paymentConfig.value?.payment_provider === 'grow'
})
```

**Task 10.3:** Update getPaymentStatusBadge function
```typescript
function getPaymentStatusBadge(status: string | null): PaymentBadge | null {
  const badges: Record<string, PaymentBadge> = {
    unpaid: { label: 'Unpaid', borderColor: '#D1D5DB', showBadge: false },
    pending: { label: 'Pending', borderColor: '#3B82F6', bgColor: '#DBEAFE', showBadge: true },
    paid: { label: 'Paid', borderColor: '#10B981', bgColor: '#ECFDF5', showBadge: true },
    failed: { label: 'Failed', borderColor: '#EF4444', bgColor: '#FEE2E2', showBadge: true },
    refunded: { label: 'Refunded', borderColor: '#8B5CF6', bgColor: '#F5F3FF', showBadge: true },
    waived: { label: 'Waived', borderColor: '#8B5CF6', bgColor: '#F5F3FF', showBadge: true },
  }
  return status ? badges[status] || null : null
}
```

**Deliverables:**
- ✅ PaymentConfig interface updated
- ✅ paymentsEnabled logic updated
- ✅ getPaymentStatusBadge updated with new statuses

**Verification:**
```bash
# Run composable tests
npm run test:unit -- usePayments
```

---

### Phase 11: PaymentTrackingCard Update

**Task 11.1:** Update props interface
- [ ] Open `/frontend/src/components/appointments/PaymentTrackingCard.vue`
- [ ] Update Props interface:

```typescript
interface Props {
  paymentPrice?: number | null
  paymentStatus: PaymentStatus
  // REMOVED: paymentMethod, paymentNotes, paidAt
  // ADDED:
  paymentRequestedAt?: string | null
  paymentCompletedAt?: string | null
  paymentFailedAt?: string | null
  paymentFailureReason?: string | null
  growTransactionCode?: string | null
  readonly?: boolean
}
```

**Task 11.2:** Remove payment_method field
- [ ] Delete payment method dropdown
- [ ] Delete methodOptions array

**Task 11.3:** Remove payment_notes field
- [ ] Delete payment notes textarea
- [ ] Delete notes-related handlers

**Task 11.4:** Update payment_status options
```typescript
const statusOptions = [
  { value: 'unpaid', label: 'Unpaid', badgeClass: 'bg-slate-100 text-slate-700' },
  { value: 'pending', label: 'Pending', badgeClass: 'bg-blue-100 text-blue-700' },
  { value: 'paid', label: 'Paid', badgeClass: 'bg-emerald-100 text-emerald-700' },
  { value: 'failed', label: 'Failed', badgeClass: 'bg-red-100 text-red-700' },
  { value: 'refunded', label: 'Refunded', badgeClass: 'bg-purple-100 text-purple-700' },
  { value: 'waived', label: 'Waived', badgeClass: 'bg-purple-100 text-purple-700' },
]
```

**Task 11.5:** Add timestamp displays
```vue
<!-- Timestamp Display (context-aware) -->
<div v-if="localStatus === 'pending' && formattedRequestedAt" class="mt-2 text-xs text-slate-500">
  Payment requested on {{ formattedRequestedAt }}
</div>
<div v-if="localStatus === 'paid' && formattedCompletedAt" class="mt-2 text-xs text-slate-500">
  Paid on {{ formattedCompletedAt }}
</div>
<div v-if="localStatus === 'failed' && formattedFailedAt" class="mt-2 text-xs text-red-600">
  Failed on {{ formattedFailedAt }}
  <p v-if="paymentFailureReason" class="mt-1">{{ paymentFailureReason }}</p>
</div>
```

**Task 11.6:** Add transaction code display
```vue
<!-- Transaction Code (read-only, for support) -->
<div v-if="growTransactionCode" class="mt-4 rounded-lg bg-slate-50 p-3">
  <label class="text-xs text-slate-500">Transaction Code (for support)</label>
  <code class="mt-1 block font-mono text-sm text-slate-900">{{ growTransactionCode }}</code>
</div>
```

**Deliverables:**
- ✅ Props updated (method/notes removed, timestamps added)
- ✅ payment_method field removed
- ✅ payment_notes field removed
- ✅ payment_status options updated
- ✅ Timestamp displays added
- ✅ Transaction code display added

**Verification:**
```bash
# Run component tests
npm run test:unit -- PaymentTrackingCard
```

---

### Phase 12: PaymentActions Update

**Task 12.1:** Update props interface
- [ ] Open `/frontend/src/components/appointments/PaymentActions.vue`
- [ ] Add growPaymentLink prop:

```typescript
interface Props {
  price: number | null
  status: 'unpaid' | 'pending' | 'paid' | 'failed' | 'refunded' | 'waived'
  growPaymentLink: string | null // NEW
  readonly?: boolean
  sending?: boolean
  sent?: boolean
  copying?: boolean
  copied?: boolean
}
```

**Task 12.2:** Update button logic
- [ ] Disable "Send" if status is 'paid', 'failed', or 'refunded'
- [ ] Enable "Resend" if status is 'pending' or 'failed'
- [ ] Copy button uses growPaymentLink prop instead of API call

**Task 12.3:** Update API endpoint calls
```typescript
async function sendPaymentRequest() {
  // Call POST /appointments/{id}/send-payment-request
  // Updated to use Grow API
}

async function copyPaymentLink() {
  // Use props.growPaymentLink directly
  await navigator.clipboard.writeText(props.growPaymentLink)
}
```

**Deliverables:**
- ✅ Props updated with growPaymentLink
- ✅ Button logic updated for Grow statuses
- ✅ API calls updated

**Verification:**
```bash
# Run component tests
npm run test:unit -- PaymentActions
```

---

### Phase 13: PaymentSettings Complete Rewrite

**Task 13.1:** Backup old PaymentSettings.vue
- [ ] Copy `/frontend/src/components/settings/PaymentSettings.vue` to `.vue.backup`

**Task 13.2:** Rewrite component structure
- [ ] Replace entire component with Grow setup wizard
- [ ] Implement connection status display
- [ ] Add Grow credential inputs (grow_user_id, grow_page_code)

**Task 13.3:** Add Grow connection form
```vue
<div class="space-y-4">
  <div>
    <label>Grow User ID</label>
    <input v-model="growUserId" type="text" placeholder="e.g., 123456" />
    <p class="mt-1 text-xs text-slate-500">
      Find your User ID in your Grow dashboard under Settings → API
    </p>
  </div>

  <div>
    <label>Grow Page Code</label>
    <input v-model="growPageCode" type="text" placeholder="e.g., ABC123" />
    <p class="mt-1 text-xs text-slate-500">
      Find your Page Code in your Grow dashboard under Payment Pages
    </p>
  </div>

  <button @click="connectGrow">Connect Grow</button>
</div>
```

**Task 13.4:** Add webhook URL display
```vue
<div class="rounded-lg border border-slate-200 bg-slate-50 p-6">
  <h4>Webhook Configuration</h4>
  <p>Copy this URL and add it to your Grow dashboard under Settings → Webhooks</p>
  <code>{{ webhookUrl }}</code>
  <button @click="copyWebhookUrl">Copy</button>
</div>
```

**Task 13.5:** Add test payment link feature
```vue
<button @click="testPaymentLink">Test Payment Link</button>
```

**Task 13.6:** Add disconnect flow
```vue
<button @click="disconnectGrow">Disconnect Grow</button>
```

**Task 13.7:** Implement API methods
```typescript
async function connectGrow() {
  await apiClient.put('/payments/config', {
    payment_provider: 'grow',
    grow_user_id: growUserId.value,
    grow_page_code: growPageCode.value,
  })
}

async function disconnectGrow() {
  if (confirm('Disconnect Grow?')) {
    await apiClient.put('/payments/config', {
      payment_provider: null,
      grow_user_id: null,
      grow_page_code: null,
    })
  }
}

async function testPaymentLink() {
  const response = await apiClient.post('/payments/test-link', {
    amount: 100,
    description: 'Test payment',
  })
  window.open(response.data.payment_link, '_blank')
}
```

**Deliverables:**
- ✅ Complete rewrite of PaymentSettings.vue
- ✅ Grow setup wizard implemented
- ✅ Webhook URL display added
- ✅ Test payment link feature added
- ✅ Connect/disconnect flow implemented

**Verification:**
```bash
# Run component tests
npm run test:unit -- PaymentSettings
```

---

### Phase 14: Modal Updates

**Task 14.1:** Update AppointmentFormModal.vue
- [ ] Open `/frontend/src/components/calendar/AppointmentFormModal.vue`
- [ ] Update PaymentTrackingCard props:

```vue
<PaymentTrackingCard
  v-model:payment-price="formData.payment_price"
  v-model:payment-status="formData.payment_status!"
  :payment-requested-at="formData.payment_requested_at"
  :payment-completed-at="formData.payment_completed_at"
  :payment-failed-at="formData.payment_failed_at"
  :payment-failure-reason="formData.payment_failure_reason"
  :grow-transaction-code="formData.grow_transaction_code"
/>
```

**Task 14.2:** Remove auto-save for deleted fields
- [ ] Remove payment_method auto-save handler
- [ ] Remove payment_notes auto-save handler

**Task 14.3:** Update formData initialization
```typescript
const formData = ref<AppointmentFormData>({
  client_id: '',
  scheduled_start: '',
  scheduled_end: '',
  location_type: 'clinic',
  location_details: '',
  notes: '',
  payment_price: null,
  payment_status: 'unpaid', // Changed from 'not_paid'
  // REMOVED: payment_method, payment_notes
})
```

**Task 14.4:** Update AppointmentDetailsModal.vue
- [ ] Same changes as AppointmentFormModal
- [ ] Update PaymentTrackingCard props
- [ ] Update PaymentActions props (add growPaymentLink)
- [ ] Remove auto-save handlers for deleted fields

**Deliverables:**
- ✅ AppointmentFormModal updated
- ✅ AppointmentDetailsModal updated
- ✅ Auto-save handlers cleaned up

**Verification:**
```bash
# Run component tests
npm run test:unit -- AppointmentFormModal
npm run test:unit -- AppointmentDetailsModal
```

---

### Phase 15: API Client Regeneration

**Task 15.1:** Regenerate TypeScript client
- [ ] Ensure backend is running with updated endpoints
- [ ] Run OpenAPI client generator:

```bash
cd frontend
npm run generate-api-client
```

**Task 15.2:** Review generated types
- [ ] Verify PaymentStatus enum updated
- [ ] Verify AppointmentListItem fields updated
- [ ] Verify PaymentConfigResponse updated

**Task 15.3:** Fix any type errors
- [ ] Run type check: `npm run type-check`
- [ ] Fix any breaking type changes

**Deliverables:**
- ✅ TypeScript client regenerated from OpenAPI spec
- ✅ All type errors resolved

**Verification:**
```bash
npm run type-check
```

---

## Testing

### Phase 16: Backend Unit Tests

**Task 16.1:** Create Grow provider tests
- [ ] Create `/backend/tests/unit/payments/test_grow_provider.py`
- [ ] Test GrowAPIClient initialization
- [ ] Test create_payment_link() success/failure
- [ ] Test verify_webhook() with valid/invalid signatures
- [ ] Test parse_webhook_payment() with various payloads

**Task 16.2:** Update payment service tests
- [ ] Update `/backend/tests/unit/services/test_payment_service.py`
- [ ] Remove Phase 1 method tests (mark_as_paid, etc.)
- [ ] Add create_payment_request() tests
- [ ] Add handle_payment_completed() tests
- [ ] Add handle_payment_failed() tests

**Task 16.3:** Update model tests
- [ ] Update workspace model tests (new fields)
- [ ] Update appointment model tests (new fields)

**Deliverables:**
- ✅ Grow provider unit tests (100% coverage)
- ✅ Payment service tests updated
- ✅ Model tests updated

**Verification:**
```bash
cd backend
uv run pytest tests/unit/payments/ -v --cov
uv run pytest tests/unit/services/test_payment_service.py -v --cov
```

---

### Phase 17: Backend Integration Tests

**Task 17.1:** Create webhook integration tests
- [ ] Create `/backend/tests/integration/api/test_grow_webhooks.py`
- [ ] Test webhook with valid signature (payment completed)
- [ ] Test webhook with invalid signature (401 error)
- [ ] Test webhook idempotency (duplicate webhooks)
- [ ] Test webhook with unknown transaction_code (400 error)

**Task 17.2:** Update appointment payment tests
- [ ] Update `/backend/tests/integration/api/test_appointment_payments.py`
- [ ] Test send_payment_request() with Grow
- [ ] Test send_payment_request() without Grow configured (400 error)
- [ ] Test appointment fields updated after payment request

**Task 17.3:** Create payment config tests
- [ ] Create `/backend/tests/integration/api/test_payment_config.py`
- [ ] Test GET /payments/config
- [ ] Test PUT /payments/config (connect Grow)
- [ ] Test PUT /payments/config (disconnect Grow)
- [ ] Test POST /payments/config/test

**Task 17.4:** Remove Phase 1 tests
- [ ] Delete `/backend/tests/integration/api/test_manual_payments.py`

**Deliverables:**
- ✅ Webhook integration tests
- ✅ Appointment payment tests updated
- ✅ Payment config tests created
- ✅ Phase 1 tests deleted

**Verification:**
```bash
cd backend
uv run pytest tests/integration/api/test_grow_webhooks.py -v
uv run pytest tests/integration/api/test_appointment_payments.py -v
uv run pytest tests/integration/api/test_payment_config.py -v
```

---

### Phase 18: Frontend Unit Tests

**Task 18.1:** Update PaymentTrackingCard tests
- [ ] Update status enum tests (unpaid/pending/paid/failed/refunded)
- [ ] Remove payment_method tests
- [ ] Remove payment_notes tests
- [ ] Add timestamp display tests
- [ ] Add transaction code display test

**Task 18.2:** Update PaymentActions tests
- [ ] Update button state tests (new statuses)
- [ ] Test growPaymentLink prop

**Task 18.3:** Rewrite PaymentSettings tests
- [ ] Remove Phase 1 tests completely
- [ ] Add Grow connection form tests
- [ ] Add webhook URL display tests
- [ ] Test connect/disconnect flow

**Task 18.4:** Update modal tests
- [ ] Update AppointmentFormModal tests (remove method/notes)
- [ ] Update AppointmentDetailsModal tests (remove method/notes)

**Deliverables:**
- ✅ PaymentTrackingCard tests updated
- ✅ PaymentActions tests updated
- ✅ PaymentSettings tests rewritten
- ✅ Modal tests updated

**Verification:**
```bash
cd frontend
npm run test:unit
```

---

### Phase 19: End-to-End Testing

**Task 19.1:** Manual testing checklist
- [ ] Enable Grow in PaymentSettings (connect flow)
- [ ] Create appointment with price
- [ ] Send payment request (verify link generated)
- [ ] Copy payment link (verify clipboard)
- [ ] Simulate webhook (use Grow sandbox or test script)
- [ ] Verify payment status updates to 'paid'
- [ ] Test payment failure flow (webhook with failure)
- [ ] Disconnect Grow (verify graceful degradation)

**Task 19.2:** Grow sandbox testing
- [ ] Get Grow sandbox credentials (test environment)
- [ ] Configure sandbox in development environment
- [ ] Test full payment flow in sandbox
- [ ] Verify webhook signature verification works

**Deliverables:**
- ✅ Manual testing checklist completed
- ✅ Grow sandbox integration verified

**Verification:**
- Document test results in `/docs/testing/GROW_E2E_TEST_RESULTS.md`

---

## Deployment

### Phase 20: Pre-Production Checklist

**Task 20.1:** Database migration on staging
- [ ] Backup staging database
- [ ] Run Alembic migration: `uv run alembic upgrade head`
- [ ] Verify schema changes
- [ ] Test rollback: `uv run alembic downgrade -1` → `upgrade head`

**Task 20.2:** Environment configuration
- [ ] Add Grow API key to environment variables
- [ ] Add webhook secret to environment variables
- [ ] Configure Grow base URL (production vs sandbox)
- [ ] Update CORS settings (if needed for webhooks)

**Task 20.3:** Grow webhook configuration
- [ ] Get production webhook URL: `https://pazpaz.health/api/v1/webhooks/grow`
- [ ] Add webhook URL to Grow dashboard
- [ ] Test webhook delivery with Grow test tool

**Task 20.4:** Build and deploy
- [ ] Build backend: `cd backend && uv build`
- [ ] Build frontend: `cd frontend && npm run build`
- [ ] Deploy to staging environment
- [ ] Verify health check: `curl https://staging.pazpaz.health/api/health`

**Deliverables:**
- ✅ Staging database migrated
- ✅ Environment variables configured
- ✅ Webhook URL registered with Grow
- ✅ Application deployed to staging

**Verification:**
```bash
# Test staging endpoints
curl https://staging.pazpaz.health/api/v1/payments/config
curl -X POST https://staging.pazpaz.health/api/v1/webhooks/grow -d '...'
```

---

### Phase 21: Production Deployment

**Task 21.1:** Production database migration
- [ ] Backup production database (full backup)
- [ ] Export Phase 1 payment data to CSV (historical archive)
- [ ] Run migration during maintenance window
- [ ] Verify migration success

**Task 21.2:** Deploy to production
- [ ] Deploy backend to production
- [ ] Deploy frontend to production
- [ ] Verify health check
- [ ] Smoke test: Create appointment, send payment request

**Task 21.3:** Monitor deployment
- [ ] Check logs for errors
- [ ] Monitor webhook endpoint (/webhooks/grow)
- [ ] Verify Grow API calls succeed

**Task 21.4:** User communication
- [ ] Send email to therapists about new Grow integration
- [ ] Provide setup instructions (link to docs)
- [ ] Offer support for migration questions

**Deliverables:**
- ✅ Production database migrated
- ✅ Application deployed to production
- ✅ Monitoring in place
- ✅ Users notified

**Verification:**
- Monitor Sentry for errors
- Check Grow webhook logs
- Verify first payment completes successfully

---

## Post-Launch

### Phase 22: Monitoring & Support

**Task 22.1:** Set up monitoring alerts
- [ ] Alert on webhook signature verification failures
- [ ] Alert on Grow API errors (401, 500)
- [ ] Alert on payment processing failures
- [ ] Dashboard for payment metrics (sent/completed/failed)

**Task 22.2:** Documentation
- [ ] Update `/docs/backend/PAYMENT_INTEGRATION.md`
- [ ] Create `/docs/USER_GUIDE_GROW_SETUP.md`
- [ ] Update API documentation
- [ ] Create troubleshooting guide

**Task 22.3:** First 48 hours
- [ ] Monitor webhook processing closely
- [ ] Respond to user support requests quickly
- [ ] Document any issues encountered
- [ ] Hot-fix any critical bugs

**Task 22.4:** Week 1 review
- [ ] Review payment success rate
- [ ] Check Grow API cost vs projections
- [ ] Gather user feedback
- [ ] Identify optimization opportunities

**Deliverables:**
- ✅ Monitoring alerts configured
- ✅ Documentation updated
- ✅ First 48 hours stable
- ✅ Week 1 review completed

---

## Success Metrics

### Technical Metrics
- ✅ Webhook processing time < 100ms (p95)
- ✅ Payment link generation time < 2s (p95)
- ✅ Zero webhook signature verification failures
- ✅ 99.9% uptime for payment endpoints

### Business Metrics
- ✅ Payment success rate > 95%
- ✅ Therapist adoption rate (% enabling Grow)
- ✅ Average time to first payment
- ✅ Grow API cost per payment

### User Experience Metrics
- ✅ Setup completion rate (% completing Grow configuration)
- ✅ Support tickets related to payments
- ✅ User satisfaction score (NPS)

---

## Rollback Plan

### If Critical Issues Arise

1. **Database Rollback:**
   ```bash
   cd backend
   uv run alembic downgrade -1
   ```

2. **Code Rollback:**
   - Revert to previous commit
   - Redeploy previous version

3. **Disable Grow:**
   - Update all workspaces: `SET payment_provider = NULL`
   - Disable webhook endpoint

4. **Communication:**
   - Notify users of rollback
   - Provide timeline for fix

---

## Estimated Timeline

### Development
- Database Migration: 2 hours
- Backend Implementation: 16 hours
- Frontend Implementation: 19 hours
- Testing: 12 hours
- **Total Development:** ~49 hours (6-7 working days)

### Deployment
- Staging: 4 hours
- Production: 4 hours
- Monitoring: Ongoing
- **Total Deployment:** ~8 hours (1 day)

### Grand Total: 57 hours (~8 working days)

---

## Team Assignments

**Backend Developer:**
- Database migration (Phase 1)
- Grow provider implementation (Phase 2-3)
- Webhook endpoint (Phase 4)
- Endpoint updates (Phase 5-6)
- Backend testing (Phase 16-17)

**Frontend Developer:**
- Type updates (Phase 9-10)
- Component updates (Phase 11-14)
- Frontend testing (Phase 18)

**DevOps:**
- Environment configuration (Phase 20)
- Deployment (Phase 20-21)
- Monitoring (Phase 22)

**Product Manager:**
- User communication (Phase 21)
- Documentation (Phase 22)
- Success metrics tracking (Phase 22)

---

## Contacts

**Grow Support:**
- Email: support@grow.co.il
- Documentation: https://grow-il.readme.io/reference/

**PazPaz Team:**
- Backend Lead: [Name]
- Frontend Lead: [Name]
- DevOps Lead: [Name]

---

## Appendix

### Useful Commands

**Database:**
```bash
# Run migration
cd backend && uv run alembic upgrade head

# Rollback migration
uv run alembic downgrade -1

# Check migration status
uv run alembic current
```

**Testing:**
```bash
# Backend tests
cd backend
uv run pytest tests/ -v --cov

# Frontend tests
cd frontend
npm run test:unit
npm run type-check
```

**Deployment:**
```bash
# Build backend
cd backend && uv build

# Build frontend
cd frontend && npm run build

# Health check
curl https://pazpaz.health/api/health
```

### Environment Variables

**Backend (.env):**
```bash
GROW_API_KEY=pk_live_...
GROW_WEBHOOK_SECRET=whsec_...
GROW_BASE_URL=https://api.grow.com
DATABASE_URL=postgresql+asyncpg://...
```

**Frontend (.env):**
```bash
VITE_API_BASE_URL=https://pazpaz.health/api
```

---

## Change Log

- **2025-11-03:** Initial plan created
- **[Date]:** Database migration completed
- **[Date]:** Backend implementation completed
- **[Date]:** Frontend implementation completed
- **[Date]:** Deployed to staging
- **[Date]:** Deployed to production

---

**END OF IMPLEMENTATION PLAN**
