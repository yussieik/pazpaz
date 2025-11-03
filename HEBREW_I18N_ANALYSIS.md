# PazPaz Frontend Hebrew i18n Analysis Report

## Executive Summary

**Scope:** Complete analysis of user-facing text in PazPaz frontend for Hebrew localization implementation.

**Key Metrics:**
- **Total Vue Components:** 83 (components) + 11 (views) = 94 total
- **Toast Messages:** 122+ toast messages across the application
- **Text Organization:** 100% inline hardcoded text (no existing i18n framework)
- **Third-party Libraries with Locale Needs:** FullCalendar v6.1.19 + date-fns
- **Text Categories:** Auth, Calendar, Clients, Sessions, Payments, Settings, Notifications, Modals, Validations, Empty States

---

## 1. CURRENT TEXT ORGANIZATION PATTERN

### Current State: NO Existing i18n Framework
- All text is hardcoded directly in Vue templates
- No translation files, keys, or i18n plugin installed
- Text is scattered across:
  - Template text
  - Form labels and placeholders
  - aria-label attributes
  - Error/success messages
  - Validation messages
  - Empty state copy
  - Modal titles and buttons

### Example: LoginView.vue
```vue
<h1 class="text-4xl font-bold text-emerald-600">PazPaz</h1>
<p class="mt-2 text-slate-600">Practice Management for Therapists</p>

<!-- 40+ hardcoded strings in single view -->
<label for="email" class="mb-2 block text-sm font-medium text-slate-700">
  Email Address
</label>
<input placeholder="you@example.com" />
```

---

## 2. COMPONENT COUNT AND CATEGORIES

### By Feature Area (94 total components)

#### Authentication (3 views)
- LoginView.vue - Sign in screen with 20+ text strings
- AuthVerifyView.vue - Email verification flow
- AcceptInvitationView.vue - Invitation acceptance

#### Calendar & Appointments (8 views + 15 components)
- CalendarView.vue - Main calendar with multiple modals
- AppointmentFormModal.vue - Create/edit with 30+ strings
- AppointmentDetailsModal.vue - View appointment details
- CancelAppointmentDialog.vue - Cancellation interface
- DeleteAppointmentModal.vue - Delete confirmation
- DragConflictModal.vue - Conflict warning on drag
- MobileRescheduleModal.vue - Mobile-specific UX
- CalendarToolbar.vue - View switching and navigation
- AppointmentStatusCard.vue - Status display
- AppointmentEditIndicator.vue - Edit state indicator
- ConflictAlert.vue - Conflict warnings
- PaymentTrackingCard.vue - Payment UI in appointments

#### Clients (3 views + 8 components)
- ClientsView.vue - Client list with 15+ strings (search, filters, empty state)
- ClientDetailView.vue - Client detail page
- ClientFormModal.vue - Create/edit client
- ClientCombobox.vue - Search/select client
- ClientQuickAddForm.vue - Quick add mini form
- ClientDropdownItem.vue - List item

#### Sessions (10+ components)
- SessionView.vue - Session/SOAP note editor
- SessionEditor.vue - Edit interface
- SessionVersionHistory.vue - Version control
- SessionAttachments.vue - File attachments
- FileUpload.vue - Upload interface
- PreviousSessionPanel.vue - Previous sessions reference
- DeletedNotesSection.vue - Deleted notes recovery

#### Settings (5 views + 4 components)
- PaymentsView.vue - Payment configuration
- NotificationsView.vue - Notification preferences
- PaymentSettings.vue - Payment method configuration (20+ strings)
- GoogleCalendarSettings.vue - Calendar sync settings
- SettingsSidebar.vue - Settings navigation

#### Admin (2 views + 5 components)
- PlatformAdminPage.vue - Admin dashboard
- CreateWorkspaceModal.vue - Workspace creation
- ConfirmationModal.vue - Generic confirmation
- WorkspaceDetailsModal.vue - Workspace details

