# PazPaz Hebrew i18n - Quick Reference Summary

## Key Numbers
- **Total Components:** 94 (83 components + 11 views)
- **Text Strings to Translate:** ~450-500
- **Toast Messages:** 122+
- **Files to Modify:** 94

## Highest Priority Areas (Should be translated first)
1. **LoginView.vue** - Auth entry point (25+ strings)
2. **AppointmentFormModal.vue** - Most-used modal (35+ strings)
3. **CalendarView.vue** - Main feature (20+ strings)
4. **ClientsView.vue** - Key feature (15+ strings)
5. **ClientFormModal.vue** - Core workflow (20+ strings)

## Critical Third-Party Library Integrations
1. **FullCalendar v6.1.19** - Has built-in Hebrew locale
2. **date-fns** - Has Hebrew locale module
3. **vue-toastification** - Mostly uses icons, text comes from app

## Text Categories by Volume
| Category | Count | Impact |
|----------|-------|--------|
| Toast messages | 122 | HIGH |
| Form labels | 80 | HIGH |
| Button labels | 60 | MEDIUM |
| Modal content | 45 | HIGH |
| Validation messages | 35 | MEDIUM |
| Other UI text | 113 | MEDIUM |

## Current State
- **NO existing i18n framework** - All text is hardcoded
- **NO translation files** exist
- **RTL support** already implemented (v-rtl directive)
- **Hebrew text awareness** exists (recent Bit payment label commit)

## Implementation Approach
```
Phase 1: Install vue-i18n + create i18n folder
Phase 2: Extract ~500 text strings into JSON files
Phase 3: Migrate components (start with views)
Phase 4: Configure FullCalendar + date-fns locales
Phase 5: Add language selector UI
```

## Text Organization
Text is scattered across:
- Template text (`<p>`, `<h1>`, etc.)
- Attributes (`placeholder`, `label`, `aria-label`)
- Computed properties
- Dynamic messages in JS
- Function constants

## RTL & Date Format Notes
- RTL directive already present: `v-rtl`
- Hebrew date format typically DD.MM.YYYY
- Time format: verify preference (12h vs 24h)
- Payment methods already showing Hebrew awareness

## Estimated Effort
**2-3 weeks** for complete Hebrew localization with testing

## Next Steps
1. Review full analysis in `HEBREW_I18N_ANALYSIS.md`
2. Install `vue-i18n` v10
3. Create i18n folder structure
4. Start extracting text (recommend automated tool)
5. Begin component migration from high-priority list

---

For detailed analysis, see: `/HEBREW_I18N_ANALYSIS.md`
