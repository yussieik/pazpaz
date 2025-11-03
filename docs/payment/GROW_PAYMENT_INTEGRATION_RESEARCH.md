# Grow Payment Integration Research Summary

**Date:** 2025-11-03
**Status:** ✅ CONFIRMED - Grow API + Invoice Integration Available

---

## Executive Summary

Grow (formerly Meshulam) **CONFIRMED support for marketplace/platform integrations** for PazPaz. Based on direct conversation with Grow support team:

### Confirmed Integration Model

- ✅ **API Access Available:** ₪500/month + VAT for platform API access
- ✅ **Pay As You Grow Plan:** Volume-based commission rates (1.4% to 0.9% as volume increases)
- ✅ **All Payment Methods:** Credit cards, Bit for Business, Apple Pay, Google Pay, bank transfers
- ✅ **Automatic Invoicing:** Digital invoices issued automatically at no extra cost
- ✅ **No Setup Fees:** Usage-based billing only
- ✅ **12 Installments:** Credit card payments up to 12 installments without interest
- ✅ **Recurring Payments:** Supported without blocking customer credit limit

### Pricing Structure

**For PazPaz (Platform):**
- Monthly API fee: ₪500 + VAT (₪585 total)
- Required from testing phase onwards

**For Therapists (Per Transaction):**
- Volume-based commission rates (see detailed pricing below)
- Lower rates as total platform volume increases
- Bit transfers: ₪1 flat fee per transaction

### Integration Method

**Confirmed Approach:** API + Automatic Invoice Generation
- Each therapist has Grow account (userId)
- PazPaz uses platform apiKey + therapist userId
- Payments trigger automatic invoice generation
- Money flows directly to therapist accounts

**Note:** userId creation method (programmatic vs manual) still to be determined during technical implementation

---

## 1. Business Requirements

### What PazPaz Needs

**For MVP:**
- Zero-friction therapist onboarding (no payment setup required)
- Automatic Bit payment tracking
- Direct payment to therapists (they receive full amount minus Grow fees)
- PazPaz charges ₪0 platform fees initially (free MVP)

**Post-MVP:**
- Optional platform fees OR subscription-based revenue
- Scalable to 100-200+ therapists
- Transparent pricing for therapists

---

## 2. Grow's Platform Model

### Architecture Overview

```
Client pays ₪300 via Bit
  ↓
Payment processed through Grow
  ↓
Grow automatically splits:
  ├─ Platform commission (PazPaz): ₪X (configurable via companyCommission)
  └─ Merchant payment (Therapist): ₪(300-X) (minus Grow's processing fees)
  ↓
Money settles to respective bank accounts automatically
```

### Key API Parameters

#### 1. `apiKey` (Platform Identifier)
- **Required:** Yes, for all platform requests
- **Purpose:** Authenticates PazPaz as the platform
- **Type:** String
- **Example:** `"pazpaz_platform_key_abc123"`
- **Where to get:** Provided by Grow during platform onboarding

#### 2. `userId` (Per-Therapist Account)
- **Required:** Yes, for each therapist
- **Purpose:** Routes payment to specific therapist's Grow account
- **Type:** String
- **Example:** `"therapist_user_xyz789"`
- **Critical Question:** How is this created? (See Section 4)

#### 3. `pageCode` (Payment Configuration)
- **Required:** Yes
- **Purpose:** Defines payment type and settings
- **Type:** String
- **Example:** `"appointment_payment"`
- **Where to get:** Provided by Grow

#### 4. `companyCommission` (Platform Fee)
- **Required:** No (optional)
- **Purpose:** Platform's fee per transaction
- **Type:** Number (fixed amount in ILS, NOT percentage)
- **Format:** Excludes VAT
- **Example:** `2.5` = ₪2.50 platform fee
- **For MVP:** Set to `0` (no platform fee)

---

## 3. Payment Flow Example

### MVP Flow (No Platform Fee)

```python
# Create payment request via Grow API
response = await grow_api.create_payment({
    "apiKey": "pazpaz_platform_key",        # PazPaz's platform identifier
    "userId": "therapist_123",               # Specific therapist's account
    "pageCode": "appointment",               # Payment type
    "sum": 300.00,                          # ₪300 appointment price
    "companyCommission": 0,                  # No platform fee (MVP)
    "description": "Appointment with Sarah Cohen",
    "clientEmail": "client@example.com",
    "notificationUrl": "https://pazpaz.com/api/v1/webhooks/grow",
    "successUrl": "https://pazpaz.com/payment-success",
    "cancelUrl": "https://pazpaz.com/payment-cancelled",
})

# Returns payment link
payment_url = response["url"]  # Client clicks this to pay via Bit
```

**Money Flow:**
- Client pays: ₪300
- Grow fee: ~₪5.20 (₪1 + 1.4%)
- Platform fee: ₪0 (MVP)
- Therapist receives: ₪294.80

### Post-MVP Flow (With Platform Fee)

```python
response = await grow_api.create_payment({
    "apiKey": "pazpaz_platform_key",
    "userId": "therapist_123",
    "pageCode": "appointment",
    "sum": 300.00,
    "companyCommission": 10.0,              # ₪10 platform fee
    "description": "Appointment with Sarah Cohen",
    # ... other params
})
```

**Money Flow:**
- Client pays: ₪300
- Grow fee: ~₪5.20 (₪1 + 1.4%)
- Platform fee: ₪10 (goes to PazPaz)
- Therapist receives: ₪284.80

---

## 4. Critical Question: userId Creation

