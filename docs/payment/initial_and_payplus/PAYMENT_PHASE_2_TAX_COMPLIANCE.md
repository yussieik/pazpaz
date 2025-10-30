# Phase 2: Tax Compliance & Financial Reporting

**Duration:** 2-3 weeks
**Prerequisites:** Phase 1 complete (PayPlus integration, payment flow working)
**Goal:** Enable therapists to track complete revenue picture, generate tax-compliant receipts, and export data for accountants

---

## Overview

Phase 2 focuses on the "after payment" workflow - what therapists need for their business and tax obligations:
1. **Manual Payment Entry:** Track cash, bank transfers, checks (not all clients pay online)
2. **Receipt Generation:** Israeli tax receipts ("מס קבלה") with VAT breakdown
3. **Financial Reporting:** Dashboard showing monthly revenue, payment methods, outstanding payments
4. **Data Export:** Excel/CSV export for accountants

**Key Principle:** Simple is better than perfect. Basic receipts and exports are more valuable than complex tax automation.

---

## Deliverables Checklist

### **Week 1: Manual Payment Entry & Receipt Generation**

#### **1.1 Manual Payment Entry**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **1.1.1** Create manual payment entry API endpoint
  - Endpoint: `POST /api/v1/appointments/{id}/manual-payment`
  - Input: `{total_amount, payment_method, payment_date, notes}`
  - Validate: therapist can only add payments to their own appointments
  - Calculate VAT breakdown automatically
  - Create `PaymentTransaction` with `provider="manual"`, `status="completed"`
  - Update appointment `payment_status` to "paid"
  - **Deliverable:** Manual payment endpoint in `src/pazpaz/api/v1/payments.py`

- [ ] **1.1.2** Support multiple payment methods
  - Add validation for `payment_method` enum: "cash", "bank_transfer", "check", "paypal", "venmo"
  - Document each method in code comments
  - **Deliverable:** Payment method enum and validation

- [ ] **1.1.3** Allow backdated payments
  - Accept `payment_date` in request (defaults to today)
  - Validate: payment_date cannot be in future
  - Set `completed_at` to provided `payment_date`
  - **Deliverable:** Backdating logic in manual payment creation

**Implementation example:**
```python
# src/pazpaz/api/v1/payments.py (addition)

class ManualPaymentRequest(BaseModel):
    total_amount: Decimal
    payment_method: Literal["cash", "bank_transfer", "check", "paypal", "venmo"]
    payment_date: date
    notes: str | None = None
    vat_included: bool = True  # If false, total_amount is before VAT

@router.post("/appointments/{appointment_id}/manual-payment")
async def add_manual_payment(
    appointment_id: uuid.UUID,
    request: ManualPaymentRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Add manual payment (cash, bank transfer, etc.) to appointment."""

    # Fetch appointment
    appointment = await db.get(Appointment, appointment_id)
    if not appointment or appointment.workspace_id != workspace.id:
        raise HTTPException(404, "Appointment not found")

    # Validate payment date not in future
    if request.payment_date > date.today():
        raise HTTPException(400, "Payment date cannot be in future")

    # Calculate VAT breakdown
    if request.vat_included:
        base_amount, vat_amount, total_amount = PaymentService.calculate_vat(
            request.total_amount, workspace.vat_rate, workspace.vat_registered
        )
    else:
        # Total amount is before VAT, calculate total
        vat_amount = (request.total_amount * workspace.vat_rate / 100) if workspace.vat_registered else 0
        total_amount = request.total_amount + vat_amount
        base_amount = request.total_amount

    # Create transaction
    transaction = PaymentTransaction(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        appointment_id=appointment.id,
        base_amount=base_amount,
        vat_amount=vat_amount,
        total_amount=total_amount,
        currency="ILS",
        payment_method=request.payment_method,
        status="completed",
        provider="manual",
        completed_at=datetime.combine(request.payment_date, datetime.min.time(), tzinfo=timezone.utc),
        notes=request.notes,
    )

    db.add(transaction)

    # Update appointment status
    appointment.payment_status = "paid"

    await db.commit()
    await db.refresh(transaction)

    return PaymentTransactionResponse(
        id=transaction.id,
        appointment_id=transaction.appointment_id,
        total_amount=str(transaction.total_amount),
        currency=transaction.currency,
        status=transaction.status,
        provider=transaction.provider,
        payment_link=None,
        created_at=transaction.created_at.isoformat(),
    )
```

