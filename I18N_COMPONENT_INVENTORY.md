# PazPaz Frontend - Complete Component Inventory for i18n

## Views (11 files total)

### Authentication (3 files)
1. `/frontend/src/views/LoginView.vue` - Sign in page (25+ strings)
2. `/frontend/src/views/AuthVerifyView.vue` - Email verification (10+ strings)
3. `/frontend/src/views/AcceptInvitationView.vue` - Invitation flow (8+ strings)

### Main Features (4 files)
4. `/frontend/src/views/CalendarView.vue` - Calendar main view (20+ strings)
5. `/frontend/src/views/ClientsView.vue` - Clients list view (15+ strings)
6. `/frontend/src/views/ClientDetailView.vue` - Client detail (10+ strings)
7. `/frontend/src/views/SessionView.vue` - Session/SOAP editor (15+ strings)

### Settings (3 files)
8. `/frontend/src/views/settings/PaymentsView.vue` - Payments settings (5 strings, delegates to component)
9. `/frontend/src/views/settings/NotificationsView.vue` - Notification settings (20+ strings)

### Admin (1 file)
10. `/frontend/src/views/PlatformAdminPage.vue` - Admin dashboard (15+ strings)

---

## Calendar Components (15 files)

Located in `/frontend/src/components/calendar/`

### Modals & Dialogs
1. **AppointmentFormModal.vue** - Create/edit appointment (35+ strings) ⭐ HIGH PRIORITY
   - Modal title (Create vs Edit)
   - Conflict detection messages
   - Form labels (Client, Date, Start Time, End Time, Location, Notes)
   - Duration presets
   - Address auto-fill hint
   - Validation messages
   - Button labels (Create, Save Changes, Cancel)

2. **AppointmentDetailsModal.vue** - View appointment (15+ strings)
   - Details display
   - Status badges
   - Payment information

3. **CancelAppointmentDialog.vue** - Cancel appointment (10+ strings)
   - Dialog title
   - Cancellation reason field
   - Buttons (Cancel Appointment, Keep Appointment)

4. **DeleteAppointmentModal.vue** - Delete confirmation (8+ strings)
   - Confirmation message
   - Buttons (Delete, Cancel)

5. **DragConflictModal.vue** - Conflict on drag (10+ strings)
   - Conflict warning
   - Time range display
   - Client name display
   - Buttons (Reschedule anyway, Keep original time)

6. **MobileRescheduleModal.vue** - Mobile time picker (10+ strings)
   - Time picker interface
   - Confirmation buttons

### Toolbar & Navigation
7. **CalendarToolbar.vue** - View switching (20+ strings)
   - Week / Day / Month buttons
   - Previous / Next / Today buttons
   - Date range display
   - View change labels

### Status & Indicators
8. **AppointmentStatusCard.vue** - Status display (10+ strings)
   - Status badges
   - Information display

9. **AppointmentEditIndicator.vue** - Edit state (5+ strings)
   - Edit indicator message

10. **ConflictAlert.vue** - Conflict warning (8+ strings)
    - Conflict message
    - Details

### Loading States
11. **CalendarLoadingState.vue** - Loading indicator (5+ strings)
    - Loading message

### Help & Info
12. **KeyboardShortcutsHelp.vue** - Keyboard help (15+ strings)
    - Shortcut descriptions

### Mobile & Action
13. **MobileActionToolbar.vue** - Mobile actions (8+ strings)
    - Action buttons for mobile

14-15. Additional calendar components

---

## Client Components (8 files)

Located in `/frontend/src/components/clients/` and `/frontend/src/components/client/`

1. **ClientFormModal.vue** - Create/edit client (20+ strings) ⭐ HIGH PRIORITY
   - Modal title (New vs Edit)
   - Form fields (First Name, Last Name, Email, Phone, Address, Medical History, Notes)
   - Placeholders for each field
   - Button labels (Create, Save Changes, Cancel)
   - Validation messages

2. **ClientCombobox.vue** - Client search/select (10+ strings)
   - Search placeholder
   - "No clients found" message
   - "Create new client" action