### Two Possible Models

#### Option A: Programmatic Sub-Account Creation (PREFERRED)

**How it works:**
```
Therapist signs up for PazPaz
  ↓
Therapist provides: Bank account, ID, business info
  ↓
PazPaz calls Grow API: POST /api/create-sub-merchant
  {
    "apiKey": "pazpaz_platform_key",
    "bankAccount": "123456",
    "bankBranch": "789",
    "accountName": "Dr. Sarah Cohen",
    "idNumber": "123456789",
    "businessLicense": "...",
  }
  ↓
Grow returns: { "userId": "therapist_123" }
  ↓
PazPaz stores userId in database
  ↓
Therapist never interacts with Grow directly
```

**Pros:**
- ✅ Zero therapist friction (they never see Grow)
- ✅ Seamless onboarding UX
- ✅ PazPaz controls entire flow
- ✅ Therapist just provides bank details

**Cons:**
- ⚠️ Requires API support from Grow (not yet confirmed)
- ⚠️ PazPaz responsible for KYC/compliance data collection

#### Option B: Manual Therapist Account Creation (FALLBACK)

**How it works:**
```
Therapist signs up for PazPaz
  ↓
PazPaz: "To enable payments, create a Grow account"
  ↓
Therapist clicks link → grow.business/join-us/
  ↓
Therapist creates Grow account (5-10 min)
  ↓
Therapist receives userId from Grow dashboard
  ↓
Therapist enters userId in PazPaz Settings → Payment Settings
  ↓
PazPaz stores userId and can now create payment links
```

**Pros:**
- ✅ Simpler for PazPaz (no sub-account management)
- ✅ Therapist owns their Grow account directly
- ✅ Grow handles all KYC/compliance
- ✅ Still automatic money flow (no manual payouts)

**Cons:**
- ❌ Therapist setup friction (5-10 min onboarding)
- ❌ Therapist must understand Grow
- ❌ Risk of therapists abandoning setup

---

## 5. Questions to Ask Grow

### Email Template

```
Subject: Platform Integration - userId Creation for Therapists

Hi Grow Team,

Great news! I found your "Platforms & Multi-Merchant Systems" documentation
showing the apiKey + userId + companyCommission model. This looks perfect
for PazPaz!

I understand the architecture:
✓ PazPaz has platform apiKey
✓ Each therapist has userId
✓ We create payments with: apiKey + therapist's userId
✓ Money goes directly to therapist's Grow account
✓ Optional companyCommission for platform fees

**CRITICAL QUESTION (Blocks our UX decision):**

How do therapists get their userId?

**Option A (WHAT WE NEED):**
• PazPaz creates userId via API when therapist signs up
• Therapist provides: bank account, ID, business info
• PazPaz calls POST /api/create-sub-merchant → Returns userId
• Therapist never interacts with Grow directly
• Money still goes to therapist's bank account

**Option B (What we want to avoid):**
• Each therapist creates Grow merchant account manually
• Therapist gets userId from Grow dashboard
• Therapist enters userId in PazPaz settings
• Adds friction to therapist onboarding

**Question:** Does Grow support Option A (programmatic userId creation)?

If YES → Perfect! This is exactly what we need.
If NO → We can work with Option B, but UX is less ideal.

**Additional Questions:**

1. **Settlement:** When does money reach therapist's bank?
   • Same day as payment? Next day? End of month?

2. **Platform Commission:** If we use companyCommission:
   • Where does our commission go? (PazPaz's Grow account?)
   • When do we receive it?

3. **Onboarding:** For Option A:
   • What API endpoint creates userId?
   • What therapist info is required? (Bank, ID, tax number?)
   • KYC/verification process?

4. **Testing:** How do we test in sandbox?
   • Can we create test userIds?
   • Test companyCommission flows?

**Our Use Case:**
• 100-200 therapists initially
• ₪200-500 per appointment
• Want zero-friction therapist onboarding
• MVP: No platform commission (companyCommission: 0)
• Future: Maybe ₪5-10 per transaction OR monthly subscription

Can we schedule a call this week to clarify?

Best,
[Your Name]
PazPaz Founder
Email: [email]
WhatsApp: [number]
```

---

## 6. Technical Implementation (Option A)

### Backend Architecture

#### Database Schema

```python
# Workspace model (therapist account)
class Workspace(Base):
    __tablename__ = "workspaces"

    # Existing fields...

    # Grow integration
    grow_user_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    grow_onboarding_status: Mapped[str] = mapped_column(String, default="pending")
    # pending, verification_needed, verified, rejected

    # Payout info (for Grow sub-account creation)
    payout_bank_name: Mapped[str | None] = mapped_column(String, nullable=True)
    payout_bank_branch: Mapped[str | None] = mapped_column(String, nullable=True)
    payout_account_number: Mapped[str | None] = mapped_column(String, nullable=True)
    payout_account_name: Mapped[str | None] = mapped_column(String, nullable=True)
    payout_id_number: Mapped[str | None] = mapped_column(String, nullable=True)
    payout_business_license: Mapped[str | None] = mapped_column(String, nullable=True)

# Appointment model
class Appointment(Base):
    __tablename__ = "appointments"

    # Existing fields...

    # Payment tracking
    payment_link: Mapped[str | None] = mapped_column(String, nullable=True)
    grow_process_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    grow_transaction_id: Mapped[str | None] = mapped_column(String, nullable=True)
```

#### Grow Payment Provider