#### **1.2 Receipt PDF Generation**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **1.2.1** Research PDF generation libraries
  - **Option 1:** ReportLab (Python, full control, complex)
  - **Option 2:** WeasyPrint (HTML → PDF, easier styling)
  - **Option 3:** External service (DocRaptor, CloudConvert)
  - **Decision:** Recommend WeasyPrint (HTML templates easier to maintain)
  - **Deliverable:** Decision documented in `/docs/backend/pdf_generation_decision.md`

- [ ] **1.2.2** Add `uv add weasyprint` dependency
  - **Deliverable:** Updated `pyproject.toml`

- [ ] **1.2.3** Create receipt HTML template
  - Jinja2 template with workspace branding
  - Hebrew support (RTL layout)
  - VAT breakdown section
  - Receipt number, date, business details
  - **Deliverable:** `backend/templates/receipt_template.html`

- [ ] **1.2.4** Implement receipt generation service
  - Method: `generate_receipt_pdf(transaction: PaymentTransaction) -> str`
  - Auto-increment workspace receipt counter
  - Generate receipt number: `YYYY-NNNNNN` (e.g., "2025-000001")
  - Render HTML template with transaction data
  - Convert to PDF using WeasyPrint
  - Upload PDF to S3/MinIO
  - Update transaction with receipt details
  - **Deliverable:** `src/pazpaz/services/receipt_service.py`

- [ ] **1.2.5** Implement receipt number auto-increment trigger
  - PostgreSQL function to atomically increment `workspace.receipt_counter`
  - Trigger on `payment_transactions` update when `receipt_issued` set to true
  - **Deliverable:** Database trigger (can be in migration or separate SQL file)

**Implementation example:**
```python
# src/pazpaz/services/receipt_service.py

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from decimal import Decimal
import uuid
from datetime import datetime

from pazpaz.models import PaymentTransaction, Workspace
from pazpaz.storage import upload_file  # Assuming S3/MinIO upload function exists

class ReceiptService:
    """Generate tax-compliant receipts for payments."""

    def __init__(self):
        self.template_env = Environment(
            loader=FileSystemLoader("backend/templates")
        )

    async def generate_receipt_pdf(
        self,
        transaction: PaymentTransaction,
        db: AsyncSession,
    ) -> str:
        """
        Generate PDF receipt for payment transaction.

        Returns:
            URL of uploaded PDF
        """
        workspace = transaction.workspace

        # Auto-increment receipt counter
        async with db.begin_nested():
            await db.execute(
                update(Workspace)
                .where(Workspace.id == workspace.id)
                .values(receipt_counter=Workspace.receipt_counter + 1)
            )
            await db.refresh(workspace)

        # Generate receipt number
        receipt_number = f"{datetime.now().year}-{workspace.receipt_counter:06d}"

        # Render HTML template
        template = self.template_env.get_template("receipt_template.html")
        html_content = template.render(
            workspace=workspace,
            transaction=transaction,
            receipt_number=receipt_number,
            receipt_date=transaction.completed_at.strftime("%d/%m/%Y"),
        )

        # Convert to PDF
        pdf_bytes = HTML(string=html_content).write_pdf()

        # Upload to S3/MinIO
        pdf_filename = f"receipts/{receipt_number}.pdf"
        pdf_url = await upload_file(pdf_filename, pdf_bytes)

        # Update transaction
        transaction.receipt_number = receipt_number
        transaction.receipt_issued = True
        transaction.receipt_issued_at = datetime.now(timezone.utc)
        transaction.receipt_pdf_url = pdf_url

        await db.commit()

        return pdf_url
```

**HTML template example:**
```html
<!-- backend/templates/receipt_template.html -->
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <title>Receipt {{ receipt_number }}</title>
    <style>
        body { font-family: 'Arial', sans-serif; direction: rtl; }
        .header { text-align: center; margin-bottom: 30px; }
        .business-details { margin-bottom: 20px; }
        .receipt-details { margin-bottom: 20px; }
        .financial-breakdown { border: 1px solid #ddd; padding: 15px; }
        .total { font-size: 18px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ workspace.business_name }}</h1>
        <p>{{ workspace.business_address }}</p>
        <p>ת.ז. / ח.פ.: {{ workspace.tax_id }}</p>
        {% if workspace.vat_registered %}
        <p>עוסק מורשה</p>
        {% endif %}
    </div>

    <div class="receipt-details">
        <p><strong>מספר קבלה:</strong> {{ receipt_number }}</p>
        <p><strong>תאריך:</strong> {{ receipt_date }}</p>
    </div>

    <div class="financial-breakdown">
        <h2>פירוט תשלום</h2>
        {% if workspace.vat_registered %}
        <p>מחיר לפני מע"מ: ₪{{ transaction.base_amount }}</p>
        <p>מע"מ ({{ workspace.vat_rate }}%): ₪{{ transaction.vat_amount }}</p>
        {% endif %}
        <p class="total">סה"כ לתשלום: ₪{{ transaction.total_amount }}</p>
        <p><strong>אמצעי תשלום:</strong> {{ transaction.payment_method }}</p>
    </div>

    <div class="footer" style="margin-top: 40px; text-align: center;">
        <p>קבלה זו הופקה באמצעות מערכת PazPaz</p>
    </div>
</body>
</html>
```