3. **ClientQuickAddForm.vue** - Quick add mini form (8+ strings)
   - Compact form
   - Quick add button

4. **ClientDropdownItem.vue** - Client list item (5+ strings)
   - Client name
   - Client info display

5. **ClientFilesTab.vue** - Client files/attachments (8+ strings)
   - File list
   - Upload interface

6-8. Additional client components

---

## Session Components (10+ files)

Located in `/frontend/src/components/sessions/`

1. **SessionEditor.vue** - SOAP note editor (25+ strings)
   - SOAP section titles (Subjective, Objective, Assessment, Plan)
   - Save/Cancel buttons
   - Version history link
   - Autosave indicator
   - Delete button

2. **SessionVersionHistory.vue** - Version control (10+ strings)
   - Version list
   - Diff display
   - Revert button

3. **SessionAttachments.vue** - Attachments section (15+ strings)
   - Attachment list
   - Add/remove buttons
   - Upload messages

4. **FileUpload.vue** - File upload interface (12+ strings)
   - Upload prompt
   - File type errors
   - Size errors
   - Success messages

5. **SessionCard.vue** - Session summary card (8+ strings)
   - Session info
   - Date display

6. **PreviousSessionPanel.vue** - Previous sessions reference (10+ strings)
   - "Previous sessions" heading
   - Session list
   - View more link

7. **PreviousSessionHistory.vue** - Session history (8+ strings)
   - History timeline
   - Session summaries

8. **PreviousSessionSummary.vue** - Summary display (6+ strings)
   - Summary text

9. **PreviousSessionSummaryStrip.vue** - Compact summary (5+ strings)
   - Compact display

10. **DeletedNotesSection.vue** - Deleted notes recovery (8+ strings)
    - Deleted notes list
    - Restore button

---

## Payment Components (4 files)

Located in `/frontend/src/components/appointments/` and `/frontend/src/components/settings/`

1. **PaymentTrackingCard.vue** - Payment UI in appointments (20+ strings)
   - Payment method options (Cash, Card, Bank Transfer, Bit, PayBox, Other)
   - Payment status options (Not Paid, Payment Sent, Paid, Waived)
   - Amount field label
   - Notes field label

2. **PaymentDetailsForm.vue** - Payment details form (15+ strings)
   - Form fields
   - Validation messages

3. **PaymentActions.vue** - Payment action buttons (8+ strings)
   - Send payment request
   - Mark as paid
   - View receipt

4. **PaymentSettings.vue** - Settings payment configuration (40+ strings) ⭐ HIGH PRIORITY
   - "Enable Payment Tracking" toggle
   - Payment provider selection
   - Per-provider configuration
     - Bit: Phone number field, placeholder
     - PayBox: URL field, placeholder
     - Bank Transfer: Bank details field, placeholder
     - Custom: Custom link field, placeholder
   - Action buttons (Copy, Share, Save, Cancel, Edit, Remove)
   - Success/error messages

---

## Settings Components (5 files)

Located in `/frontend/src/components/settings/`

1. **PaymentSettings.vue** - (See above)

2. **GoogleCalendarSettings.vue** - Calendar sync (15+ strings)
   - "Google Calendar Integration" title
   - Enable toggle
   - Sync direction
   - Authorize button
   - Disconnect button
   - Last synced display
   - Error messages

3. **SettingsSidebar.vue** - Settings navigation (10+ strings)
   - Navigation menu items
   - Settings categories

4. **SettingsCard.vue** - Settings card wrapper (5+ strings)
   - Card title
   - Card description

5. **SettingsLayout.vue** - Settings page layout (5+ strings)
   - Page structure
   - Navigation

---

## Common/Shared Components (20+ files)

Located in `/frontend/src/components/common/`

1. **AppointmentToastContent.vue** - Rich toast notification (10+ strings)
   - Appointment details display
   - Action buttons

2. **AutosaveBanner.vue** - Autosave indicator (5+ strings)
   - "Autosaved" message
   - Status text

3. **BaseButton.vue** - Button component (2+ strings)
   - Text/labels passed as content

4. **DirectionsButton.vue** - Directions link (5+ strings)
   - "Get directions" text
   - Location context

