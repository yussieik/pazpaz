# Payment System Architecture V2: Manual + Automated Providers

**Status:** Architecture Design Document
**Version:** 2.0
**Created:** 2025-11-02
**Purpose:** Define a maintainable, extensible payment system supporting both manual and automated payment tracking

---

## Executive Summary

This document defines a **dual-mode payment system** that:
1. **Manual Mode (Phase 1):** Simple bank transfer tracking (immediate need)
2. **Automated Mode (Phase 2+):** Provider integrations (Bit, PayBox, PayPlus, Stripe)

**Key Design Principles:**
- ✅ **Feature Flag Architecture:** Opt-in, reversible, workspace-scoped
- ✅ **Strategy Pattern:** Pluggable payment providers
- ✅ **Separation of Concerns:** Manual tracking ≠ Automated providers
- ✅ **Zero Breaking Changes:** Backwards compatible with existing appointments
- ✅ **Progressive Enhancement:** Start simple, add complexity when needed

---

## Architecture Overview

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Workspace Model                          │
├─────────────────────────────────────────────────────────────┤
│  Manual Tracking (Always Available):                        │
│    - bank_account_details: str | None                       │
│                                                              │
│  Automated Providers (Optional, Future):                    │
│    - payment_provider: "manual" | "bit" | "paybox" | null   │
│    - payment_provider_config: JSONB (encrypted)             │
│    - payment_auto_send: bool                                │
│    - payment_send_timing: str                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Payment Provider Registry                       │
│         (Factory Pattern + Strategy Pattern)                 │
├─────────────────────────────────────────────────────────────┤
│  Available Providers:                                        │
│    - ManualProvider (bank transfer, Bit, PayBox manual)     │
│    - BitProvider (future: Bit API integration)              │
│    - PayBoxProvider (future: PayBox API integration)        │
│    - PayPlusProvider (future: re-add if needed)             │
│    - StripeProvider (future: international payments)        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Appointment Model                           │
├─────────────────────────────────────────────────────────────┤
│  Payment Fields (Provider-Agnostic):                        │
│    - payment_price: Decimal                                 │
│    - payment_status: "not_paid" | "paid" | "payment_sent"  │
│    - payment_method: "bank_transfer" | "bit" | "paybox"    │
│    - payment_notes: str                                     │
│    - paid_at: datetime                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema Design

### Workspace Table

```python
class Workspace(Base):
    __tablename__ = "workspaces"

    # ============================================================================
    # MANUAL PAYMENT TRACKING (Phase 1 - Implemented Now)
    # ============================================================================
    bank_account_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Bank account details for manual payment tracking. "
                "Therapist shares this with clients via WhatsApp/SMS. "
                "Example: 'Bank Leumi, Account: 12-345-67890, Branch: 789'"
    )

    # ============================================================================
    # AUTOMATED PAYMENT PROVIDERS (Phase 2+ - Reserved for Future)
    # ============================================================================
    payment_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Automated payment provider: 'manual', 'bit', 'paybox', 'payplus', 'stripe', null. "
                "NULL = no automated provider configured (use manual tracking only). "
                "'manual' = explicit manual-only mode (no automation, just tracking)."
    )

    payment_provider_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Provider-specific configuration (encrypted). "
                "Format varies by provider: "
                "  manual: null (no config needed) "
                "  bit: {api_key, merchant_id} "
                "  paybox: {terminal_id, api_secret} "
                "  payplus: {api_key, page_uid, webhook_secret} "
                "  stripe: {api_key, webhook_secret}"
    )

    payment_auto_send: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Auto-send payment requests after appointment completion "
                "(only applies to automated providers, not manual)"
    )

    payment_send_timing: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
        server_default="manual",
        comment="When to send payment requests: 'immediately', 'end_of_day', 'end_of_month', 'manual'. "
                "Only applies to automated providers."
    )

    # ============================================================================
    # COMPUTED PROPERTIES
    # ============================================================================
    @property
    def payments_enabled(self) -> bool:
        """
        Check if ANY payment tracking is enabled (manual OR automated).

        Returns True if:
        - bank_account_details is configured (manual tracking), OR
        - payment_provider is configured (automated provider)

        This allows therapists to use manual OR automated, or BOTH.
        """
        return (
            self.bank_account_details is not None or
            self.payment_provider is not None
        )

    @property
    def manual_payments_enabled(self) -> bool:
        """Check if manual payment tracking is configured."""
        return self.bank_account_details is not None

    @property
    def automated_payments_enabled(self) -> bool:
        """Check if automated payment provider is configured."""
        return self.payment_provider is not None
```