```python
# backend/src/pazpaz/payments/providers/grow.py

from typing import Optional
from decimal import Decimal
import httpx
from ..base import PaymentProvider

class GrowPaymentProvider(PaymentProvider):
    """
    Grow (formerly Meshulam) platform payment provider.
    Supports marketplace model with automatic therapist payouts.

    Docs: https://grow-il.readme.io/
    """

    def __init__(
        self,
        platform_api_key: str,
        page_code: str,
        base_url: str = "https://secure.meshulam.co.il"
    ):
        self.platform_api_key = platform_api_key
        self.page_code = page_code
        self.base_url = base_url

    async def create_sub_merchant(
        self,
        bank_name: str,
        bank_branch: str,
        account_number: str,
        account_name: str,
        id_number: str,
        business_license: Optional[str] = None,
    ) -> dict:
        """
        Create sub-merchant account for therapist.
        Returns userId for future payment requests.

        NOTE: Endpoint URL is hypothetical - waiting for Grow confirmation.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/platform/create-sub-merchant",
                data={
                    "apiKey": self.platform_api_key,
                    "bankName": bank_name,
                    "bankBranch": bank_branch,
                    "accountNumber": account_number,
                    "accountName": account_name,
                    "idNumber": id_number,
                    "businessLicense": business_license,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            data = response.json()
            return {
                "user_id": data["userId"],
                "status": data["status"],  # verified, pending_verification, rejected
            }

    async def create_payment_link(
        self,
        therapist_user_id: str,
        amount: Decimal,
        description: str,
        appointment_id: str,
        client_email: str,
        client_phone: Optional[str] = None,
        platform_commission: Decimal = Decimal("0"),  # ₪0 for MVP
    ) -> dict:
        """
        Create payment link for appointment.
        Money goes directly to therapist's account.
        Platform commission (if any) goes to PazPaz.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/light-server-1-0/createPaymentProcess",
                data={
                    "apiKey": self.platform_api_key,
                    "userId": therapist_user_id,
                    "pageCode": self.page_code,
                    "sum": float(amount),
                    "companyCommission": float(platform_commission),  # ₪0 for MVP
                    "description": description,
                    "clientEmail": client_email,
                    "clientPhone": client_phone,
                    "customFields[appointment_id]": appointment_id,
                    "notificationUrl": f"{BACKEND_URL}/api/v1/webhooks/grow",
                    "successUrl": f"{FRONTEND_URL}/payment-success",
                    "cancelUrl": f"{FRONTEND_URL}/payment-cancelled",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            data = response.json()
            return {
                "payment_url": data["url"],
                "process_id": data["processId"],
                "status": "pending"
            }

    async def verify_webhook_signature(self, payload: dict, signature: str) -> bool:
        """Verify webhook authenticity from Grow."""
        # Implementation based on Grow webhook security docs
        # TODO: Get signature verification method from Grow
        pass

    async def get_payment_status(self, process_id: str) -> str:
        """Query payment status from Grow API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/light-server-1-0/getPaymentProcessInfo",
                data={
                    "apiKey": self.platform_api_key,
                    "processId": process_id
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            data = response.json()
            return data["status"]
```

#### Webhook Handler

```python
# backend/src/pazpaz/api/webhooks.py

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..payments.factory import get_payment_provider
from ..models import Appointment
from ..services.email_service import send_payment_confirmation_email
from datetime import datetime

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/grow")
async def grow_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Receive payment status updates from Grow.
    Called automatically when client completes Bit payment.
    """
    # Parse FormData webhook payload
    form_data = await request.form()
    payload = dict(form_data)

    # Verify webhook signature (security critical!)
    provider = get_payment_provider("grow")
    signature = request.headers.get("X-Grow-Signature")
    if not await provider.verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    # Extract appointment ID from custom fields
    appointment_id = payload.get("customFields[appointment_id]")
    appointment = await db.get(Appointment, appointment_id)

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Update payment status based on webhook
    transaction_status = payload.get("status")  # Hebrew: "שולם", "נכשל", etc.

    if transaction_status == "שולם":  # "Paid"
        appointment.payment_status = "paid"
        appointment.paid_at = datetime.utcnow()
        appointment.grow_transaction_id = payload.get("transactionId")

        # Send confirmation email to therapist
        await send_payment_confirmation_email(appointment)

    elif transaction_status == "נכשל":  # "Failed"
        appointment.payment_status = "not_paid"
        # Maybe notify therapist of failed payment

    await db.commit()

    return {"status": "ok"}
```

### Frontend Flow

#### Therapist Onboarding

