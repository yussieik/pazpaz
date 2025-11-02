# Changelog

All notable changes to PazPaz will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Phase 1.5: Smart Payment Links (2025-11-02)

#### Payment Link Generation
- **Bit SMS Links**: Auto-generate `sms:050-1234567` links with payment amount and message
- **PayBox URL Links**: Generate PayBox payment URLs with `?amount=150` parameter
- **Bank Transfer Details**: Display formatted bank account information
- **Custom Payment Links**: Support for any custom URL template

#### Payment Configuration UI
- **Payment Settings Page**: 4 payment method cards (Bit, PayBox, Bank Transfer, Custom)
- **Real-time Validation**: Phone number validation for Bit (Israeli mobile format)
- **URL Validation**: Validate PayBox and custom URLs
- **Save/Test Flow**: Test payment links before saving configuration

#### Email Payment Requests
- **Bilingual Templates**: Hebrew + English payment request emails
- **Smart Link Integration**: Payment links embedded in emails based on payment type
- **SMS Fallback**: Bit uses SMS protocol with Hebrew instructions
- **Copy to Clipboard**: One-click copy payment links from appointment details

#### Backend Services
- **PaymentLinkService**: Generate payment links for all supported types
- **Email Service**: Send bilingual payment request emails
- **Payment Config API**: GET/PUT `/api/v1/workspaces/payment-config` endpoints
- **Appointment Payment API**: POST/GET payment links for appointments

#### Database Schema
- **payment_link_type**: Column for 'bit', 'paybox', 'bank', 'custom', null
- **payment_link_template**: Store phone number, URL, or bank details
- **payment_mode**: Property that returns 'manual', 'smart_link', 'automated', or null
- **Priority System**: automated > smart_link > manual > disabled

#### Frontend Components
- **PaymentSettings.vue**: Complete rewrite with 4 payment method cards (710 lines)
- **AppointmentDetailsModal.vue**: Send payment request and copy link buttons
- **usePayments Composable**: Shared state for payment configuration
- **OpenAPI Types**: Regenerated schema.ts with Phase 1.5 fields

#### Testing
- **Integration Tests**: 41/41 payment tests passing (100% pass rate)
- **Manual QA Guide**: 10 test scenarios covering all payment types
- **Backwards Compatibility**: Phase 1 manual tracking still works
- **Edge Cases**: Tested all validation scenarios and error cases

### Changed

#### Payment System Evolution
- **From Manual to Smart Links**: Upgraded from Phase 1 (manual tracking only)
- **Preserved Manual Mode**: Phase 1 bank_account_details still functional
- **Priority-Based Detection**: System automatically detects best available payment mode

#### UI/UX Improvements
- **Simplified Payment Setup**: 4-card layout instead of form-heavy approach
- **Contextual Validation**: Validation messages specific to each payment type
- **Clear Instructions**: Hebrew+English instructions for each payment method

### Technical Details

#### Architecture
- **Phase Progression**: Phase 1 (manual) → Phase 1.5 (smart links) → Phase 2+ (automated)
- **Feature Flag Pattern**: payment_link_type NULL = disabled, value = enabled
- **Backwards Compatible**: No breaking changes to Phase 1 functionality
- **Pluggable Design**: Ready for Phase 2+ automated provider integration

#### Performance
- **All Tests Passing**: 41/41 integration tests (100%)
- **TypeScript Clean**: No type errors in frontend
- **Build Success**: Production build completed successfully
- **API Response**: All endpoints <150ms p95 (within performance targets)

#### Files Changed (Summary)
- **Backend**: 12 files modified/created (~2,000 lines)
- **Frontend**: 6 files modified (~1,500 lines)
- **Tests**: 3 test files (41 test cases, 100% passing)
- **Documentation**: 3 files updated

#### Migration Path
- **Zero Downtime**: Database migration adds nullable columns
- **No Data Loss**: Existing payment data preserved
- **Seamless Upgrade**: Users can enable smart links without affecting manual tracking

### Documentation

#### Updated Files
- `docs/PROJECT_OVERVIEW.md` - Payment tracking section updated
- `PAYMENT_PHASE1_IMPLEMENTATION_PLAN.md` - Marked as archived, superseded by Phase 1.5
- `docs/payment/PAYMENT_PHASE1.5_SMART_LINKS_PLAN.md` - Complete implementation tracking

#### User-Facing Guides
- Payment setup instructions for each payment type
- Email template examples (Hebrew + English)
- Manual QA testing checklist

### For Developers

#### New APIs
```
GET  /api/v1/workspaces/payment-config       - Get payment configuration
PUT  /api/v1/workspaces/payment-config       - Update payment configuration
POST /api/v1/appointments/{id}/send-payment-request  - Send payment email
GET  /api/v1/appointments/{id}/payment-link  - Get payment link for appointment
```

#### Database Migration
```bash
# Upgrade to Phase 1.5
env PYTHONPATH=src uv run alembic upgrade head

# Adds: payment_link_type, payment_link_template to workspaces table
```

#### Frontend Schema Regeneration
```bash
# Regenerate TypeScript types from OpenAPI spec
npm run generate-api
```

### Known Limitations

- **Phase 1.5 is Links Only**: No API integration with Bit/PayBox
- **Manual Payment Confirmation**: Therapist still marks appointments as paid manually
- **No Webhooks**: Payment confirmations not automated (Phase 2+ feature)
- **SMS Requires Client App**: Bit SMS links require client to have SMS app installed

### Next Steps (Phase 2+)

- [ ] Bit API Integration - Auto-generate payment links via Bit API
- [ ] PayBox API Integration - Auto-generate payment links via PayBox API
- [ ] Webhook Support - Automated payment confirmation from providers
- [ ] Transaction Tracking - Store payment provider transaction IDs
- [ ] Receipt Generation - Auto-generate VAT-compliant receipts

---

## [0.1.0] - Initial Release

### Added
- Basic appointment scheduling
- Client management
- SOAP session notes
- Calendar view
- Magic link authentication

[Unreleased]: https://github.com/username/pazpaz/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/username/pazpaz/releases/tag/v0.1.0