#### Common Components (20+ reusable)
- BaseButton.vue - Button component
- EmptyState.vue - Empty state template
- LoadingSpinner.vue - Loading indicator
- AppointmentToastContent.vue - Rich toast notification
- KebabMenu.vue - Context menu
- RateLimitBanner.vue - Rate limit warning
- SessionExpirationBanner.vue - Session expiry warning
- AutosaveBanner.vue - Autosave indicator
- And 12+ more...

---

## 3. USER-FACING TEXT BY FEATURE AREA

### A. Authentication (Priority: HIGH)

**LoginView.vue** (~25 strings)
```
- "PazPaz"
- "Practice Management for Therapists"
- "Development Mode"
- "Check MailHog for magic link emails during testing"
- "Sign In"
- "Session Expired"
- "Your session has expired due to inactivity. Please sign in again to continue."
- "Check your email"
- "We've sent a magic link to [email]"
- "Edit"
- "Link expires in:"
- "Check your spam folder if you don't see it"
- "The link can only be used once"
- "Didn't receive it?"
- "Resending..."
- "Resend magic link"
- "Didn't receive the email?"
- "Check spam folder: Magic links sometimes end up in spam or junk folders"
- "Check email address: Make sure [email] is correct"
- "Wait a few minutes: Email delivery can take up to 5 minutes"
- "Check email provider: Some email providers block automated emails..."
- "Firewall/filters: Corporate email systems may block external emails"
- "Still having trouble? Contact support@pazpaz.com"
- "Email Address"
- "We'll send you a magic link to sign in"
- "Send Magic Link"
- "Sending..."
- "Link Sent!"
- "Send New Link"
- "Secure passwordless authentication"
```

**AuthVerifyView.vue** (~10 strings)
- Verification messages
- Success/error states
- Link validation copy

**AcceptInvitationView.vue** (~8 strings)
- Invitation acceptance flow
- Workspace setup messages

### B. Calendar & Appointments (Priority: CRITICAL)

**CalendarView.vue** (~20 strings)
```
- "New Appointment"
- "Appointment created"
- "Appointment rescheduled"
- "Appointment cancelled"
- "Appointment deleted"
- "Changes saved"
- "Failed to create appointment"
- "Failed to reschedule appointment"
- "Failed to cancel appointment"
- "Failed to delete appointment"
- And toolbar labels (Week, Day, Month, Today, etc.)
```

**AppointmentFormModal.vue** (~35 strings)
```
- "New Appointment" / "Edit Appointment"
- "Checking availability..."
- "Time slot overlap detected"
- "1 existing appointment" / "[n] existing appointments"
- "conflict with this time slot"
- "Time slot available"
- "This appointment is in the past. You can still create it if you're logging a past session."
- Form labels:
  - "Client" (required)
  - "Date" (required)
  - "Start Time" (required)
  - "End Time" (required)
  - "Duration: [X] min"
  - "Quick Duration:"
  - "[30/45/60/90] min" (duration pills)
  - "Location Type" (required)
  - "Clinic" / "Home Visit" / "Online (Video/Phone)"
  - "Location Details"
  - "e.g., Zoom link, room number, address"
  - "Using address from client profile"
  - "Notes"
  - "Optional notes about this appointment"
- Buttons:
  - "Cancel"
  - "Create" / "Save Changes"
  - "⚠️ [Action] Anyway" (when conflicts)
  - "⌘Enter" / "CtrlEnter" keyboard shortcut hint
```

**AppointmentDetailsModal.vue** (~15 strings)
- Display appointment details
- Status badges
- Payment status
- Client information

**CancelAppointmentDialog.vue** (~10 strings)
```
- Dialog title
- "Reason for cancellation (optional)"
- "e.g., Client requested cancellation, therapist illness..."
- "Cancel Appointment" button
- "Keep Appointment" button
```

**PaymentTrackingCard.vue** (~20 strings)
```
- "Payment Method"
  - "Cash"
  - "Card"
  - "Bank Transfer"
  - "Bit" (with Hebrew label in recent commit)
  - "PayBox"
  - "Other"
- "Payment Status"
  - "Not Paid"
  - "Payment Sent"
  - "Paid"
  - "Waived"
- "Amount" field
- "Notes" field
- Action buttons
```