#### **1.3 Receipt API Endpoints**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **1.3.1** Implement `POST /api/v1/payments/{transaction_id}/generate-receipt`
  - Generate receipt PDF for payment transaction
  - Return receipt number and PDF URL
  - **Deliverable:** Receipt generation endpoint

- [ ] **1.3.2** Implement `GET /api/v1/receipts/{receipt_number}/download`
  - Download receipt PDF
  - Set proper headers: `Content-Disposition: attachment; filename="receipt-{number}.pdf"`
  - **Deliverable:** Receipt download endpoint

- [ ] **1.3.3** Implement `POST /api/v1/receipts/{receipt_number}/resend-email`
  - Resend receipt email to client
  - **Deliverable:** Receipt email resend endpoint

---

### **Week 2: Financial Reporting & Analytics**

#### **2.1 Financial Reports Backend**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **2.1.1** Implement revenue summary API
  - Endpoint: `GET /api/v1/workspaces/{workspace_id}/reports/revenue`
  - Query params: `start_date`, `end_date`, `group_by` (month/week/year)
  - Calculate: total revenue, total VAT, total net, payment count
  - Group by period (monthly, weekly, quarterly)
  - **Deliverable:** Revenue summary endpoint

- [ ] **2.1.2** Implement payment method breakdown
  - Group payments by method (online_card, cash, bank_transfer, etc.)
  - Calculate totals and percentages
  - **Deliverable:** Payment method breakdown in revenue endpoint

- [ ] **2.1.3** Implement outstanding payments query
  - Find all "pending" payment transactions
  - Calculate total outstanding amount
  - Show oldest/newest pending request dates
  - **Deliverable:** Outstanding payments endpoint

**Implementation example:**
```python
# src/pazpaz/api/v1/reports.py (new file)

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date
from pydantic import BaseModel

from pazpaz.db import get_db
from pazpaz.dependencies import get_current_workspace
from pazpaz.models import Workspace, PaymentTransaction

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

class RevenueReport(BaseModel):
    total_revenue: str
    total_vat: str
    total_net: str
    payment_count: int
    by_period: list[dict]
    by_payment_method: dict[str, str]
    outstanding: str

@router.get("/revenue", response_model=RevenueReport)
async def get_revenue_report(
    start_date: date = Query(...),
    end_date: date = Query(...),
    group_by: Literal["month", "week", "year"] = Query(default="month"),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Generate revenue report for workspace."""

    # Query completed payments in date range
    stmt = select(PaymentTransaction).where(
        PaymentTransaction.workspace_id == workspace.id,
        PaymentTransaction.status == "completed",
        PaymentTransaction.completed_at >= start_date,
        PaymentTransaction.completed_at <= end_date,
    )
    result = await db.execute(stmt)
    transactions = result.scalars().all()

    # Calculate totals
    total_revenue = sum(t.total_amount for t in transactions)
    total_vat = sum(t.vat_amount for t in transactions)
    total_net = sum(t.base_amount for t in transactions)
    payment_count = len(transactions)

    # Group by payment method
    by_payment_method = {}
    for txn in transactions:
        method = txn.payment_method
        by_payment_method[method] = by_payment_method.get(method, 0) + txn.total_amount

    # Group by period (simplified - use pandas in real implementation)
    by_period = []
    # ... grouping logic here ...

    # Calculate outstanding (pending online payments)
    stmt_outstanding = select(func.sum(PaymentTransaction.total_amount)).where(
        PaymentTransaction.workspace_id == workspace.id,
        PaymentTransaction.status == "pending",
        PaymentTransaction.provider.isnot(None),  # Online payments only
    )
    result_outstanding = await db.execute(stmt_outstanding)
    outstanding = result_outstanding.scalar() or 0

    return RevenueReport(
        total_revenue=str(total_revenue),
        total_vat=str(total_vat),
        total_net=str(total_net),
        payment_count=payment_count,
        by_period=by_period,
        by_payment_method={k: str(v) for k, v in by_payment_method.items()},
        outstanding=str(outstanding),
    )
```