### Appointment Table (Unchanged)

```python
class Appointment(Base):
    __tablename__ = "appointments"

    # Payment tracking fields (provider-agnostic)
    payment_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Actual price for this appointment"
    )

    payment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PaymentStatus.NOT_PAID.value,
        comment="Payment status: not_paid, paid, payment_sent, waived"
    )

    payment_method: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Payment method: cash, card, bank_transfer, bit, paybox, other"
    )

    payment_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Free-text notes about payment"
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When payment was received/confirmed"
    )
```

**Key Design Decision:** Appointment payment fields are **provider-agnostic**. They work identically for manual tracking and automated providers. This prevents tight coupling.

---

## Payment Provider Strategy Pattern

### Abstract Base Provider

```python
from abc import ABC, abstractmethod
from typing import Protocol

class PaymentProvider(ABC):
    """
    Abstract base class for all payment providers.

    Design Pattern: Strategy Pattern
    - Each provider implements this interface
    - Workspace selects which strategy to use
    - Easy to add new providers without changing existing code (Open/Closed Principle)
    """

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider identifier (e.g., 'manual', 'bit', 'paybox')."""
        pass

    @abstractmethod
    def supports_automated_requests(self) -> bool:
        """Return True if provider supports automated payment request generation."""
        pass

    @abstractmethod
    async def validate_config(self, config: dict) -> tuple[bool, str]:
        """
        Validate provider configuration.

        Returns:
            (is_valid, error_message)

        Example:
            For Bit: Validate API key format, check merchant_id exists
            For Manual: Always return (True, "")
        """
        pass

    @abstractmethod
    async def create_payment_request(
        self,
        appointment: Appointment,
        config: dict
    ) -> str | None:
        """
        Create a payment request for an appointment.

        Returns:
            Payment link URL (for automated providers)
            None (for manual providers - no link needed)

        Example:
            Bit: Generate payment link via Bit API
            Manual: Return None (therapist sends bank details manually)
        """
        pass

    @abstractmethod
    async def check_payment_status(
        self,
        appointment: Appointment,
        config: dict
    ) -> PaymentStatus:
        """
        Check current payment status.

        Returns:
            Current payment status

        Example:
            Bit: Query Bit API for transaction status
            Manual: Return current appointment.payment_status (no external check)
        """
        pass
```

### Manual Provider Implementation (Phase 1)

```python
class ManualPaymentProvider(PaymentProvider):
    """
    Manual payment provider for bank transfers and manual tracking.

    This provider does NOT integrate with any external API.
    It simply provides a consistent interface for manual payment workflows.

    Use Cases:
    - Therapist shares bank account details via WhatsApp
    - Client pays via bank transfer, Bit app, or PayBox app
    - Therapist manually marks appointment as paid
    """

    def get_provider_name(self) -> str:
        return "manual"

    def supports_automated_requests(self) -> bool:
        return False  # No automation, therapist handles everything

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        # Manual provider has no config requirements
        return (True, "")

    async def create_payment_request(
        self,
        appointment: Appointment,
        config: dict
    ) -> str | None:
        # Manual provider doesn't generate payment links
        # Therapist copies bank details from workspace.bank_account_details
        return None

    async def check_payment_status(
        self,
        appointment: Appointment,
        config: dict
    ) -> PaymentStatus:
        # Manual provider can't check external status
        # Just return what's in the database
        return appointment.payment_status
```

### Future Provider Implementations (Phase 2+)