```vue
<!-- Settings → Payment Settings -->
<template>
  <div v-if="!paymentsEnabled">
    <h3>Enable Automatic Bit Payments</h3>
    <p>Accept payments automatically with zero setup!</p>

    <button @click="showBankDetailsForm = true">
      Get Started
    </button>

    <!-- Bank Details Collection Form -->
    <div v-if="showBankDetailsForm" class="bank-details-form">
      <h4>Your Bank Details</h4>
      <p>Required for receiving payments from clients</p>

      <select v-model="bankName">
        <option value="hapoalim">Bank Hapoalim</option>
        <option value="leumi">Bank Leumi</option>
        <option value="discount">Discount Bank</option>
        <!-- ... other Israeli banks -->
      </select>

      <input v-model="bankBranch" placeholder="Branch number" />
      <input v-model="accountNumber" placeholder="Account number" />
      <input v-model="accountName" placeholder="Account holder name" />
      <input v-model="idNumber" placeholder="ID number" />
      <input v-model="businessLicense" placeholder="Business license (optional)" />

      <p class="fee-info">
        Processing fee: ₪1 + 1.4% per transaction (charged by Grow)
        PazPaz is free!
      </p>

      <button @click="submitBankDetails">
        Enable Payments
      </button>
    </div>
  </div>

  <div v-else-if="onboardingStatus === 'verified'">
    <h3>Automatic Payments Enabled ✓</h3>
    <p>You can now send payment requests to clients</p>

    <div class="bank-info">
      <p>Bank: {{ maskBankAccount(accountNumber) }}</p>
      <button @click="showEditBankDetails = true">Edit</button>
    </div>
  </div>

  <div v-else-if="onboardingStatus === 'pending'">
    <h3>Verification in Progress</h3>
    <p>Your bank details are being verified by Grow. This typically takes 1-2 business days.</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { usePaymentsApi } from '@/composables/usePaymentsApi'

const { enablePayments } = usePaymentsApi()

const showBankDetailsForm = ref(false)
const bankName = ref('')
const bankBranch = ref('')
const accountNumber = ref('')
const accountName = ref('')
const idNumber = ref('')
const businessLicense = ref('')

async function submitBankDetails() {
  try {
    const result = await enablePayments({
      bankName: bankName.value,
      bankBranch: bankBranch.value,
      accountNumber: accountNumber.value,
      accountName: accountName.value,
      idNumber: idNumber.value,
      businessLicense: businessLicense.value,
    })

    // Show success message
    toast.success('Payment setup initiated! Verification in progress.')
  } catch (error) {
    toast.error('Failed to enable payments. Please check your details.')
  }
}
</script>
```

#### Sending Payment Request

```vue
<!-- Appointment Details Modal → Payment Tab -->
<template>
  <div v-if="paymentsEnabled && appointment.payment_status === 'not_paid'">
    <button @click="sendPaymentRequest" class="primary-button">
      Send Payment Request
    </button>
  </div>

  <div v-else-if="appointment.payment_link && appointment.payment_status === 'not_paid'">
    <p>Payment link sent</p>
    <div class="payment-link">
      <input :value="appointment.payment_link" readonly />
      <button @click="copyPaymentLink">Copy Link</button>
    </div>

    <button @click="resendPaymentRequest">
      Resend via Email/SMS
    </button>
  </div>

  <div v-else-if="appointment.payment_status === 'paid'">
    <div class="payment-success">
      <span class="badge success">Paid ✓</span>
      <p>Paid on {{ formatDate(appointment.paid_at) }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { usePaymentsApi } from '@/composables/usePaymentsApi'

const { createPaymentLink } = usePaymentsApi()

async function sendPaymentRequest() {
  try {
    const result = await createPaymentLink(appointment.id)

    appointment.payment_link = result.payment_url

    toast.success('Payment request sent to client!')
  } catch (error) {
    toast.error('Failed to create payment link')
  }
}

function copyPaymentLink() {
  navigator.clipboard.writeText(appointment.payment_link)
  toast.success('Payment link copied!')
}
</script>
```

---

## 7. Technical Implementation (Option B)

### If Therapists Must Create Grow Accounts Manually

**Onboarding Flow:**

```vue
<template>
  <div v-if="!paymentsEnabled">
    <h3>Enable Automatic Bit Payments</h3>

    <div class="setup-steps">
      <div class="step">
        <span class="step-number">1</span>
        <div class="step-content">
          <h4>Create Grow Account</h4>
          <p>Takes 5-10 minutes, one-time setup</p>
          <a href="https://grow.business/join-us/" target="_blank" class="button">
            Create Grow Account →
          </a>
        </div>
      </div>

      <div class="step">
        <span class="step-number">2</span>
        <div class="step-content">
          <h4>Get Your API Credentials</h4>
          <p>From Grow dashboard → Settings → API</p>
          <ol>
            <li>Log in to grow.business</li>
            <li>Go to Settings → API</li>
            <li>Copy your User ID</li>
          </ol>
        </div>
      </div>

      <div class="step">
        <span class="step-number">3</span>
        <div class="step-content">
          <h4>Connect to PazPaz</h4>
          <input v-model="growUserId" placeholder="Paste your Grow User ID" />
          <button @click="connectGrowAccount">
            Connect Account
          </button>
        </div>
      </div>
    </div>
  </div>

  <div v-else>
    <h3>Grow Account Connected ✓</h3>
    <p>You can now send payment requests to clients</p>
  </div>
</template>
```

**Backend changes minimal** - just store `grow_user_id` instead of creating it.

---

## 8. Cost Analysis (UPDATED WITH CONFIRMED PRICING)

### Grow's Pay As You Grow Pricing (Confirmed)

**Volume-Based Commission Tiers:**
| Monthly Volume | Commission Rate | Per Transaction Fee | Total Fee (₪300 payment) |
|----------------|-----------------|---------------------|-------------------------|
| ₪0-18,500 | 1.4% | +₪1 | ₪5.20 |
| ₪18,500-74,000 | 1.2% | +₪1 | ₪4.60 |
| ₪74,000-555,000 | 1.0% | +₪1 | ₪4.00 |
| ₪555,000-925,000 | 0.95% | +₪1 | ₪3.85 |
| ₪925,000+ | 0.9% | +₪1 | ₪3.70 |

**Special Fees:**
- **Bit transfers:** ₪1 flat fee (no percentage!)
- **Diners Club:** Additional 0.5% surcharge
- **Bank settlement:** ₪16.90 (waived if transfer >₪5,000)
- **Chargebacks:** ₪40 per dispute