#### **2.2 Excel/CSV Export**
**Owner:** `fullstack-backend-specialist` agent

- [ ] **2.2.1** Add `uv add openpyxl pandas` dependencies
  - For Excel generation
  - **Deliverable:** Updated `pyproject.toml`

- [ ] **2.2.2** Implement Excel export service
  - Method: `export_transactions_to_excel(workspace_id, start_date, end_date) -> bytes`
  - Create Excel file with tabs: Summary, Monthly, Transactions
  - Include formulas for totals
  - **Deliverable:** `src/pazpaz/services/export_service.py`

- [ ] **2.2.3** Implement export API endpoint
  - Endpoint: `GET /api/v1/workspaces/{workspace_id}/reports/export`
  - Query params: `format=xlsx` or `format=csv`, `start_date`, `end_date`
  - Return file download
  - **Deliverable:** Export endpoint

**Implementation example:**
```python
# src/pazpaz/services/export_service.py

import pandas as pd
from io import BytesIO
from datetime import date

from pazpaz.models import PaymentTransaction

class ExportService:
    """Export financial data to Excel/CSV."""

    async def export_transactions_to_excel(
        self,
        transactions: list[PaymentTransaction],
        workspace_name: str,
    ) -> bytes:
        """Generate Excel file with transaction data."""

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                "Date": t.completed_at.date() if t.completed_at else None,
                "Receipt #": t.receipt_number,
                "Client": t.appointment.client.full_name if t.appointment else "N/A",
                "Payment Method": t.payment_method,
                "Base Amount": float(t.base_amount),
                "VAT": float(t.vat_amount),
                "Total": float(t.total_amount),
                "Status": t.status,
                "Notes": t.notes or "",
            }
            for t in transactions
        ])

        # Create Excel file with multiple sheets
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Sheet 1: Summary
            summary_df = pd.DataFrame({
                "Metric": ["Total Revenue", "Total VAT", "Total Net", "Payment Count"],
                "Value": [
                    df["Total"].sum(),
                    df["VAT"].sum(),
                    df["Base Amount"].sum(),
                    len(df),
                ],
            })
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

            # Sheet 2: Transactions
            df.to_excel(writer, sheet_name="Transactions", index=False)

            # Sheet 3: Monthly breakdown
            df["Month"] = pd.to_datetime(df["Date"]).dt.to_period("M")
            monthly = df.groupby("Month").agg({
                "Total": "sum",
                "VAT": "sum",
                "Base Amount": "sum",
                "Receipt #": "count",
            }).reset_index()
            monthly.columns = ["Month", "Revenue", "VAT", "Net", "Count"]
            monthly.to_excel(writer, sheet_name="Monthly", index=False)

        output.seek(0)
        return output.getvalue()
```

---

### **Week 3: Frontend - Financial Dashboard & UI**

#### **3.1 Manual Payment UI**
**Owner:** `fullstack-frontend-specialist` agent

- [ ] **3.1.1** Create `ManualPaymentModal.vue` component
  - Form: amount, payment method dropdown, date picker, notes textarea
  - Checkbox: "VAT included" (default: true)
  - Validation: amount > 0, date not in future
  - **Deliverable:** Manual payment modal component

- [ ] **3.1.2** Add "Add Manual Payment" button to appointment detail
  - Show button next to "Send Payment Request"
  - Open modal when clicked
  - **Deliverable:** Updated `AppointmentDetail.vue`

- [ ] **3.1.3** Implement manual payment form submission
  - Call API: `POST /api/v1/appointments/{id}/manual-payment`
  - Update appointment status on success
  - Show success toast
  - **Deliverable:** Form submission logic

#### **3.2 Financial Dashboard**
**Owner:** `fullstack-frontend-specialist` agent

- [ ] **3.2.1** Create `FinancialDashboard.vue` page
  - Route: `/reports/financial`
  - Date range picker (default: current month)
  - Summary cards: Total Revenue, Paid Sessions, Outstanding
  - Revenue chart (monthly/weekly)
  - Payment method breakdown (pie chart or bar chart)
  - Transactions table
  - Export button
  - **Deliverable:** Financial dashboard page

- [ ] **3.2.2** Implement revenue chart visualization
  - Use Chart.js or similar library
  - Bar chart showing revenue by period
  - **Deliverable:** Revenue chart component