```python
class BitPaymentProvider(PaymentProvider):
    """
    Bit payment provider (Israeli mobile payment app).

    Integration: Bit Business API
    Features:
    - Generate payment links
    - Webhook for payment confirmations
    - Automatic status updates
    """

    def get_provider_name(self) -> str:
        return "bit"

    def supports_automated_requests(self) -> bool:
        return True  # Can auto-generate payment links

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        # Validate Bit API key and merchant ID
        if "api_key" not in config:
            return (False, "Bit API key is required")
        if "merchant_id" not in config:
            return (False, "Merchant ID is required")

        # Test API connection
        try:
            await self._test_bit_api_connection(config)
            return (True, "")
        except Exception as e:
            return (False, f"Bit API connection failed: {e}")

    async def create_payment_request(
        self,
        appointment: Appointment,
        config: dict
    ) -> str:
        # Call Bit API to generate payment link
        link = await bit_api.create_payment_link(
            amount=appointment.payment_price,
            description=f"Appointment {appointment.id}",
            merchant_id=config["merchant_id"],
            api_key=config["api_key"]
        )
        return link

    async def check_payment_status(
        self,
        appointment: Appointment,
        config: dict
    ) -> PaymentStatus:
        # Query Bit API for payment status
        status = await bit_api.get_payment_status(
            transaction_id=appointment.payment_transaction_id,
            api_key=config["api_key"]
        )
        return self._map_bit_status_to_internal(status)
```

---

## Provider Registry (Factory Pattern)

```python
class PaymentProviderRegistry:
    """
    Registry of available payment providers.

    Design Pattern: Factory Pattern
    - Centralizes provider instantiation
    - Makes it easy to add new providers
    - Supports runtime provider selection
    """

    _providers: dict[str, type[PaymentProvider]] = {}

    @classmethod
    def register(cls, provider_name: str, provider_class: type[PaymentProvider]):
        """Register a payment provider."""
        cls._providers[provider_name] = provider_class

    @classmethod
    def get_provider(cls, provider_name: str) -> PaymentProvider:
        """Get provider instance by name."""
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown payment provider: {provider_name}")
        return cls._providers[provider_name]()

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered providers."""
        return list(cls._providers.keys())


# Register providers
PaymentProviderRegistry.register("manual", ManualPaymentProvider)
# Future registrations:
# PaymentProviderRegistry.register("bit", BitPaymentProvider)
# PaymentProviderRegistry.register("paybox", PayBoxPaymentProvider)
# PaymentProviderRegistry.register("payplus", PayPlusPaymentProvider)
# PaymentProviderRegistry.register("stripe", StripePaymentProvider)
```

---

## Payment Service (Orchestration Layer)

```python
class PaymentService:
    """
    Orchestrates payment operations across providers.

    This service:
    - Selects the appropriate provider for a workspace
    - Delegates operations to the provider
    - Handles cross-cutting concerns (logging, audit trail)
    - Maintains provider-agnostic business logic
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_workspace_provider(self, workspace: Workspace) -> PaymentProvider:
        """
        Get the payment provider for a workspace.

        Logic:
        1. If workspace.payment_provider is set, use that provider
        2. If only bank_account_details is set, use ManualProvider
        3. If neither is set, raise error (payments not enabled)
        """
        if workspace.payment_provider:
            # Explicit provider selected
            return PaymentProviderRegistry.get_provider(workspace.payment_provider)
        elif workspace.bank_account_details:
            # Only manual tracking configured
            return PaymentProviderRegistry.get_provider("manual")
        else:
            raise ValueError("Payments not enabled for this workspace")

    async def create_payment_request(
        self,
        appointment: Appointment,
        workspace: Workspace
    ) -> str | None:
        """
        Create a payment request for an appointment.

        Returns:
            Payment link URL (if automated provider)
            None (if manual provider)
        """
        provider = await self.get_workspace_provider(workspace)

        # Delegate to provider
        payment_link = await provider.create_payment_request(
            appointment,
            workspace.payment_provider_config or {}
        )

        # Update appointment status
        if provider.supports_automated_requests() and payment_link:
            appointment.payment_status = PaymentStatus.PAYMENT_SENT

        await self.db.commit()

        # Audit log
        await self._log_payment_event(appointment, "payment_request_created", payment_link)

        return payment_link

    async def mark_as_paid(
        self,
        appointment: Appointment,
        payment_method: str,
        notes: str | None = None
    ):
        """
        Mark appointment as paid (manual or automated confirmation).

        This works the same way for ALL providers.
        """
        appointment.payment_status = PaymentStatus.PAID
        appointment.paid_at = datetime.now(UTC)
        appointment.payment_method = payment_method
        if notes:
            appointment.payment_notes = notes

        await self.db.commit()

        # Audit log
        await self._log_payment_event(appointment, "payment_received", None)
```