### C. Clients (Priority: HIGH)

**ClientsView.vue** (~15 strings)
```
- "Search clients by name, email, or phone... (press / to focus)"
- "Tap to search clients..." (mobile)
- "[n] client / [n] clients"
- "Loading clients..."
- "Error loading clients"
- "No clients yet"
- "Get started by adding your first client to begin managing their treatment journey."
- "Add First Client"
- "No clients match your search."
- "Clear search"
- "Add Client"
- "Add Client (N)" (shortcut hint)
- Client card:
  - "Phone:"
  - "Next:"
  - "Last:"
  - "Appointments:"
```

**ClientFormModal.vue** (~20 strings)
```
- "New Client" / "Edit Client"
- Form fields:
  - "First Name *"
  - "Last Name *"
  - "Email Address"
  - "Phone Number"
  - "Phone (for reminders, optional)"
  - "Address"
  - "Medical History"
  - "Relevant medical history, conditions, medications, allergies..."
  - "Notes"
  - "Initial assessment, treatment goals, preferences..."
- Buttons:
  - "Cancel"
  - "Create" / "Save Changes"
```

**ClientCombobox.vue** (~10 strings)
- Search placeholder
- "No clients found" message
- "Create new client" action
- "Clear client selection"

### D. Sessions/SOAP Notes (Priority: HIGH)

**SessionEditor.vue** (~25 strings)
```
- "SOAP Note"
- Form sections:
  - "Subjective"
  - "Objective"
  - "Assessment"
  - "Plan"
- "Add attachment"
- "Delete note"
- "Delete this session note?"
- "Save changes"
- "Cancel"
- "Session last modified:"
- "Version history"
- "Autosave enabled"
- "Undo recent changes"
- And validation messages
```

**SessionAttachments.vue** (~15 strings)
- "Attachments"
- "Add file"
- "Remove file"
- "File uploaded successfully"
- "Failed to upload file"
- "Maximum file size exceeded"
- "Unsupported file type"

**PreviousSessionPanel.vue** (~10 strings)
- "Previous sessions"
- "Last session: [date]"
- "View more"
- "No previous sessions"

### E. Settings (Priority: MEDIUM)

**PaymentSettings.vue** (~40 strings)
```
Payment provider configuration:
- "Enable Payment Tracking"
- "Payment Provider Selection"
- "Manual Payment Tracking"
- "Bit" (with Hebrew label)
- "PayBox"
- "Custom Payment Link"
- "Bank Transfer Details"

Per provider:
- Input labels:
  - "Bit Phone Number"
  - "050-123-4567 or https://www.bitpay.co.il/app/me/..."
  - "PayBox URL"
  - "https://paybox.co.il/p/yourname"
  - "Custom Payment Link"
  - "https://example.com/pay?amount={amount}"
  - "Bank Details"
  - "Bank: Leumi, Account: 12345..."

- Action buttons:
  - "Copy link"
  - "Share with client"
  - "Clear"
  - "Save"
  - "Cancel"
  - "Edit"
  - "Remove"

- Status messages:
  - "Saved successfully"
  - "Failed to save"
  - "Copied to clipboard"
```

**GoogleCalendarSettings.vue** (~15 strings)
- "Google Calendar Integration"
- "Enable automatic sync"
- "Sync direction"
- "Authorize"
- "Disconnect"
- "Last synced: [time]"
- "Sync error: [error]"

**NotificationsView.vue** (~20 strings)
- "Notification Settings"
- "Email notifications"
- "Appointment reminders"
- "Enable reminders"
- "[1 hour before / custom]"
- "Save preferences"
- "Preferences updated"

### F. Modals & Dialogs (Priority: HIGH)

**DeleteAppointmentModal.vue** (~8 strings)
```
- "Delete Appointment?"
- "Are you sure you want to delete this appointment? This action cannot be undone."
- "Delete" (button)
- "Cancel" (button)
```

