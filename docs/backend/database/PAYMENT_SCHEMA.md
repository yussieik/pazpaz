# Payment System Database Schema

**Status:** Phase 0 Complete (Foundation)
**Created:** October 30, 2025
**Last Updated:** October 30, 2025

---

## Overview

The payment system uses an **opt-in feature flag architecture** where payments are disabled by default and can be enabled per workspace. This document describes the database schema for the payment infrastructure.

**Key Principle:** All payment-related fields are nullable or have defaults to ensure zero-downtime deployments and backward compatibility.

---

## Tables

### 1. Workspaces (Extended)

Payment-related columns added to the existing `workspaces` table:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `payment_provider` | VARCHAR(50) | Yes | NULL | Payment provider: payplus, meshulam, stripe, or NULL (disabled) |
| `payment_provider_config` | JSONB | Yes | NULL | Encrypted payment provider API keys and configuration |
| `payment_auto_send` | BOOLEAN | No | false | Automatically send payment requests after appointment completion |
| `payment_send_timing` | VARCHAR(20) | No | 'immediately' | When to send: immediately, end_of_day, end_of_month, manual |
| `business_name` | VARCHAR(255) | Yes | NULL | Legal business name for receipts |
| `business_name_hebrew` | VARCHAR(255) | Yes | NULL | Business name in Hebrew (שם העסק בעברית) |
| `tax_id` | VARCHAR(20) | Yes | NULL | Israeli Tax ID (ת.ז. or ח.פ.) |
| `business_license` | VARCHAR(50) | Yes | NULL | Business license number (מספר רישיון עסק) |
| `business_address` | TEXT | Yes | NULL | Business address for tax receipts |
| `vat_registered` | BOOLEAN | No | false | Whether workspace is VAT registered (עוסק מורשה) |
| `vat_rate` | NUMERIC(5,2) | No | 17.00 | VAT rate percentage (default 17% for Israel) |
| `receipt_counter` | INTEGER | No | 0 | Auto-incrementing counter for receipt numbers |
| `tax_service_provider` | VARCHAR(50) | Yes | NULL | Third-party tax service: greeninvoice, morning, ness, NULL |
| `tax_service_config` | JSONB | Yes | NULL | Tax service API configuration |

**Feature Flag:**
- If `payment_provider` is NULL, payments are **disabled** for the workspace
- If `payment_provider` is set (payplus/meshulam/stripe), payments are **enabled**

---

### 2. Appointments (Extended)

Payment-related columns added to the existing `appointments` table:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `payment_price` | NUMERIC(10,2) | Yes | NULL | Appointment price in ILS (NULL = no price set) |
| `payment_status` | VARCHAR(20) | No | 'unpaid' | Payment status: unpaid, pending, paid, partially_paid, refunded, failed |
| `payment_auto_send` | BOOLEAN | Yes | NULL | Override workspace auto-send setting (NULL = use workspace default) |

**Payment Status Values:**
- `unpaid` - No payment request sent yet
- `pending` - Payment request sent, awaiting payment
- `paid` - Payment completed
- `partially_paid` - Partial payment received
- `refunded` - Payment refunded
- `failed` - Payment attempt failed

---

### 3. Payment Transactions (New Table)