---

## Frontend Architecture

### Payment Settings UI (Multi-Mode)

```typescript
// frontend/src/composables/usePaymentSettings.ts

export function usePaymentSettings() {
  const workspace = useWorkspace()

  const paymentMode = computed(() => {
    if (workspace.value.payment_provider) {
      return 'automated'  // Provider configured
    } else if (workspace.value.bank_account_details) {
      return 'manual'  // Only manual tracking
    } else {
      return 'disabled'  // No payments configured
    }
  })

  const availableProviders = ref([
    { value: 'manual', label: 'Manual Tracking (Bank Transfer)' },
    // Future:
    // { value: 'bit', label: 'Bit (Israeli Mobile Payment)' },
    // { value: 'paybox', label: 'PayBox (Israeli Payment Service)' },
    // { value: 'payplus', label: 'PayPlus (Online Payment Platform)' },
  ])

  return {
    paymentMode,
    availableProviders,
    isManualMode: computed(() => paymentMode.value === 'manual'),
    isAutomatedMode: computed(() => paymentMode.value === 'automated'),
    isDisabled: computed(() => paymentMode.value === 'disabled'),
  }
}
```

### Settings UI Flow

```vue
<!-- frontend/src/components/settings/PaymentSettings.vue -->

<template>
  <div class="payment-settings">
    <!-- STEP 1: Enable/Disable -->
    <div v-if="isDisabled">
      <h2>Enable Payment Tracking</h2>
      <p>Track payments from your clients</p>
      <button @click="showEnableModal = true">Enable Payments</button>
    </div>

    <!-- STEP 2: Choose Mode (when enabling) -->
    <Modal v-model="showEnableModal">
      <h2>Choose Payment Mode</h2>

      <div class="mode-option" @click="enableManualMode">
        <h3>📝 Manual Tracking</h3>
        <p>Share your bank account details with clients</p>
        <ul>
          <li>Clients pay via bank transfer, Bit, or PayBox</li>
          <li>You manually mark appointments as paid</li>
          <li>Simple, no integration needed</li>
        </ul>
        <button>Enable Manual Tracking</button>
      </div>

      <div class="mode-option disabled">
        <h3>🤖 Automated Provider (Coming Soon)</h3>
        <p>Automatic payment links and confirmations</p>
        <ul>
          <li>Generate payment links automatically</li>
          <li>Receive instant payment confirmations</li>
          <li>Requires provider integration (Bit, PayBox, etc.)</li>
        </ul>
        <button disabled>Coming Soon</button>
      </div>
    </Modal>

    <!-- STEP 3: Manual Mode Configuration -->
    <div v-if="isManualMode">
      <h2>Manual Payment Tracking</h2>
      <textarea
        v-model="bankAccountDetails"
        placeholder="Bank name, account number, branch..."
      />
      <button @click="copyBankDetails">Copy to Clipboard</button>
      <button @click="saveBankDetails">Save</button>
      <button @click="disablePayments">Disable Payments</button>
    </div>

    <!-- STEP 4: Automated Mode Configuration (Future) -->
    <div v-if="isAutomatedMode">
      <h2>Automated Payment Provider</h2>
      <select v-model="selectedProvider">
        <option value="bit">Bit</option>
        <option value="paybox">PayBox</option>
      </select>

      <!-- Provider-specific config fields -->
      <component :is="providerConfigComponent" />

      <button @click="testConnection">Test Connection</button>
      <button @click="saveProviderConfig">Save</button>
      <button @click="disablePayments">Disable Payments</button>
    </div>
  </div>
</template>
```

---

## Migration Strategy

### Phase 1: Manual Tracking (Current - Week 1)

**Goal:** Enable therapists to track bank transfer payments manually

