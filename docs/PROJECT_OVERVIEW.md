Project Name

PazPaz — a lightweight practice management web app for independent therapists

⸻

1. Problem & Context

Independent therapists (massage, physiotherapy, psychotherapy, etc.) often manage their work using fragmented tools — Google Calendar, paper notes, spreadsheets — which makes it hard to:
	•	Maintain a consistent schedule across multiple locations or home visits
	•	Track client history and treatment notes in a structured, retrievable way
	•	Ensure continuity of care with clear session logs (like SOAP notes)
	•	Keep records compliant, secure, and accessible
	•	Communicate reliably (reminders, cancellations)

In hospitals and clinics, structured systems exist — but in private practice, solo practitioners lack a clear, secure, and simple platform.

PazPaz aims to bridge this gap by offering an integrated, privacy-first tool designed specifically for private therapists.

⸻

2. Core Objectives
	1.	Scheduling
	•	Create, update, cancel appointments
	•	Assign locations (clinic, home, online)
	•	Detect conflicts and overlaps
	•	Sync or export via ICS / Google Calendar
	2.	Client Management
	•	Maintain a list of clients with contacts, consent status, and tags
	•	View full treatment history per client
	•	Search and filter easily
	3.	Session Documentation
	•	Log each session using SOAP structure:
	•	Subjective (client-reported symptoms)
	•	Objective (therapist findings)
	•	Assessment
	•	Plan
	•	Attach photos or files
	•	Track treatment outcomes and progress
	4.	Plan of Care / Timeline
	•	Show a chronological view of all sessions, assessments, and notes
	•	Support ongoing goal tracking and scheduled reviews
	5.	Reminders & Notifications
	•	Email reminders to clients (SMS optional later)
	•	Daily summary for therapist
	6.	Payment Tracking (Phase 1.5 Complete)
	•	Manual payment tracking - therapists mark payments manually
	•	Smart payment links - auto-generate Bit SMS, PayBox URLs, bank transfer details
	•	Flexible payment methods: bank transfer, Bit, PayBox, cash, card, custom links
	•	Email payment requests with bilingual Hebrew/English templates
	•	Phase 2+: Automated provider integrations (Bit API, PayBox API, PayPlus, Stripe)
	7.	Privacy & Security
	•	All data scoped per therapist workspace
	•	Encryption at rest and in transit
	•	Audit trail for all data access/modification
	•	No third-party sharing by default

⸻

3. Non-Goals (V1)
	•	Insurance billing or claims
	•	Multi-clinic / multi-therapist scheduling
	•	Inventory or advanced financial reports
	•	Integrations with large EMRs (future optional)

⸻

4. Target Users
	•	Primary: Independent massage / physical / psychological therapists
	•	Secondary: Small clinics with up to 2 practitioners
	•	Tech-savvy enough to use a web app, but not developers

⸻

5. Product Philosophy
	•	Simplicity first — no unnecessary complexity
	•	Speed — must feel instantaneous (p95 <150 ms)
	•	Privacy — therapist is data owner; client data stays private
	•	Structure with flexibility — use best practices (SOAP) but allow notes customization

⸻

6. High-Level Architecture

Layer	Stack	Purpose
Backend	Python 3.13 + FastAPI + SQLAlchemy (async) + PostgreSQL 16	APIs, business logic, persistence
Frontend	Vue 3 + TypeScript + Tailwind CSS	User interface, responsive and minimal
Infra	Docker Compose (api, web, db, redis)	Local and deployment parity
Storage	PostgreSQL for relational data, MinIO/S3 for attachments	Durable, secure data store
Queue/Cache	Redis	Background tasks, caching reminders
Auth	Passwordless (magic link) + optional 2FA	Simple, secure authentication


⸻

7. Key Entities
	•	Workspace: therapist account context
	•	User: therapist or assistant
	•	Client: individual receiving treatment
	•	Appointment: scheduled session with location/time/status
	•	Session: SOAP-based log attached to appointment
	•	Service: type of therapy offered
	•	Location: saved places (clinic/home/online)
	•	PlanOfCare: structured long-term goals and milestones
	•	AuditEvent: log of every access/change

⸻

8. UX Principles
	•	Keyboard-first, quick actions
	•	Weekly calendar view with drag-and-drop
	•	Clean and calm visual design
	•	Autosave for notes
	•	Offline-tolerant drafts

⸻

9. V1 Milestones

Milestone	Deliverables
M1	Project scaffold, DB schema, basic CRUD for clients & appointments
M2	Calendar UI + conflict detection + reminders
M3	SOAP session notes + file attachments
M4	Client timeline view
M5	Auth + audit logs + privacy checks
M6	Polish: UX refinements, seed data, deploy staging


⸻

10. Deployment Target
	•	Start as self-hosted / single-tenant (Docker Compose)
	•	Optional managed version later (multi-tenant)

⸻

11. Success Metrics
	•	Therapist can create a client + schedule + log a SOAP note in <3 minutes total
	•	0 production PII leaks (verified by automated tests)
	•	API response <150 ms p95 for schedule endpoints

⸻

12. Future Extensions (Post-V1)
	•	Multi-user shared calendar
	•	Client portal
	•	Automated payment provider integrations (Phase 2: Bit API, PayBox API, PayPlus, Stripe)
	•	Invoice service integration (GreenInvoice, Morning, Ness)
	•	Tele-session integration
	•	Multi-language support beyond English/Hebrew
	•	Google Calendar two-way sync

⸻

13. Example Workflow
	1.	Therapist signs in via magic link
	2.	Creates a client “John Doe”
	3.	Books appointment on Monday 10:00 at “Clinic A”
	4.	After session, adds SOAP note + photo
	5.	Later views John’s timeline and sees all sessions chronologically
	6.	Reminder email sent automatically before each session

⸻

14. Notes for AI Agent (Claude Code)
	•	When planning tasks, always align with this product definition
	•	Keep each feature test-driven, with clear separation of layers
	•	Respect workspace scoping in all queries
	•	Ask for clarifications if requirements are ambiguous