Core payment tracking table (immutable log of all payment attempts):

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | gen_random_uuid() | Primary key |
| `workspace_id` | UUID | No | - | Foreign key to workspaces (CASCADE DELETE) |
| `appointment_id` | UUID | Yes | NULL | Optional foreign key to appointments (SET NULL) |
| `base_amount` | NUMERIC(10,2) | No | - | Amount before VAT (מחיר לפני מע"מ) |
| `vat_amount` | NUMERIC(10,2) | No | 0 | VAT amount (מע"מ) |
| `total_amount` | NUMERIC(10,2) | No | - | Total amount (base + VAT) |
| `currency` | VARCHAR(3) | No | 'ILS' | Currency code: ILS, USD, EUR |
| `payment_method` | VARCHAR(50) | No | - | Payment method: online_card, cash, bank_transfer, check, paypal, apple_pay, google_pay |
| `status` | VARCHAR(20) | No | 'pending' | Status: pending, completed, failed, refunded, cancelled |
| `provider` | VARCHAR(50) | Yes | NULL | Payment provider: payplus, meshulam, stripe, manual |
| `provider_transaction_id` | VARCHAR(255) | Yes | NULL | Provider transaction ID |
| `provider_payment_link` | TEXT | Yes | NULL | Payment link sent to client |
| `receipt_number` | VARCHAR(50) | Yes | NULL | Sequential receipt number (e.g., 2025-001234) |
| `receipt_issued` | BOOLEAN | No | false | Whether receipt was issued |
| `receipt_issued_at` | TIMESTAMPTZ | Yes | NULL | When receipt was issued |
| `receipt_pdf_url` | TEXT | Yes | NULL | S3/MinIO URL for receipt PDF |
| `created_at` | TIMESTAMPTZ | No | NOW() | When transaction was created |
| `completed_at` | TIMESTAMPTZ | Yes | NULL | When payment was completed |
| `failed_at` | TIMESTAMPTZ | Yes | NULL | When payment failed |
| `refunded_at` | TIMESTAMPTZ | Yes | NULL | When payment was refunded |
| `failure_reason` | TEXT | Yes | NULL | Reason for payment failure |
| `refund_reason` | TEXT | Yes | NULL | Reason for refund |
| `notes` | TEXT | Yes | NULL | Manual payment notes |
| `metadata` | JSONB | Yes | NULL | Provider-specific metadata |

**Foreign Keys:**
- `workspace_id` → `workspaces.id` (CASCADE DELETE)
- `appointment_id` → `appointments.id` (SET NULL)

**Payment Transaction as Immutable Log:**
- Payment transactions are never updated after creation (append-only)
- Status changes create new transaction records
- This ensures complete audit trail

---

### 4. Tax Receipts (New Table - Phase 2)

**Note:** Table created in Phase 0 migration, but functionality implemented in Phase 2.

Israeli tax-compliant receipts (מס קבלה):

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | UUID | No | Primary key |
| `workspace_id` | UUID | No | Foreign key to workspaces |
| `payment_transaction_id` | UUID | No | Foreign key to payment_transactions |
| `receipt_number` | VARCHAR(50) | No | Sequential receipt number |
| `receipt_date` | DATE | No | Date receipt was issued |
| `fiscal_year` | INTEGER | No | Fiscal year (e.g., 2025) |
| `allocation_number` | VARCHAR(50) | Yes | Israel Tax Authority allocation number (מספר הקצאה) |
| `tax_authority_status` | VARCHAR(20) | No | Status: not_submitted, pending, submitted, approved, rejected |
| `base_amount` | NUMERIC(10,2) | No | Amount before VAT |
| `vat_amount` | NUMERIC(10,2) | No | VAT amount |
| `total_amount` | NUMERIC(10,2) | No | Total amount |
| `currency` | VARCHAR(3) | No | Currency code |
| `client_name` | VARCHAR(255) | Yes | Client name (can be "Anonymous") |
| `client_tax_id` | VARCHAR(20) | Yes | Client tax ID (for B2B) |
| `service_description` | TEXT | No | Service description |
| `pdf_url` | TEXT | No | S3/MinIO URL for receipt PDF |
| `external_invoice_id` | VARCHAR(255) | Yes | GreenInvoice/Morning invoice ID |
| `external_invoice_url` | TEXT | Yes | External service invoice URL |
| `created_at` | TIMESTAMPTZ | No | When receipt was created |
| `updated_at` | TIMESTAMPTZ | No | When receipt was last updated |

---

### 5. Payment Refunds (New Table - Phase 2)

**Note:** Table created in Phase 0 migration, but functionality implemented in Phase 2.

Tracks all refund transactions:

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | UUID | No | Primary key |
| `workspace_id` | UUID | No | Foreign key to workspaces |
| `original_transaction_id` | UUID | No | Foreign key to payment_transactions |
| `refund_amount` | NUMERIC(10,2) | No | Refund amount |
| `refund_reason` | TEXT | Yes | Reason for refund |
| `refund_method` | VARCHAR(50) | Yes | Refund method |
| `provider` | VARCHAR(50) | Yes | Payment provider |
| `provider_refund_id` | VARCHAR(255) | Yes | Provider refund transaction ID |
| `status` | VARCHAR(20) | No | Status: pending, completed, failed |
| `created_at` | TIMESTAMPTZ | No | When refund was created |
| `completed_at` | TIMESTAMPTZ | Yes | When refund was completed |
| `metadata` | JSONB | Yes | Provider-specific refund metadata |

---

## Indexes

### Payment Transaction Indexes (8 total)

1. **idx_workspace_payments** - `(workspace_id, created_at DESC)`
   - Purpose: Workspace-scoped payment queries with time ordering
   - Use case: List all payments for a workspace

2. **idx_appointment_payments** - `(appointment_id)`
   - Purpose: Find payments for a specific appointment
   - Use case: Display payment status on appointment detail page

3. **idx_provider_txn** - `(provider_transaction_id)`
   - Purpose: Fast webhook lookup by provider transaction ID
   - Use case: Webhook processing from PayPlus/Meshulam/Stripe

4. **idx_payment_status** - `(status)`
   - Purpose: Filter payments by status
   - Use case: Find all pending/completed/failed payments

5. **idx_receipt_number** - `(receipt_number)`
   - Purpose: Fast receipt lookup
   - Use case: Search receipts by number

6. **idx_completed_at** - `(completed_at)`
   - Purpose: Date range queries for reporting
   - Use case: Monthly revenue reports

7. **idx_payment_method** - `(payment_method)`
   - Purpose: Analytics by payment method
   - Use case: Payment method breakdown reports

8. **idx_payments_workspace_date_status** - `(workspace_id, completed_at DESC, status)`
   - Purpose: Composite index for common reporting queries
   - Use case: Workspace revenue reports with status filtering

### Partial Index

**idx_payments_date_range** - `(workspace_id, completed_at) WHERE status = 'completed'`
- Purpose: Fast queries for completed payments only
- Use case: Revenue reporting (excludes pending/failed transactions)

### Appointment Payment Index

**idx_appointments_workspace_payment_status** - `(workspace_id, payment_status)`
- Purpose: Filter appointments by payment status per workspace
- Use case: "Show all unpaid appointments" queries

---

## Database Views (Phase 2)

### 1. monthly_revenue_summary

Aggregates payment revenue by month:

```sql
SELECT
    workspace_id,
    DATE_TRUNC('month', completed_at) AS month,
    COUNT(*) AS payment_count,
    SUM(base_amount) AS total_base_amount,
    SUM(vat_amount) AS total_vat_amount,
    SUM(total_amount) AS total_revenue,
    SUM(CASE WHEN payment_method = 'online_card' THEN total_amount ELSE 0 END) AS online_revenue,
    SUM(CASE WHEN payment_method = 'cash' THEN total_amount ELSE 0 END) AS cash_revenue,
    SUM(CASE WHEN payment_method = 'bank_transfer' THEN total_amount ELSE 0 END) AS bank_transfer_revenue
FROM payment_transactions
WHERE status = 'completed'
GROUP BY workspace_id, DATE_TRUNC('month', completed_at)
```

### 2. outstanding_payments

Lists pending payment requests:

```sql
SELECT
    workspace_id,
    COUNT(*) AS outstanding_count,
    SUM(total_amount) AS outstanding_amount,
    MIN(created_at) AS oldest_request,
    MAX(created_at) AS newest_request
FROM payment_transactions
WHERE status = 'pending' AND provider IS NOT NULL
GROUP BY workspace_id
```

### 3. payment_method_breakdown

Analytics by payment method:

```sql
SELECT
    workspace_id,
    payment_method,
    COUNT(*) AS transaction_count,
    SUM(total_amount) AS total_amount,
    AVG(total_amount) AS avg_amount
FROM payment_transactions
WHERE status = 'completed'
GROUP BY workspace_id, payment_method
```

---

## Triggers

### 1. generate_payment_receipt_number

Auto-generates sequential receipt numbers when `receipt_issued` is set to `true`:

```sql
CREATE OR REPLACE FUNCTION generate_receipt_number()
RETURNS TRIGGER AS $$
DECLARE
    new_counter INTEGER;
    new_receipt_number VARCHAR(50);
BEGIN
    IF NEW.receipt_issued = true AND (OLD.receipt_issued IS NULL OR OLD.receipt_issued = false) THEN
        -- Atomically increment counter
        UPDATE workspaces
        SET receipt_counter = receipt_counter + 1
        WHERE id = NEW.workspace_id
        RETURNING receipt_counter INTO new_counter;

        -- Generate receipt number: YYYY-NNNNNN
        new_receipt_number := EXTRACT(YEAR FROM NOW())::TEXT || '-' || LPAD(new_counter::TEXT, 6, '0');

        NEW.receipt_number := new_receipt_number;
        NEW.receipt_issued_at := NOW();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER generate_payment_receipt_number
BEFORE UPDATE ON payment_transactions
FOR EACH ROW
EXECUTE FUNCTION generate_receipt_number();
```

**Receipt Number Format:** `YYYY-NNNNNN` (e.g., `2025-000001`, `2025-000002`)

### 2. update_tax_receipts_updated_at

Auto-updates `updated_at` timestamp on tax_receipts table:

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_tax_receipts_updated_at
BEFORE UPDATE ON tax_receipts
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
```

---

## Entity Relationships

```
Workspace (1) ─────── (*) PaymentTransaction
    │                         │
    │                         │
    │                    (*) TaxReceipt
    │                         │
    │                    (*) PaymentRefund
    │
    └─────── (*) Appointment
                   │
                   └─────── (*) PaymentTransaction (optional)
```

**Key Relationships:**
- One **Workspace** has many **PaymentTransactions** (CASCADE DELETE)
- One **PaymentTransaction** optionally belongs to one **Appointment** (SET NULL)
- One **PaymentTransaction** has one **TaxReceipt** (CASCADE DELETE)
- One **PaymentTransaction** has many **PaymentRefunds** (CASCADE DELETE)

---

## VAT Calculation

**Formula:**
```
total_amount = base_amount + vat_amount
vat_amount = base_amount * (vat_rate / 100)
```

**Example (17% VAT):**
```
base_amount = 100.00 ILS
vat_rate = 17.00
vat_amount = 100.00 * 0.17 = 17.00 ILS
total_amount = 100.00 + 17.00 = 117.00 ILS
```

**VAT-Exempt Workspaces:**
- Set `vat_registered = false`
- `vat_amount` will be 0
- `total_amount` = `base_amount`

---

## Security Considerations

### Encrypted Fields

**`payment_provider_config` (JSONB):**
- Contains payment provider API keys
- **MUST** be encrypted at application layer before storing
- Use existing PHI encryption infrastructure (`ENCRYPTION_MASTER_KEY`)
- **NEVER** expose in API responses

**`tax_service_config` (JSONB):**
- Contains tax service API credentials
- Same encryption requirements as `payment_provider_config`

### Workspace Scoping

**All payment queries MUST filter by `workspace_id`:**
```sql
-- ✅ CORRECT
SELECT * FROM payment_transactions
WHERE workspace_id = :workspace_id
AND status = 'completed';

-- ❌ INCORRECT (leaks data across workspaces)
SELECT * FROM payment_transactions
WHERE status = 'completed';
```

### PII Handling

**Sensitive fields:**
- `business_name`, `business_name_hebrew`, `tax_id`, `business_license`
- `client_name`, `client_tax_id` (in tax_receipts)

**Best practices:**
- Never log these fields
- Mask in error messages
- Audit all access (use `audit_events` table)

---

## Performance Targets

**Phase 0:** No performance-critical queries (configuration only)
**Phase 1:** Payment request creation < 500ms p95
**Phase 2:** Revenue report queries < 1000ms p95

**Index Strategy:**
- Composite indexes for common query patterns
- Partial indexes for frequently filtered subsets
- Time-based ordering for reporting queries

---

## Migration History

**Migration:** `7530a2393547_add_payment_infrastructure`
**Date:** October 30, 2025
**Revises:** `84d3337219df`

**Changes:**
- Added 14 columns to `workspaces`
- Added 3 columns to `appointments`
- Created `payment_transactions` table (24 columns)
- Created `tax_receipts` table (25 columns)
- Created `payment_refunds` table (12 columns)
- Created 17 indexes
- Created 3 views
- Created 2 triggers

---

## Future Extensibility

### Multi-Currency Support (Future)

Current: One currency per workspace (set in `workspace.currency` or defaults to ILS)
Future: Multi-currency transactions with exchange rates

### Invoice Service Integration (Future)

Schema already supports third-party invoice services:
- `workspace.tax_service_provider` (greeninvoice, morning, ness)
- `workspace.tax_service_config` (API credentials)
- `tax_receipts.external_invoice_id` (invoice ID from external service)
- `tax_receipts.external_invoice_url` (link to external invoice)

---

## References

- [Payment Integration Plan](../PAYMENT_INTEGRATION_PLAN.md)
- [Payment Phase 0 Foundation](../PAYMENT_PHASE_0_FOUNDATION.md)
- [Tax-Compliant Schema SQL](../PAYMENT_SCHEMA_TAX_COMPLIANT.sql)
- [Payment Feature Flag Design](../PAYMENT_FEATURE_FLAG_DESIGN.md)