**Changes:**
- ✅ Keep payment_provider fields (don't delete!)
- ✅ Add bank_account_details field
- ✅ Implement ManualPaymentProvider
- ✅ Update UI to support manual mode
- ✅ Delete PayPlus-specific code (but keep provider abstraction)

**User Flow:**
1. Therapist enables payments → Chooses "Manual Tracking"
2. Enters bank account details
3. For each appointment: Sets price, shares bank details with client
4. Client pays via bank transfer/Bit/PayBox app
5. Therapist manually marks appointment as paid

### Phase 2: Bit Integration (Future - Week 4-6)

**Goal:** Add automated Bit payment provider

**Changes:**
- Implement BitPaymentProvider
- Register with PaymentProviderRegistry
- Add Bit config UI in Settings
- Add webhook endpoint for Bit callbacks

**User Flow:**
1. Therapist enables payments → Chooses "Bit (Automated)"
2. Enters Bit API credentials
3. For each appointment: System auto-generates Bit payment link
4. Client receives link via SMS/WhatsApp, pays
5. System auto-marks appointment as paid (webhook)

### Phase 3: PayBox Integration (Future - Week 7-9)

**Goal:** Add automated PayBox payment provider

**Changes:**
- Implement PayBoxPaymentProvider
- Register with PaymentProviderRegistry
- Add PayBox config UI in Settings
- Add webhook endpoint for PayBox callbacks

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/services/test_payment_service.py

async def test_manual_provider_selected_when_only_bank_details():
    workspace = Workspace(bank_account_details="Account 123")
    service = PaymentService(db)

    provider = await service.get_workspace_provider(workspace)

    assert isinstance(provider, ManualPaymentProvider)

async def test_bit_provider_selected_when_configured():
    workspace = Workspace(
        bank_account_details="Account 123",
        payment_provider="bit",
        payment_provider_config={"api_key": "xxx"}
    )
    service = PaymentService(db)

    provider = await service.get_workspace_provider(workspace)

    assert isinstance(provider, BitPaymentProvider)

async def test_manual_provider_create_payment_request_returns_none():
    provider = ManualPaymentProvider()
    appointment = Appointment(payment_price=Decimal("100.00"))

    link = await provider.create_payment_request(appointment, {})

    assert link is None  # Manual provider doesn't generate links
```

### Integration Tests

```python
# tests/integration/test_payment_workflows.py

async def test_manual_payment_workflow():
    """Test complete manual payment workflow."""
    # 1. Enable manual payments
    workspace = await create_workspace(bank_account_details="Account 123")

    # 2. Create appointment with price
    appointment = await create_appointment(
        workspace_id=workspace.id,
        payment_price=Decimal("150.00")
    )

    # 3. Therapist marks as paid
    await payment_service.mark_as_paid(
        appointment,
        payment_method="bank_transfer",
        notes="Client paid via Bit app"
    )

    # 4. Verify status
    assert appointment.payment_status == PaymentStatus.PAID
    assert appointment.payment_method == "bank_transfer"
    assert appointment.paid_at is not None
```

---

## Benefits of This Architecture

### 1. **Separation of Concerns**
- Manual tracking is independent of automated providers
- Can use manual OR automated OR both
- Clear boundaries between components

### 2. **Open/Closed Principle**
- Easy to add new providers without modifying existing code
- Just implement PaymentProvider interface and register

### 3. **Feature Flag Friendly**
- Payments can be disabled (NULL all fields)
- Can switch between manual and automated
- Backwards compatible with existing data

### 4. **Testability**
- Each provider can be tested independently
- Easy to mock providers in tests
- Clear interfaces make testing straightforward

### 5. **Maintainability**
- Clear, documented architecture
- Consistent patterns (Strategy, Factory, Service Layer)
- Easy for new developers to understand and extend

### 6. **Progressive Enhancement**
- Start simple (manual tracking)
- Add complexity gradually (providers one at a time)
- No big-bang rewrites needed

---

## Success Metrics

**Phase 1 (Manual Tracking):**
- [ ] 90% of therapists enable manual payment tracking
- [ ] Average time to enable payments: <2 minutes
- [ ] Zero data loss during migration
- [ ] No performance regression

**Phase 2+ (Automated Providers):**
- [ ] 40% of therapists upgrade to automated provider
- [ ] Payment confirmation time: <5 seconds (vs 24 hours manual)
- [ ] Client payment completion rate: >70%

---

**Document Version:** 2.0
**Status:** Ready for Implementation
**Next Steps:** Update implementation plan to match this architecture