### For Therapists (Real Costs)

#### Scenario 1: Single Therapist Starting Out (Low Volume)
**40 appointments/month @ ₪300 each = ₪12,000 monthly volume**
- Volume tier: ₪0-18,500 (1.4% + ₪1)
- Per ₪300 appointment: ₪5.20 fee
- Monthly fees: ₪208 (40 × ₪5.20)
- **Net to therapist: ₪11,792** (98.27% of revenue)

#### Scenario 2: Established Therapist (Medium Volume)
**100 appointments/month @ ₪350 each = ₪35,000 monthly volume**
- Volume tier: ₪18,500-74,000 (1.2% + ₪1)
- Per ₪350 appointment: ₪5.20 fee
- Monthly fees: ₪520 (100 × ₪5.20)
- **Net to therapist: ₪34,480** (98.51% of revenue)

#### Scenario 3: Platform with 50 Therapists (High Volume)
**Total platform volume: ₪600,000/month**
- Volume tier: ₪555,000-925,000 (0.95% + ₪1)
- Per ₪300 appointment: ₪3.85 fee
- **Each therapist saves ₪1.35 per transaction** vs starting tier
- **Platform-wide savings: ~₪2,700/month** compared to low-volume pricing

#### Special Case: Bit Payments Only
**40 appointments/month @ ₪300 via Bit**
- Fee per transaction: **₪1 flat** (no percentage!)
- Monthly fees: ₪40 (40 × ₪1)
- **Net to therapist: ₪11,960** (99.67% of revenue!)

**This is HUGE for therapists who primarily use Bit!**

### Post-MVP Revenue Models

#### Option A: Transaction Fee
```
Platform fee: ₪10 per appointment
- Client pays: ₪300
- Grow fee: ₪5.20
- Platform fee: ₪10
- Therapist receives: ₪284.80 (94.93%)

PazPaz revenue (40 appointments): ₪400/month per therapist
```

#### Option B: Monthly Subscription
```
- Therapist pays: ₪149/month subscription
- No per-transaction platform fee
- Therapist receives: ₪294.80 per ₪300 appointment (98.27%)

PazPaz revenue: ₪149/month per therapist (predictable)
```

#### Option C: Hybrid
```
- Therapist pays: ₪79/month subscription
- Platform fee: ₪5 per appointment
- Therapist receives: ₪289.80 per ₪300 appointment (96.6%)

PazPaz revenue (40 appointments): ₪79 + ₪200 = ₪279/month per therapist
```

### For PazPaz (Confirmed Costs)

**Infrastructure (Already Running):**
- Hetzner Cloud CPX41: €46/month (~₪180/month)
  - 8 vCPU, 16GB RAM, 160GB NVMe
  - Includes: PostgreSQL, Redis, MinIO, all services