**DragConflictModal.vue** (~10 strings)
```
- "Scheduling Conflict"
- "This time conflicts with existing appointment(s)"
- "Time: [time range]"
- "Client: [name]"
- "Reschedule anyway" (button)
- "Keep original time" (button)
```

**LogoutConfirmationModal.vue** (~8 strings)
```
- "Sign Out?"
- "You will be signed out of PazPaz"
- "Sign Out" (button)
- "Cancel" (button)
```

**SessionExpirationModal.vue** (~10 strings)
```
- "Session Expiring"
- "Your session will expire in [time]"
- "Stay signed in" (button)
- "Sign out" (button)
```

### G. Validation Messages (Priority: MEDIUM)

**AppointmentFormModal.vue validation**
```
- "Client is required"
- "Start time is required"
- "End time is required"
- "End time must be after start time"
```

**ClientFormModal.vue validation**
```
- "First name is required"
- "Last name is required"
- "Invalid email address"
- "Invalid phone number"
```

**Form field errors** (25+ variations across forms)

### H. Empty States (Priority: MEDIUM)

**ClientsView.vue**
```
- "No clients yet"
- "Get started by adding your first client to begin managing their treatment journey."
- "No clients match your search."
- "Clear search"
```

**SessionView.vue**
```
- "No sessions yet"
- "Create your first session note"
- "No attachments"
- "Add an attachment to get started"
```

**Other empty states** (10+ variations)

### I. Toast Notifications (Priority: HIGH)

**122+ toast messages** across application:
```
Success messages:
- "Client added successfully"
- "Client updated"
- "Appointment created"
- "Appointment rescheduled"
- "Appointment cancelled"
- "Session saved"
- "Settings saved"
- "Changes saved"
- "Copied to clipboard"

Error messages:
- "Failed to [action]"
- "An error occurred. Please try again."
- "Network error"
- "Please try again"
- "Permission denied"

Info messages:
- "Loading..."
- "Saving..."
- "Syncing..."
- "Unsaved changes"

Rate limit errors:
- "Too many requests"
- "Please try again in [X] seconds"

Undo messages:
- "[Action] completed. Undo?"
```

### J. Buttons & UI Labels (Priority: HIGH)

**Common button labels**
```
- "Save"
- "Cancel"
- "Delete"
- "Edit"
- "Add"
- "Create"
- "Update"
- "Close"
- "Send"
- "Undo"
- "Confirm"
- "Yes"
- "No"
- "OK"
- "Skip"
- "More"
- "Less"
```

**Navigation & menu items** (in SettingsSidebar.vue, etc.)
```
- "Calendar"
- "Clients"
- "Sessions"
- "Appointments"
- "Settings"
- "Profile"
- "Preferences"
- "Account"
- "Billing"
- "Help"
- "Sign Out"
```

### K. Accessibility Text (aria-labels, screen reader text)

**122+ aria-label attributes**
```
- "Close dialog"
- "Delete appointment"
- "Edit client"
- "Search clients"
- "Submit form"
- "View more options"
- "Keyboard shortcut help"
- "Open menu"
- "Sort by"
- "Filter results"
```

---

## 4. THIRD-PARTY COMPONENTS REQUIRING LOCALE CONFIGURATION

### A. FullCalendar v6.1.19

**Current Setup:** `/frontend/src/utils/calendar/calendarConfig.ts`

```typescript
// Currently hardcoded to English
const TIME_FORMAT_CONFIG = {
  eventTimeFormat: {
    hour: '2-digit',
    minute: '2-digit',
    meridiem: 'short',
  },
  slotLabelFormat: {
    hour: '2-digit',
    minute: '2-digit',
    meridiem: 'short',
  },
}
```

**Elements Requiring Translation:**
- Month/day names
- Button labels (prev, next, today)
- View names (week, day, month)
- Time formats
- Event titles

**Locale Support:** FullCalendar includes built-in Hebrew locale (`he`)

**Implementation:** 
```typescript
import heLocale from '@fullcalendar/core/locales/he'

const calendarOptions = {
  locale: heLocale,
  // ... other options
}
```