5. **EmptyState.vue** - Empty state template (10+ strings)
   - Empty title
   - Empty description
   - CTA button text

6. **FloatingActionButton.vue** - FAB button (5+ strings)
   - Button label
   - Title/tooltip

7. **KebabMenu.vue** - Context menu (8+ strings)
   - Menu items
   - Actions

8. **LoadingSpinner.vue** - Loading indicator (3+ strings)
   - Loading message

9. **PageHeader.vue** - Page title header (8+ strings)
   - Title
   - Subtitle
   - Back button

10. **RateLimitBanner.vue** - Rate limit warning (8+ strings)
    - Rate limit message
    - Retry countdown

11. **SessionExpirationBanner.vue** - Session expiry warning (8+ strings)
    - Warning message
    - Action buttons

12. **SessionExpirationModal.vue** - Session expiry modal (10+ strings)
    - Modal title
    - Warning message
    - Buttons (Stay signed in, Sign out)

13. **SessionTimeoutModal.vue** - Timeout modal (8+ strings)
    - Timeout message
    - Action buttons

14. **SkeletonLoader.vue** - Loading skeleton (3+ strings)
    - Minimal text

15. **TimePickerDropdown.vue** - Time picker (5+ strings)
    - Label
    - Time options

16. **ToggleSwitch.vue** - Toggle switch (3+ strings)
    - Label

17-20+. Additional common components

---

## Authentication Components (3 files)

Located in `/frontend/src/components/auth/`

1. **LogoutConfirmationModal.vue** - Sign out confirmation (8+ strings)
   - "Sign Out?" title
   - Confirmation message
   - Buttons (Sign Out, Cancel)

2. **SessionExpirationModal.vue** - (See above)

3. **SessionExpirationBanner.vue** - (See above)

---

## Platform Admin Components (5 files)

Located in `/frontend/src/components/platform-admin/`

1. **CreateWorkspaceModal.vue** - Workspace creation (15+ strings)
   - Modal title
   - Form fields
   - Validation messages
   - Buttons

2. **ConfirmationModal.vue** - Generic confirmation (8+ strings)
   - Title
   - Message
   - Buttons

3. **WorkspaceDetailsModal.vue** - Workspace details (10+ strings)
   - Details display
   - Edit/Delete buttons

4. **ActivityTimeline.vue** - Activity log (10+ strings)
   - Timeline labels
   - Activity descriptions

5. **ActivityItem.vue** - Single activity (5+ strings)
   - Activity type label
   - Timestamp

---

## Summary Statistics

| Category | Files | Total Strings | Priority |
|----------|-------|---------------|----------|
| Views | 11 | ~155 | HIGH |
| Calendar | 15 | ~150 | CRITICAL |
| Clients | 8 | ~80 | HIGH |
| Sessions | 10 | ~115 | HIGH |
| Payments | 4 | ~70 | MEDIUM |
| Settings | 5 | ~50 | MEDIUM |
| Common | 20+ | ~150 | HIGH |
| Auth | 3 | ~25 | HIGH |
| Admin | 5 | ~50 | MEDIUM |
| **Total** | **94** | **~450-500** | - |

---

## Priority Migration Order

### Phase 1 (Week 1 - Views)
- LoginView.vue (25+ strings)
- CalendarView.vue (20+ strings)
- ClientsView.vue (15+ strings)
- SessionView.vue (15+ strings)
- ClientDetailView.vue (10+ strings)
- Others (5-10 strings each)

### Phase 2 (Week 1-2 - High Impact Components)
- AppointmentFormModal.vue (35+ strings)
- ClientFormModal.vue (20+ strings)
- PaymentSettings.vue (40+ strings)
- Common components (20 files)

### Phase 3 (Week 2 - Feature Components)
- All Calendar components
- All Session components
- All Client components
- All Payment components

### Phase 4 (Week 2-3 - Remaining)
- Admin components
- Settings components
- Other remaining components

### Phase 5 (Week 3 - Integration)
- Third-party locale config (FullCalendar, date-fns)
- Language selector UI
- Testing across all components

---

Note: All file paths relative to `/frontend/src/`