- [ ] **3.2.3** Implement transactions table
  - Columns: Date, Receipt #, Client, Method, Amount, Status
  - Sortable, filterable
  - **Deliverable:** Transactions table component

- [ ] **3.2.4** Implement Excel export action
  - Button: "Export to Excel"
  - Download file: `GET /api/v1/workspaces/{id}/reports/export?format=xlsx`
  - Show loading state
  - **Deliverable:** Export action

#### **3.3 Receipt UI**
**Owner:** `fullstack-frontend-specialist` agent

- [ ] **3.3.1** Add "Generate Receipt" button to payment transactions
  - Show button for completed payments without receipt
  - Call API: `POST /api/v1/payments/{transaction_id}/generate-receipt`
  - Update UI with receipt number and download link
  - **Deliverable:** Receipt generation button

- [ ] **3.3.2** Add "View Receipt" / "Download Receipt" buttons
  - Show for transactions with receipt
  - Open PDF in new tab or trigger download
  - **Deliverable:** Receipt view/download buttons

---

### **Week 3: Testing & QA**

#### **4.1 Backend Tests**
**Owner:** `backend-qa-specialist` agent

- [ ] **4.1.1** Test manual payment entry
  - Test VAT calculation (with/without VAT registration)
  - Test backdated payments
  - Test workspace isolation
  - **Deliverable:** Manual payment tests

- [ ] **4.1.2** Test receipt generation
  - Test receipt number auto-increment
  - Test PDF generation (HTML → PDF)
  - Test S3 upload
  - Test Hebrew (RTL) layout
  - **Deliverable:** Receipt generation tests

- [ ] **4.1.3** Test financial reports
  - Test revenue calculations
  - Test date range filtering
  - Test payment method grouping
  - **Deliverable:** Financial report tests

- [ ] **4.1.4** Test Excel export
  - Test file generation
  - Test data accuracy (match database)
  - Test formulas in Excel file
  - **Deliverable:** Export tests

#### **4.2 Manual Testing**
**Owner:** You (QA)

- [ ] **4.2.1** Test manual payment workflow
  - Add cash payment to appointment
  - Verify appointment marked as paid
  - Generate receipt
  - Download receipt PDF
  - Verify receipt looks correct (Hebrew layout, VAT breakdown)
  - **Deliverable:** Manual test checklist

- [ ] **4.2.2** Test financial dashboard
  - View dashboard with sample data
  - Verify totals match database
  - Export to Excel
  - Open Excel file, verify data
  - **Deliverable:** Dashboard test checklist

---

## Acceptance Criteria

**Phase 2 is complete when:**

✅ **Manual payments working** - Can add cash/bank transfer payments to appointments
✅ **Receipts generated** - PDF receipts with VAT breakdown and Hebrew support
✅ **Financial dashboard working** - Summary cards, charts, transactions table
✅ **Excel export working** - Can download Excel file with all transaction data
✅ **Tests passing** - All unit and integration tests pass
✅ **UI complete** - Manual payment modal, financial dashboard, receipt buttons
✅ **Documentation complete** - User guides for receipts and financial reports

---

## Risk Mitigation

### **Risk:** PDF generation library issues (WeasyPrint installation problems)
**Mitigation:**
- Test WeasyPrint installation in Docker container early
- Have fallback: generate plain HTML "receipt" if PDF fails
- Document system dependencies (e.g., `libpango`, `libcairo`)

### **Risk:** Receipt format doesn't meet Israeli tax requirements
**Mitigation:**
- Consult with Israeli accountant on receipt format
- Include disclaimer: "For official tax receipts, use GreenInvoice" (Phase 3)
- Make receipt template easily customizable

### **Risk:** Excel export fails for large datasets (>10,000 transactions)
**Mitigation:**
- Add pagination to export (max 5,000 transactions per file)
- Add background job for large exports (email download link)
- Show warning if date range too large

---

## Next Steps After Phase 2

Once Phase 2 is complete, you can proceed to:
- **Phase 3**: Multi-provider support (Stripe, Meshulam alternative)
- **Optional Phase 4**: GreenInvoice integration for full tax authority compliance

---

## Notes

- **Simplicity over perfection:** Basic receipts are better than no receipts
- **Don't over-engineer exports:** Excel with 3 tabs is sufficient
- **Focus on Israeli market first:** Hebrew RTL support is critical
- **Accountant-friendly:** Export format should be easy for accountants to work with
- **Defer complex tax features:** Full Tax Authority integration can wait (Phase 3+)