**Files to Modify:**
- `/frontend/src/utils/calendar/calendarConfig.ts` - Add locale configuration
- `/frontend/src/views/CalendarView.vue` - Pass locale to FullCalendar component

### B. date-fns Library

**Current Usage:** `/frontend/src/utils/calendar/dateFormatters.ts`

Functions needing locale support:
- `formatDate()` - Uses format() with pattern
- `formatDateRange()` - Formats dates for toolbar
- `formatLongDate()` - Long-form date display
- `formatRelativeDate()` - Relative time (e.g., "5 days ago")
- `formatRelativeTime()` - Relative time for deletions

**Hardcoded English Strings:**
```typescript
// Line 170
if (diffDays === 0) return 'today'
if (diffDays === 1) return 'yesterday'
if (diffDays < 7) return `${diffDays} days ago`
if (diffDays < 30) {
  const weeks = Math.floor(diffDays / 7)
  return weeks === 1 ? '1 week ago' : `${weeks} weeks ago`
}
// ... more hardcoded strings
```

**Locale Support:** date-fns includes Hebrew locale (`he`)

**Implementation:**
```typescript
import { format } from 'date-fns'
import { he } from 'date-fns/locale'

export function formatDate(dateString: string, formatStr: string, locale = he): string {
  return format(new Date(dateString), formatStr, { locale })
}
```

**Files to Modify:**
- `/frontend/src/utils/calendar/dateFormatters.ts` - Replace hardcoded strings with Hebrew translations and add locale parameter to date-fns calls

### C. vue-toastification (Toast Library)

**Current Status:** Uses built-in icons and timing, minimal text configuration needed

**Required Updates:**
- Toast message strings themselves (handled by application code, not library)
- Library has minimal built-in text, mostly uses icons

---

## 5. TEXT EXTRACTION SUMMARY

### Total Text Strings to Translate: ~450-500 unique strings

**Breakdown by Category:**

| Category | Count | Priority | Complexity |
|----------|-------|----------|------------|
| Form labels & placeholders | ~80 | HIGH | Medium |
| Toast messages | ~122 | HIGH | High |
| Button labels | ~60 | HIGH | Low |
| Modal titles & content | ~45 | HIGH | Medium |
| Validation messages | ~35 | MEDIUM | Low |
| Navigation & menus | ~25 | MEDIUM | Low |
| Empty states | ~20 | MEDIUM | Low |
| Error messages | ~30 | HIGH | Medium |
| Accessibility (aria-labels) | ~40 | HIGH | Low |
| Calendar/date labels | ~20 | CRITICAL | High |
| Settings copy | ~50 | MEDIUM | High |
| Help text & hints | ~35 | MEDIUM | Low |
| Other UI text | ~75 | MEDIUM | Medium |

---

## 6. EXISTING PATTERNS & STRUCTURE

### No Existing i18n Framework
- **No translations directory** (no `locales/`, `i18n/`, `translations/`)
- **No i18n plugin** (no `vue-i18n` package)
- **No language selector** in UI
- **No localStorage for language preference**

### Text is Scattered Across:

1. **Direct Template Text**
   ```vue
   <h1>Login</h1>
   <p>Enter your email</p>
   ```

2. **Attributes**
   ```vue
   <input placeholder="you@example.com" />
   <label>Email Address</label>
   <button aria-label="Close dialog">X</button>
   ```

3. **Computed Properties**
   ```typescript
   const modalTitle = computed(() =>
     props.mode === 'create' ? 'New Appointment' : 'Edit Appointment'
   )
   ```

4. **Dynamic Messages in Code**
   ```typescript
   showSuccess(`${newClient.first_name} ${newClient.last_name} added successfully`)
   ```

5. **Constants in Functions**
   ```typescript
   const labels: Record<string, string> = {
     clinic: 'Clinic',
     home: 'Home Visit',
     online: 'Online',
   }
   ```

---

## 7. FEATURE-SPECIFIC NOTES