- Domain (pazpaz.health): ~₪50/year (~₪4/month)
- SSL Certificates: ₪0 (Let's Encrypt)
- **Subtotal: ~₪184/month**

**NEW: Grow API Access (Confirmed):**
- API monthly fee: ₪500 + VAT = **₪585/month**
- Required from testing phase onwards
- Includes: Full API access, webhook support, automatic invoicing

**Total Monthly Costs:**
- Infrastructure: ₪184
- Grow API: ₪585
- **Total: ₪769/month**

**Break-even Analysis:**

**Option 1: Transaction Fee Model (₪10 per appointment)**
- Break-even: ₪769 / ₪10 = **77 paid appointments/month**
- At 2 appointments per therapist/month: Need **39 active therapists**
- At 10 appointments per therapist/month: Need **8 active therapists**

**Option 2: Monthly Subscription (₪149/month)**
- Break-even: ₪769 / ₪149 = **6 paying therapists**
- After 6 therapists, all revenue is profit
- More predictable, easier to forecast

**Option 3: Hybrid (₪79/month + ₪5/appointment)**
- Fixed revenue from subscriptions helps cover Grow API fee
- Variable revenue scales with usage
- Break-even with mix: ~5-7 therapists depending on appointment volume

**Reality Check:**
The ₪585/month Grow API fee changes the economics significantly. You need meaningful adoption (6+ paying therapists with subscription model, or 8+ active therapists with transaction fees) to break even.

---

## 8A. CRITICAL DECISION: Is Grow API Worth ₪585/Month?

### The Economics Challenge

**Monthly API Fee: ₪585** is a significant fixed cost for an MVP. Let's analyze if this makes sense:

### Scenario Analysis

#### Pessimistic: Slow Growth
- Month 1-3: 2 paying therapists @ ₪149/month = ₪298 revenue
- **Loss: -₪287/month** (₪585 - ₪298)
- Need to subsidize ₪861 over 3 months

#### Realistic: Moderate Growth
- Month 1: 3 therapists = ₪447 revenue → Loss -₪138
- Month 2: 5 therapists = ₪745 revenue → **Profit +₪160**
- Month 3: 8 therapists = ₪1,192 revenue → Profit +₪607
- Cumulative: Small loss first month, profitable after

#### Optimistic: Strong Product-Market Fit
- Month 1: 6 therapists = ₪894 revenue → Profit +₪309
- Profitable from day 1
- Scales well beyond break-even

### Alternative: Delay Payments Until Product-Market Fit

**Option: Don't integrate Grow yet. Instead:**

1. **Validate PazPaz core features first** (2-3 months)
   - Focus on calendar, clients, SOAP notes
   - Get 20-30 therapists using PazPaz
   - Prove they love the product WITHOUT payments

2. **Survey users:** "Would you pay ₪149/month for automatic payment tracking?"
   - If 10+ say yes → Integrate Grow (you'll break even immediately)
   - If <5 say yes → Payment tracking isn't the killer feature

3. **Defer ₪585/month cost** until you have proven demand
   - Save ₪1,755 over 3 months
   - Use that money for marketing or other features
   - Less financial pressure during MVP phase

### My Recommendation

**Wait to integrate Grow until you have:**
- ✅ 30+ active therapists using PazPaz
- ✅ 10+ therapists saying "I'd pay for automatic payments"
- ✅ Confidence you can get 6+ paying therapists within 30 days of launch

**Why:**
- Avoids burning ₪585/month during slow growth phase
- Lets you validate core product first
- Payment tracking is important, but not if nobody uses PazPaz
- You can always add it later (2-3 week integration once demand is proven)

**However, if payments are truly the #1 requested feature:**
- And therapists say "I won't use PazPaz without automatic payments"
- Then it's worth the ₪585/month bet
- Budget for 3 months of losses (₪1,755) and aggressively drive adoption

### Questions to Ask Yourself

1. **Can PazPaz get traction without payments?**
   - If YES → Wait to integrate Grow
   - If NO → Payments are table stakes, integrate now

2. **Do you have 6+ therapists ready to pay ₪149/month on day 1?**
   - If YES → Integrate Grow, you'll break even immediately
   - If NO → Consider waiting until you do

3. **Can you afford ₪1,755 loss over 3 months?**
   - If YES and payments are critical → Go for it
   - If NO → Build other features first, validate demand

---

## 9. Competitive Comparison

### PazPaz with Grow (Post-MVP Option B)

**Therapist cost:**
- ₪149/month subscription
- ₪5.20 per ₪300 appointment (1.73%)
- **Total: ₪149 + ₪208 (40 appts) = ₪357/month**

### Alternatives

**Cal.com + Stripe:**
- Free calendar
- Stripe: 2.9% + ₪1.20 per transaction
- Per ₪300: ₪9.90
- **Total: ₪396/month (40 appts)**
- Con: No Bit support

**Square Appointments:**
- ₪0/month (free tier)
- 2.6% + ₪0.30 per transaction
- Per ₪300: ₪8.10
- **Total: ₪324/month (40 appts)**
- Con: No Bit support, not Israeli-focused

**Manual tracking:**
- ₪0 software cost
- Hours of manual work per week
- Risk of missed payments
- **Hidden cost: Therapist time**

**PazPaz Value Prop:**
- ✅ Lowest transaction fees (1.73% vs 2.6-2.9%)
- ✅ Bit support (preferred in Israel)
- ✅ Integrated with SOAP notes, client management
- ✅ Built for therapists specifically

---

## 10. Implementation Timeline

### Phase 1: Grow Integration (2-3 weeks)

**Week 1: Backend**
- [ ] Create Grow payment provider class
- [ ] Implement payment link creation API
- [ ] Build webhook handler endpoint
- [ ] Add webhook signature verification
- [ ] Database migration (add Grow fields)
- [ ] Unit tests for payment provider

**Week 2: Frontend**
- [ ] Add "Enable Payments" in Settings
- [ ] Bank details collection form (Option A) OR
- [ ] Grow userId input form (Option B)
- [ ] "Send Payment Request" button in appointment modal
- [ ] Payment link display with "Copy" button
- [ ] Real-time payment status badge updates

**Week 3: Testing & Polish**
- [ ] End-to-end payment flow testing (sandbox)
- [ ] Webhook security hardening
- [ ] Error handling (failed payments, network issues)
- [ ] Audit logging for all payment events
- [ ] Therapist onboarding guide/documentation
- [ ] Production deployment

### Phase 2: Monetization (Post-MVP)

**After validating with 20-50 therapists:**
- [ ] Decide on revenue model (subscription vs transaction fee)
- [ ] Update `companyCommission` parameter if using transaction fees
- [ ] Implement subscription billing system if using subscriptions
- [ ] Build revenue dashboard for PazPaz
- [ ] Update pricing page for therapists

---

## 11. Risk Mitigation

### Technical Risks

**Risk: Webhook reliability**
- Mitigation: Implement retry logic, poll payment status as backup

**Risk: Grow API downtime**
- Mitigation: Queue payment link creation, process when API returns

**Risk: Webhook spoofing (security)**
- Mitigation: Verify webhook signatures, log all webhook calls

### Business Risks

**Risk: Therapists abandon payment setup (Option B)**
- Mitigation: Detailed setup guide, video walkthrough, support chat

**Risk: Grow changes pricing or terms**
- Mitigation: Monitor contract, have backup gateway researched

**Risk: Low therapist adoption**
- Mitigation: MVP validation first, iterate on UX before scaling

---

## 12. Success Metrics

### MVP Validation (First 3 Months)

**Adoption Metrics:**
- Target: 50 therapists enable payments
- Conversion: 30%+ of sign-ups enable payments
- Time to enable: <10 minutes average

**Usage Metrics:**
- Payment links created: 500+ per month
- Payment completion rate: 70%+ (clients actually pay)
- Bit payment percentage: 60%+ (vs cards)

**Satisfaction Metrics:**
- Therapist NPS: 8+ out of 10
- Support tickets: <5% of transactions
- Positive feedback on automatic tracking

**Financial Metrics:**
- Total GMV: ₪100,000+ processed
- Average appointment value: ₪250-350
- Churn rate: <10% monthly

### Post-MVP Goals (Months 4-12)

- 200+ therapists using payments
- ₪1M+ monthly GMV
- Profitable with chosen revenue model
- <1% payment failure rate

---

## 13. Next Steps (UPDATED WITH CONFIRMED PRICING)

### IMMEDIATE DECISION REQUIRED

**Before any integration work, decide:**

1. **Launch payments now or wait?**
   - Cost: ₪585/month from testing phase onwards
   - Break-even: 6 paying therapists @ ₪149/month subscription
   - Question: Can you get 6 paying therapists within 60 days of launch?

2. **If launching now:**
   - Budget: ₪1,755 for first 3 months (assume losses)
   - Risk: Paying ₪585/month while building user base
   - Reward: Payments become competitive differentiator from day 1

3. **If waiting:**
   - Focus: Validate core PazPaz features first (2-3 months)
   - Goal: Get 30+ active therapists, survey payment demand
   - Decision point: Integrate Grow when 10+ therapists commit to paying

### If Proceeding with Grow Integration

**Phase 1: Platform Registration (Week 1)**
1. Apply for Grow platform API access
2. Provide business documentation
3. Get platform `apiKey` and sandbox credentials
4. Clarify userId creation process with technical team

**Phase 2: Testing & Development (Weeks 2-4)**
1. Set up sandbox environment
2. Test payment creation API
3. Test webhook notifications
4. Build therapist onboarding flow (Option A or B depending on confirmation)
5. Implement payment link generation
6. Build webhook handler with signature verification

**Phase 3: Beta Testing (Week 5)**
1. Onboard 2-3 therapist beta users
2. Test end-to-end flow with real Bit payments (small amounts)
3. Validate automatic status updates
4. Gather feedback on UX

**Phase 4: Production Launch (Week 6)**
1. Deploy to production
2. Enable for 6+ committed therapists
3. Monitor closely for issues
4. Iterate based on feedback

### Alternative Path: Phase Manual Payments First

**If not ready for ₪585/month commitment:**

1. **Keep current Phase 1 manual tracking** (no cost)
   - Therapists mark appointments as paid manually
   - Works fine for MVP validation
   - Zero API costs

2. **Validate demand over 2-3 months**
   - Survey therapists: "Would you pay ₪149/month for automatic Bit payments?"
   - Track how often therapists use manual payment tracking
   - Gauge actual vs perceived need

3. **Integrate Grow when demand proven**
   - Wait until 10+ therapists commit to subscription
   - Then pull trigger on ₪585/month API fee
   - Immediate break-even or profit from day 1

### Decision Points

**Proceed with Grow NOW if:**
- ✅ Payments are critical table stakes (therapists won't use PazPaz without it)
- ✅ You have budget for ₪1,755 over 3 months
- ✅ You can drive adoption aggressively (6+ therapists in 60 days)
- ✅ Automatic payments are your main competitive differentiator

**WAIT on Grow if:**
- ⚠️ Uncertain if therapists will pay for PazPaz
- ⚠️ Budget is tight (₪585/month is significant)
- ⚠️ Core features (calendar, SOAP notes) aren't polished yet
- ⚠️ Need to validate product-market fit first

**The ₪585/month API fee changes the game.** This isn't a "nice to have" expense you can absorb forever. You need paying customers relatively quickly to justify the cost.

---

## 14. Resources

### Documentation
- Grow API Docs: https://grow-il.readme.io/
- Platforms Guide: https://grow-il.readme.io/reference/api-guidelines-for-platforms-system-integrators
- Webhooks: https://grow-il.readme.io/docs/overview-7

### Grow Contact
- Website: https://grow.business/
- Email: support@grow.business
- WhatsApp/SMS: 052-7773144
- Hours: Sunday-Thursday, 9:00 AM - 10:00 PM

### Alternative Gateways (Plan B)
- Stripe Connect: https://stripe.com/connect
- PayMe (Isracard): https://paymeservice.com/
- Cardcom: https://www.cardcom.solutions/

---

## Appendix A: Full API Example

```python
# Complete flow from therapist onboarding to payment

# 1. Therapist enables payments (Option A)
async def enable_therapist_payments(
    workspace_id: str,
    bank_details: BankDetails,
    db: AsyncSession
):
    workspace = await db.get(Workspace, workspace_id)

    # Create sub-merchant via Grow API
    grow_provider = get_payment_provider("grow")
    result = await grow_provider.create_sub_merchant(
        bank_name=bank_details.bank_name,
        bank_branch=bank_details.bank_branch,
        account_number=bank_details.account_number,
        account_name=bank_details.account_name,
        id_number=bank_details.id_number,
    )

    # Store Grow userId
    workspace.grow_user_id = result["user_id"]
    workspace.grow_onboarding_status = result["status"]  # verified, pending, etc.
    workspace.payment_provider = "grow"

    await db.commit()

    return {"status": "success", "onboarding_status": result["status"]}

# 2. Create payment link for appointment
async def create_payment_link(
    appointment_id: str,
    db: AsyncSession
):
    appointment = await db.get(Appointment, appointment_id)
    workspace = await db.get(Workspace, appointment.workspace_id)

    if not workspace.grow_user_id:
        raise HTTPException(400, "Payments not enabled")

    # Create payment via Grow API
    grow_provider = get_payment_provider("grow")
    result = await grow_provider.create_payment_link(
        therapist_user_id=workspace.grow_user_id,
        amount=appointment.payment_price,
        description=f"Appointment with {appointment.client.name}",
        appointment_id=str(appointment.id),
        client_email=appointment.client.email,
        client_phone=appointment.client.phone,
        platform_commission=Decimal("0"),  # MVP: no platform fee
    )

    # Store payment link
    appointment.payment_link = result["payment_url"]
    appointment.grow_process_id = result["process_id"]
    appointment.payment_status = "payment_sent"

    await db.commit()

    # Send email/SMS to client with payment link
    await send_payment_request_email(appointment)

    return result

# 3. Webhook handler (called by Grow when client pays)
@router.post("/webhooks/grow")
async def grow_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    payload = dict(form_data)

    # Verify signature
    provider = get_payment_provider("grow")
    if not await provider.verify_webhook_signature(payload, request.headers.get("X-Grow-Signature")):
        raise HTTPException(403)

    # Update appointment
    appointment_id = payload["customFields[appointment_id]"]
    appointment = await db.get(Appointment, appointment_id)

    if payload["status"] == "שולם":  # Paid
        appointment.payment_status = "paid"
        appointment.paid_at = datetime.utcnow()
        appointment.grow_transaction_id = payload["transactionId"]

        await send_payment_confirmation_email(appointment)

    await db.commit()
    return {"status": "ok"}
```

---

## Appendix B: Database Schema Complete

```python
# Complete schema for Grow integration

from sqlalchemy import String, Numeric, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from decimal import Decimal

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

    # Existing workspace fields...
    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    # Payment configuration
    payment_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # NULL = payments disabled
    # "grow" = Grow payment provider enabled

    # Grow integration (Option A - Programmatic)
    grow_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    grow_onboarding_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # pending, verification_needed, verified, rejected

    # Payout information (for sub-account creation)
    payout_bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payout_bank_branch: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payout_account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payout_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payout_id_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payout_business_license: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    payment_enabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))

    # Existing appointment fields...
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50))

    # Payment tracking (Phase 1 - Manual tracking)
    payment_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(20), default="not_paid")
    # not_paid, payment_sent, paid, waived
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # bit, cash, card, bank_transfer, paybox, other
    payment_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Grow integration (Phase 2 - Automatic tracking)
    payment_link: Mapped[str | None] = mapped_column(String, nullable=True)
    # The URL client clicks to pay

    grow_process_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # Grow's payment process identifier (from createPaymentProcess response)

    grow_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Grow's transaction identifier (from webhook after payment)

    payment_link_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # When payment link was first sent to client

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="appointments")
    client: Mapped["Client"] = relationship(back_populates="appointments")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Optional: Track platform revenue (if using companyCommission)
class PlatformRevenue(Base):
    __tablename__ = "platform_revenue"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    appointment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("appointments.id"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))

    commission_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Amount PazPaz earned from this transaction

    grow_transaction_id: Mapped[str] = mapped_column(String(255))
    # Link to Grow transaction

    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # When commission was collected by Grow

    # Relationships
    appointment: Mapped["Appointment"] = relationship()
    workspace: Mapped["Workspace"] = relationship()
```

---

## Summary: Key Takeaways from Grow Conversation

### What We Learned

✅ **Grow API Available:** ₪500/month + VAT (₪585 total)
✅ **Pay As You Grow Pricing:** 1.4% to 0.9% + ₪1 (volume-based)
✅ **Bit Payments:** ₪1 flat fee (amazing for Israeli therapists!)
✅ **All Payment Methods:** Credit cards, Bit, Apple Pay, Google Pay, bank transfers
✅ **Auto Invoicing:** Included at no extra cost
✅ **Platform Model:** apiKey + userId + companyCommission supported

### The Big Question

**Is ₪585/month worth it for MVP?**

**Break-even: 6 paying therapists @ ₪149/month subscription**

Your decision depends on:
1. Can you get 6+ paying therapists within 60 days?
2. Is automatic payment tracking THE killer feature therapists demand?
3. Can you afford ₪1,755 over 3 months while building user base?

### Two Paths Forward

**Path A: Integrate Grow Now**
- **When:** Payments are table stakes, you have committed therapists, budget is available
- **Cost:** ₪585/month from testing onwards
- **Timeline:** 6 weeks to production
- **Risk:** Paying API fee during slow growth
- **Reward:** Competitive differentiator from day 1

**Path B: Wait & Validate**
- **When:** Uncertain about demand, tight budget, need to validate core features first
- **Cost:** ₪0 (keep manual payment tracking)
- **Timeline:** 2-3 months to validate, then 6 weeks to integrate
- **Risk:** Competitors may launch payments first
- **Reward:** Only pay ₪585/month when demand is proven

### My Recommendation

Given the ₪585/month API fee:

**Wait 60-90 days to validate PazPaz core features first**, then integrate Grow when you have:
- 30+ active therapists using PazPaz
- 10+ therapists saying "I'd pay ₪149/month for automatic payments"
- Confidence you can reach break-even (6 therapists) within 30 days of launch

**Why:** Avoids burning ₪1,755 while you're still finding product-market fit. Manual payment tracking works fine for MVP validation. You can always add Grow later (it's only 6 weeks of work).

**Exception:** If therapists explicitly say "I won't use PazPaz without automatic payments," then it's worth the investment upfront.

---

**Document Version:** 2.0
**Last Updated:** 2025-11-03 (Updated with Grow confirmed pricing)
**Status:** Confirmed pricing, decision pending on integration timing
