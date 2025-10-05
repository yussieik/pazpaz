# PazPaz Documentation

This directory contains all project-wide documentation for the PazPaz practice management system.

## 📁 Directory Structure

```
docs/
├── README.md                              # This file
├── SECURITY_FIRST_IMPLEMENTATION_PLAN.md  # Master implementation plan
├── PROJECT_OVERVIEW.md                    # Product overview and features
├── CONTEXT.md                             # Project context
├── AGENT_ROUTING_GUIDE.md                 # Agent delegation guide
│
├── security/                              # Security & Compliance
│   ├── AUDIT_LOGGING_SCHEMA.md
│   ├── AUDIT_LOGGING_IMPLEMENTATION_REPORT.md
│   ├── REDIS_CONFIGURATION.md
│   ├── REDIS_MIGRATION_GUIDE.md
│   └── REDIS_SECURITY_IMPLEMENTATION_SUMMARY.md
│
├── architecture/                          # System Architecture
│   ├── ARCHITECTURE_SUMMARY.md
│   └── BACKEND_ARCHITECTURE_DESIGN.md
│
├── testing/                               # Testing Strategy
│   └── ROUTING_TEST_SCENARIOS.md
│
├── frontend/                              # Frontend (Vue 3)
│   └── README.md (Coming in Week 2+)
│
├── backend/                               # Backend (High-level)
│   └── README.md (API design, auth flows)
│
├── deployment/                            # Infrastructure & Deployment
│   └── README.md (Coming in Week 5)
│
└── operations/                            # Day-to-day Operations
    └── README.md (Coming in Week 5)
```

## 📚 Documentation Categories

### Main Documentation (Root Level)

**High-level planning and overview documents that apply to the entire project.**

- **SECURITY_FIRST_IMPLEMENTATION_PLAN.md** - 5-week implementation plan with security-first approach
- **PROJECT_OVERVIEW.md** - Product vision, features, and success criteria
- **CONTEXT.MD** - Project context and background
- **AGENT_ROUTING_GUIDE.md** - Guide for delegating tasks to specialized agents

### Security & Compliance (`security/`)

**Authentication, authorization, audit logging, and HIPAA compliance documentation.**

- **AUDIT_LOGGING_SCHEMA.md** - Database schema for audit events (immutable logs)
- **AUDIT_LOGGING_IMPLEMENTATION_REPORT.md** - Audit middleware implementation details
- **REDIS_CONFIGURATION.md** - Redis security configuration guide
- **REDIS_MIGRATION_GUIDE.md** - Migration guide for Redis authentication
- **REDIS_SECURITY_IMPLEMENTATION_SUMMARY.md** - Redis security implementation summary

### Architecture (`architecture/`)

**System design, component architecture, and technical decisions.**

- **ARCHITECTURE_SUMMARY.md** - High-level architecture overview
- **BACKEND_ARCHITECTURE_DESIGN.md** - Detailed backend architecture (FastAPI, SQLAlchemy)

### Testing (`testing/`)

**Testing strategy, test patterns, and quality assurance.**

- **ROUTING_TEST_SCENARIOS.md** - API routing test scenarios

### Frontend (`frontend/`)

**Vue 3 application documentation (Coming in Week 2+).**

- Component architecture and patterns
- State management (Pinia)
- API integration
- UI/UX guidelines and design system
- Performance optimization

### Backend (`backend/`)

**High-level backend documentation.**

- API design patterns
- Authentication flows
- Error handling
- Middleware stack

### Deployment (`deployment/`)

**Infrastructure and deployment documentation (Coming in Week 5).**

- AWS/cloud infrastructure
- CI/CD pipelines
- Environment configuration
- Database migration procedures
- Monitoring and alerting

### Operations (`operations/`)

**Day-to-day operations and maintenance (Coming in Week 5).**

- Runbooks and procedures
- Troubleshooting guides
- Incident response
- Performance tuning
- Security incident procedures

---

## 🔒 Backend-Specific Documentation

For backend-specific documentation (encryption, testing infrastructure), see:

```
backend/docs/
├── encryption/     # Encryption implementation guides
└── testing/        # pytest configuration and test fixtures
```

See [backend/docs/README.md](../backend/docs/README.md) for details.

---

## 📖 Reading Guide

### For New Developers

1. Start with **PROJECT_OVERVIEW.md** to understand the product
2. Read **SECURITY_FIRST_IMPLEMENTATION_PLAN.md** to understand the development approach
3. Review **architecture/ARCHITECTURE_SUMMARY.md** for system design
4. Check **AGENT_ROUTING_GUIDE.md** to understand how to delegate tasks

### For Security Review

1. **SECURITY_FIRST_IMPLEMENTATION_PLAN.md** - Week 1 security foundation
2. **security/AUDIT_LOGGING_SCHEMA.md** - Audit trail design
3. **security/REDIS_SECURITY_IMPLEMENTATION_SUMMARY.md** - Redis hardening
4. **backend/docs/encryption/** - PHI encryption implementation

### For Architecture Review

1. **architecture/BACKEND_ARCHITECTURE_DESIGN.md** - Detailed backend design
2. **architecture/ARCHITECTURE_SUMMARY.md** - High-level overview
3. **PROJECT_OVERVIEW.md** - Product requirements driving architecture

---

## 🔄 Documentation Maintenance

### When to Update

- **Weekly:** Update SECURITY_FIRST_IMPLEMENTATION_PLAN.md with progress
- **After Major Changes:** Update architecture docs when system design changes
- **New Features:** Document security controls, audit logging, and encryption
- **Bug Fixes:** Update relevant guides with lessons learned

### Documentation Standards

- Use clear, descriptive headers
- Include code examples where relevant
- Document security rationale (HIPAA compliance, OWASP best practices)
- Keep diagrams and examples up-to-date
- Link to related documentation

---

## 📝 Quick Links

### Implementation

- [Security-First Implementation Plan](SECURITY_FIRST_IMPLEMENTATION_PLAN.md)
- [Agent Routing Guide](AGENT_ROUTING_GUIDE.md)

### Architecture

- [Backend Architecture](architecture/BACKEND_ARCHITECTURE_DESIGN.md)
- [Architecture Summary](architecture/ARCHITECTURE_SUMMARY.md)

### Security

- [Audit Logging Schema](security/AUDIT_LOGGING_SCHEMA.md)
- [Redis Security](security/REDIS_SECURITY_IMPLEMENTATION_SUMMARY.md)

### Backend-Specific

- [Encryption Guides](../backend/docs/encryption/)
- [Testing Infrastructure](../backend/docs/testing/)