### Authentication Flow
- Email-based passwordless login
- Multiple error states for email validation
- Help accordion with email troubleshooting (5 different tips)
- Rate limiting message with countdown

### Calendar System
- Conflict detection with real-time feedback
- Duration presets (30, 45, 60, 90 minutes)
- Auto-fill for home visit address from client profile
- Keyboard shortcut hints (⌘Enter on Mac, Ctrl+Enter on Windows)
- Undo functionality for reschedules

### Client Management
- Search by name, email, or phone
- Client card displaying next appointment or last appointment
- Appointment count display
- Quick add functionality

### Payment System (Recently Added)
- Multiple payment method options (Bit, PayBox, Bank Transfer, Cash, Card, Other)
- Payment status tracking (Not Paid, Payment Sent, Paid, Waived)
- Links/details for each payment method
- Copy-to-clipboard functionality for sharing links

### Session/SOAP Notes
- Structured form (Subjective, Objective, Assessment, Plan)
- File attachments with preview
- Version history with amendments
- Autosave indicator
- Previous session reference

### Settings
- Profile settings
- Notification preferences
- Calendar sync (Google Calendar)
- Payment configuration
- Workspace settings (admin)

---

## 8. MOBILE-SPECIFIC TEXT

Several components have mobile-specific variants:
- **MobileRescheduleModal.vue** - Time picker modal for mobile
- **ClientsView.vue** - Different search placeholder for mobile
- **Responsive form labels** - Shorter on mobile

Mobile-specific strings:
```
- "Tap to search clients..." (vs desktop "Search clients by name...")
- Mobile keyboard deferral hints
- Touch-friendly button labels (larger min-height attributes)
```

---

## 9. RECOMMENDATIONS FOR i18n IMPLEMENTATION

### Phase 1: Setup (Foundation)
1. Install `vue-i18n` v10 (latest with TypeScript support)
2. Create `/frontend/src/i18n/` directory structure
3. Create locale files:
   - `en.json` - English (source)
   - `he.json` - Hebrew (target)
4. Create composable: `useI18n()` wrapper
5. Register i18n plugin in `main.ts`

### Phase 2: Text Extraction
1. Extract all ~450-500 text strings into keys
2. Organize by feature module for maintainability:
   - `auth` - Authentication
   - `calendar` - Calendar & appointments
   - `clients` - Client management
   - `sessions` - SOAP notes
   - `payments` - Payment tracking
   - `settings` - Settings pages
   - `common` - Shared text
   - `validation` - Validation messages
   - `toast` - Toast notifications

### Phase 3: Component Migration
1. Replace hardcoded text with `i18n.t('key')` calls
2. Migrate in order:
   - Views (11 files) - quickest ROI
   - Common components (20 files) - impacts all features
   - Feature-specific components (63 files) - bulk of work

### Phase 4: Third-party Locale Config
1. Update FullCalendar config to support locale switching
2. Update date-fns usage to support locale switching
3. Create locale wrapper for consistent date formatting

### Phase 5: UI for Language Switching
1. Add language selector in Settings or Navigation
2. Store language preference in localStorage
3. Persist language across sessions

---

## 10. COMPONENT BREAKDOWN TABLE

### Views (11 total)
```
Authentication:
- LoginView.vue (25+ strings)
- AuthVerifyView.vue (10+ strings)
- AcceptInvitationView.vue (8+ strings)

Calendar:
- CalendarView.vue (20+ strings)

Clients:
- ClientsView.vue (15+ strings)
- ClientDetailView.vue (10+ strings)

Sessions:
- SessionView.vue (15+ strings)

Settings:
- PaymentsView.vue (5 strings - delegates to PaymentSettings)
- NotificationsView.vue (20+ strings)

Admin:
- PlatformAdminPage.vue (15+ strings)
```

### Components (83 total, organized by folder)

**Calendar Components (15):**
AppointmentDetailsModal, AppointmentEditIndicator, AppointmentFormModal, AppointmentStatusCard, CalendarLoadingState, CalendarToolbar, CancelAppointmentDialog, ConflictAlert, DragConflictModal, KeyboardShortcutsHelp, MobileActionToolbar, MobileRescheduleModal, and more

**Client Components (8):**
ClientCombobox, ClientDropdownItem, ClientFormModal, ClientQuickAddForm, ClientFilesTab, and more

**Session Components (10+):**
SessionEditor, SessionVersionHistory, SessionCard, SessionAttachments, FileUpload, SessionNoteBadges, PreviousSessionPanel, PreviousSessionHistory, AttachmentList, and more

**Payment Components (4):**
PaymentActions, PaymentDetailsForm, PaymentSection, PaymentTrackingCard

**Settings Components (4):**
GoogleCalendarSettings, PaymentSettings, SettingsCard, SettingsSidebar

**Common/Shared Components (20+):**
AppointmentToastContent, AutosaveBanner, BaseButton, DirectionsButton, EmptyState, FloatingActionButton, KebabMenu, LoadingSpinner, PageHeader, RateLimitBanner, SessionExpirationBanner, SessionExpirationModal, SessionTimeoutModal, SkeletonLoader, TimePickerDropdown, ToggleSwitch, and more

---

## 11. KEY IMPLEMENTATION CONSIDERATIONS

### Dynamic Text Patterns
```typescript
// These patterns need special handling:
1. String interpolation:
   `${client.first_name} ${client.last_name} added successfully`
   Solution: Use i18n parameters: i18n.t('client.added', { firstName, lastName })

2. Pluralization:
   `${count} client` / `${count} clients`
   Solution: Use i18n pluralization: i18n.tc('clients.count', count)

3. Conditional text:
   mode === 'create' ? 'New Appointment' : 'Edit Appointment'
   Solution: Keep in computed, use i18n: i18n.t(mode === 'create' ? 'appointment.new' : 'appointment.edit')

4. Component composition:
   h('div', {}, [message, actionButton])
   Solution: Wrap in i18n context or pass translated strings as props
```

### Hebrew-Specific Considerations
1. **RTL Text Direction** - Already implemented via `v-rtl` directive (seen in LoginView.vue)
2. **Date Format** - Hebrew typically uses DD.MM.YYYY, but app appears to use MM/DD or context-dependent
3. **Time Format** - Check if 24-hour format preferred
4. **Payment Methods** - "Bit" already has Hebrew label in recent commit (shows i18n awareness)
5. **Pluralization** - Hebrew has complex pluralization rules for some words

### Performance Considerations
1. Lazy load locale files (split `en.json` and `he.json` per feature module)
2. Use i18n's built-in caching
3. Minimal impact on bundle size (~40KB gzipped for vue-i18n)

---

## 12. FILES TO MODIFY (Priority Order)

### Critical Path (Phase 1-2)
1. `main.ts` - Register i18n plugin
2. Create `/frontend/src/i18n/` directory structure
3. Create translation files (en.json, he.json)

### High Priority Views (Phase 3a)
1. LoginView.vue - Auth entry point
2. CalendarView.vue - Main feature
3. ClientsView.vue - Key feature

### High Priority Components (Phase 3b)
1. AppointmentFormModal.vue
2. ClientFormModal.vue
3. PaymentSettings.vue

### Utility Files (Phase 4)
1. `/frontend/src/utils/calendar/calendarConfig.ts` - FullCalendar locale
2. `/frontend/src/utils/calendar/dateFormatters.ts` - date-fns locale
3. `/frontend/src/composables/useToast.ts` - Toast messages (if needed)

### Remaining Components (Phase 3c)
- All other 60+ components and views

---

## CONCLUSION

PazPaz frontend has a **significant i18n effort ahead** requiring:
- ~500 text strings to extract
- 94 files to modify
- Careful handling of dynamic content and pluralization
- Third-party library locale configuration
- Testing across RTL rendering and date/time formats

**Estimated Effort:** 2-3 weeks for complete Hebrew localization with proper testing.

**No blocking technical issues identified** - standard i18n implementation pattern.
