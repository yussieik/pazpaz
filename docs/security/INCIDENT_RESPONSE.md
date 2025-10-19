# PazPaz Security Incident Response Plan

**Last Updated:** 2025-10-19
**Version:** 1.0
**Status:** Production Ready
**Classification:** Internal (Confidential)

---

## Table of Contents

1. [Overview](#overview)
2. [Incident Classification](#incident-classification)
3. [Escalation Procedures](#escalation-procedures)
4. [Incident Response Playbook](#incident-response-playbook)
5. [HIPAA Breach Notification Requirements](#hipaa-breach-notification-requirements)
6. [Communication Plan](#communication-plan)
7. [Post-Incident Review](#post-incident-review)
8. [Evidence Collection & Chain of Custody](#evidence-collection--chain-of-custody)

---

## Overview

This document defines procedures for responding to security incidents affecting PazPaz PHI/PII data. As a HIPAA-covered entity, PazPaz must respond to security incidents within strict timelines to meet regulatory requirements.

### Incident Response Objectives

1. **Contain**: Stop ongoing attack, prevent further damage
2. **Eradicate**: Remove attacker access, fix vulnerability
3. **Recover**: Restore service to normal operations
4. **Learn**: Document incident, prevent recurrence

### Regulatory Timeline

- **Detection to Containment**: Within 1 hour (Critical), 4 hours (High)
- **Breach Discovery to Notification**: 60 days maximum (HIPAA requirement)
- **Incident Documentation**: Within 24 hours of resolution

---

## Incident Classification

### Severity Levels

#### Critical (Severity 1)

**Definition**: Active PHI breach or imminent risk of PHI exposure

**Examples**:
- ✅ Confirmed unauthorized access to PHI database
- ✅ Encryption key compromised and PHI accessed
- ✅ Ransomware attack encrypting PHI data
- ✅ Database publicly exposed to internet
- ✅ Mass PHI exfiltration detected
- ✅ Insider threat actively stealing PHI

**Response Time**: Immediate (< 15 minutes)
**Escalation**: Security Officer + CEO + Legal Counsel
**Notification**: HIPAA breach notification likely required

#### High (Severity 2)

**Definition**: Potential PHI exposure or significant security control failure

**Examples**:
- ✅ Successful SQL injection attack (no confirmed PHI access)
- ✅ Encryption key exposed in logs (no evidence of decryption)
- ✅ Unauthorized login attempt succeeded
- ✅ Cross-workspace data access attempt detected
- ✅ File upload malware detected and quarantined
- ✅ Rate limiting bypass allowing brute force attacks

**Response Time**: Within 1 hour
**Escalation**: Security Officer + Incident Response Team
**Notification**: Breach assessment required

#### Medium (Severity 3)

**Definition**: Security control degradation or attempted attack (unsuccessful)

**Examples**:
- ✅ Multiple failed login attempts (rate limited)
- ✅ CSRF token validation failures (attack blocked)
- ✅ Suspicious API access patterns (no PHI accessed)
- ✅ Outdated dependency with known vulnerability
- ✅ SSL certificate expiring soon
- ✅ Audit log anomalies (investigation needed)

**Response Time**: Within 4 hours
**Escalation**: On-call Engineer + Security Officer
**Notification**: Internal only

#### Low (Severity 4)

**Definition**: Minor security event, no immediate risk

**Examples**:
- ✅ Routine failed login attempts (single user)
- ✅ Invalid JWT token rejected
- ✅ File upload rejected (wrong file type)
- ✅ Non-critical dependency update available
- ✅ Security scan false positive

**Response Time**: Within 24 hours
**Escalation**: On-call Engineer
**Notification**: Internal ticketing system

---

## Escalation Procedures

### Incident Response Team

| Role | Primary Contact | Backup Contact | Responsibilities |
|------|----------------|----------------|------------------|
| **Security Officer** | security@pazpaz.com | backup-security@pazpaz.com | Incident commander, breach assessment, regulatory notifications |
| **On-Call Engineer** | oncall@pazpaz.com | PagerDuty rotation | First responder, containment, technical investigation |
| **Database Administrator** | dba@pazpaz.com | backup-dba@pazpaz.com | Database forensics, encryption key rotation, data recovery |
| **DevOps Lead** | devops@pazpaz.com | backup-devops@pazpaz.com | Infrastructure containment, log collection, system restoration |
| **HIPAA Compliance Officer** | compliance@pazpaz.com | — | Breach notification assessment, HHS reporting |
| **Legal Counsel** | legal@pazpaz.com | — | Regulatory guidance, breach notification wording |
| **CEO/Founder** | ceo@pazpaz.com | — | Executive decisions, public statements (if required) |

### Escalation Matrix

```
Low (S4) → On-Call Engineer
            ↓ (if PHI accessed)
Medium (S3) → Security Officer
               ↓ (if breach suspected)
High (S2) → Security Officer + Incident Response Team + HIPAA Compliance Officer
             ↓ (if breach confirmed)
Critical (S1) → Full Escalation (Security Officer + CEO + Legal Counsel + HHS notification)
```

### Contact Methods

**Immediate (Critical/High)**:
- PagerDuty alert (on-call engineer)
- Phone call (Security Officer personal phone)
- Slack #security-incidents channel (urgent ping)

**Non-Urgent (Medium/Low)**:
- Email to security@pazpaz.com
- Jira ticket (component: Security)
- Slack #security channel

---

## Incident Response Playbook

### Phase 1: Detect & Assess (0-15 minutes)

**Actions**:
1. **Incident Detection**
   - Automated alert (CloudWatch, Datadog, PagerDuty)
   - User report (support ticket, email)
   - Security scan finding (penetration test, vulnerability scan)
   - Manual discovery (code review, audit log review)

2. **Initial Assessment**
   ```
   INCIDENT ASSESSMENT TEMPLATE

   Date/Time: [TIMESTAMP]
   Reported By: [NAME/SYSTEM]
   Detection Method: [Alert/User Report/Manual]

   Incident Type:
   [ ] PHI Data Breach
   [ ] Unauthorized Access
   [ ] Malware/Ransomware
   [ ] SQL Injection
   [ ] Cross-Workspace Data Access
   [ ] Encryption Key Compromise
   [ ] DDoS Attack
   [ ] Insider Threat
   [ ] Other: ______________

   Severity Assessment:
   [ ] Critical (S1) - Active PHI breach
   [ ] High (S2) - Potential PHI exposure
   [ ] Medium (S3) - Security control failure
   [ ] Low (S4) - Minor event

   Affected Systems:
   [ ] API Server (pazpaz-api)
   [ ] Database (PostgreSQL)
   [ ] File Storage (S3/MinIO)
   [ ] Redis Cache
   [ ] Authentication System
   [ ] Audit Logging

   PHI at Risk:
   [ ] Client Names
   [ ] Contact Information
   [ ] Medical History
   [ ] Session Notes (SOAP)
   [ ] Photos/Attachments
   [ ] Estimated # of records: __________
   ```

3. **Classify Severity** (use classification matrix above)

4. **Escalate**
   - Critical: Page Security Officer immediately
   - High: Email + Slack Security Officer within 15 minutes
   - Medium: Slack + email within 1 hour
   - Low: Email within 4 hours

### Phase 2: Contain (15-60 minutes)

**Objective**: Stop ongoing attack, prevent further damage

**Containment Actions by Incident Type**:

#### Unauthorized Database Access
```bash
# 1. Revoke compromised credentials
psql -h db-host -U admin -c "REVOKE ALL ON DATABASE pazpaz FROM compromised_user;"

# 2. Rotate database password (emergency)
# See /docs/security/KEY_MANAGEMENT.md - Emergency Rotation

# 3. Block attacker IP at firewall
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxx \
  --protocol tcp \
  --port 5432 \
  --cidr 0.0.0.0/0 \
  --revoke  # Then re-add only known IPs

# 4. Enable read-only mode (if needed)
psql -c "ALTER DATABASE pazpaz SET default_transaction_read_only = on;"
```

#### Encryption Key Compromised
```bash
# Follow emergency key rotation procedure
# See /docs/security/KEY_MANAGEMENT.md - Emergency Rotation

# Timeline: 24 hours max
# 0-2h: Generate new key
# 2-4h: Deploy dual-key application
# 4-24h: Accelerated re-encryption
# 24h: Retire compromised key
```

#### Malware/Ransomware
```bash
# 1. Isolate infected servers
kubectl cordon node-xxx  # Prevent new pods
kubectl drain node-xxx   # Evict existing pods

# 2. Snapshot volumes (forensics)
aws ec2 create-snapshot --volume-id vol-xxx

# 3. Terminate infected instances
kubectl delete pod/infected-pod --force

# 4. Deploy clean instances from golden image
kubectl apply -f k8s/deployment.yaml
```

#### SQL Injection Attack
```bash
# 1. Block attacker IP
iptables -A INPUT -s <ATTACKER_IP> -j DROP

# 2. Enable WAF rule to block SQL patterns
aws wafv2 update-web-acl --id xxx --rules '[{"Name":"BlockSQLInjection","Priority":1,"Action":{"Block":{}},...}]'

# 3. Review audit logs for data access
psql -c "SELECT * FROM audit_events WHERE ip_address = '<ATTACKER_IP>' ORDER BY created_at DESC;"

# 4. Patch vulnerable endpoint
# (Emergency code deployment)
```

### Phase 3: Eradicate (1-4 hours)

**Objective**: Remove attacker access, fix root cause

**Eradication Actions**:

1. **Patch Vulnerability**
   - Apply security patch (code fix)
   - Update dependency (npm/pip update)
   - Reconfigure security control (fix misconfiguration)

2. **Revoke All Attacker Access**
   ```bash
   # Rotate all credentials attacker may have accessed
   # - Database password
   # - Encryption keys
   # - JWT secret
   # - S3 access keys
   # - Redis password
   ```

3. **Malware Removal**
   ```bash
   # Re-deploy from clean images
   kubectl set image deployment/pazpaz-api pazpaz-api=pazpaz-api:v1.2.3-clean

   # Scan all volumes with ClamAV
   clamscan -r /mnt/volumes --infected --remove
   ```

4. **Fix Root Cause**
   - Code review and fix vulnerable code
   - Update firewall rules
   - Enable missing security controls
   - Improve monitoring/alerting

### Phase 4: Recover (4-24 hours)

**Objective**: Restore normal operations, verify system integrity

**Recovery Actions**:

1. **Restore Services**
   ```bash
   # Re-enable database writes
   psql -c "ALTER DATABASE pazpaz SET default_transaction_read_only = off;"

   # Scale up application
   kubectl scale deployment/pazpaz-api --replicas=3

   # Verify health checks
   curl https://api.pazpaz.com/health
   ```

2. **Verify Data Integrity**
   ```sql
   -- Check record counts (pre vs post incident)
   SELECT COUNT(*) FROM clients;
   SELECT COUNT(*) FROM sessions;

   -- Check for data corruption
   SELECT COUNT(*) FROM clients WHERE full_name NOT LIKE 'v%:%:%';
   -- Expected: 0 (all records should be encrypted)
   ```

3. **Restore from Backup (if data loss)**
   ```bash
   # Restore PostgreSQL from latest clean backup
   pg_restore -h db-host -U pazpaz -d pazpaz /backups/pazpaz-clean-backup.dump

   # Restore S3 files from versioned bucket
   aws s3 sync s3://pazpaz-backups/files-clean/ s3://pazpaz-files/
   ```

4. **Monitor for Recurrence**
   - Enhanced logging (temporary)
   - Additional alerting rules
   - Daily review for 7 days post-incident

### Phase 5: Document & Learn (24-72 hours)

**Objective**: Complete post-incident review, implement preventive measures

See [Post-Incident Review](#post-incident-review) section below.

---

## HIPAA Breach Notification Requirements

### Breach Definition (HIPAA §164.402)

**A breach is**:
- Unauthorized acquisition, access, use, or disclosure of PHI
- That compromises the security or privacy of the PHI

**Exceptions** (safe harbor):
- ✅ Encrypted PHI (key not compromised)
- ✅ Good faith unintentional access by workforce member
- ✅ Inadvertent disclosure to authorized person (same covered entity)
- ✅ PHI cannot reasonably be retained by recipient

### Breach Notification Timeline

**60-Day Rule**:
- Discovery date: When incident first known or reasonably should have been known
- Notification deadline: 60 days from discovery date

**Immediate Notification** (< 60 days):
- Breach affecting >500 individuals: Notify HHS and media immediately
- Breach affecting 10+ individuals: Notify individuals within 60 days
- Breach affecting <10 individuals: Maintain log, notify annually

### Breach Notification Recipients

#### 1. Affected Individuals (Required)

**Timeline**: Within 60 days of discovery
**Method**: First-class mail (email acceptable if individual consented)

**Notification Must Include**:
- Brief description of what happened
- Types of PHI involved (name, address, medical history, etc.)
- Steps individuals should take to protect themselves
- What PazPaz is doing to investigate and prevent recurrence
- Contact information for questions

**Template**: See [Breach Notification Template](#breach-notification-template) below

#### 2. HHS Secretary (Required if >500 individuals)

**Timeline**: Contemporaneous with individual notification (within 60 days)
**Method**: HHS Breach Portal (online submission)
**URL**: https://ocrportal.hhs.gov/ocr/breach/wizard_breach.jsf

**Information Required**:
- Name and contact information for covered entity
- Date of breach discovery
- Estimated number of individuals affected
- Types of PHI involved
- Brief description of breach
- Safeguards in place before breach
- Actions taken in response

#### 3. Media Notice (Required if >500 individuals in same state/jurisdiction)

**Timeline**: Same time as individual notification
**Method**: Prominent media outlets in affected state
**Format**: Press release

#### 4. Annual Notification (For breaches <10 individuals)

**Timeline**: Within 60 days of year-end
**Method**: Mail to HHS (not via portal)
**Content**: Log of all breaches affecting <10 individuals

### Breach Risk Assessment

**Decision Tree**:

```
Was PHI accessed by unauthorized person?
  └─ YES
      └─ Was PHI encrypted with un-compromised key?
          ├─ YES → SAFE HARBOR (no breach notification required)
          │         └─ Document safe harbor justification
          └─ NO
              └─ Conduct 4-factor risk assessment:
                  1. Nature/extent of PHI (names, SSNs, medical records?)
                  2. Unauthorized person who accessed PHI (employee, hacker?)
                  3. Was PHI actually acquired or viewed? (logs confirm access?)
                  4. Extent to which risk has been mitigated (key rotated, attacker blocked?)

                  Risk Assessment Result:
                    Low Risk → No notification required (document assessment)
                    High Risk → BREACH NOTIFICATION REQUIRED (60-day timeline)
```

**4-Factor Risk Assessment Template**:

```
HIPAA BREACH RISK ASSESSMENT

Date of Assessment: [DATE]
Assessor: [HIPAA Compliance Officer]

Factor 1: Nature and Extent of PHI Involved
  [ ] Limited (names only)
  [ ] Moderate (names + contact info)
  [ ] Extensive (names + medical history + SSN)

  Types of PHI:
  [ ] Client names
  [ ] Contact information (phone, email, address)
  [ ] Medical history
  [ ] Session notes (SOAP documentation)
  [ ] Photos/attachments
  [ ] Financial information
  [ ] SSN or other identifiers

  Number of individuals affected: _______

Factor 2: Unauthorized Person
  [ ] Internal workforce member (accidental)
  [ ] External attacker (intentional)
  [ ] Known person: _______________
  [ ] Unknown/anonymous attacker

  Intent:
  [ ] Accidental/unintentional
  [ ] Intentional (malicious)

Factor 3: Was PHI Actually Acquired or Viewed?
  [ ] Confirmed acquisition (logs show data downloaded)
  [ ] Likely acquired (attacker had access for extended period)
  [ ] Unknown (logs inconclusive)
  [ ] Not acquired (access logged but no data retrieval)

  Evidence:
  - Audit log review: _______________
  - Network traffic analysis: _______________
  - Forensic investigation findings: _______________

Factor 4: Extent of Risk Mitigation
  [ ] PHI encrypted (key not compromised) → SAFE HARBOR
  [ ] Attacker access revoked immediately
  [ ] Vulnerability patched
  [ ] Encryption key rotated (if compromised)
  [ ] Affected individuals notified and offered mitigation
  [ ] Credit monitoring offered (if SSN involved)

Overall Risk Determination:
  [ ] Low Risk → No breach notification required
  [ ] High Risk → BREACH NOTIFICATION REQUIRED

Justification:
[Document reasoning for risk determination based on 4 factors]

Approvals:
  HIPAA Compliance Officer: _____________ Date: _______
  Legal Counsel: _____________ Date: _______
  CEO: _____________ Date: _______
```

---

## Communication Plan

### Internal Communication

**Incident Declared**:
- Slack #security-incidents: Real-time updates
- Email to incident-response@pazpaz.com: Detailed status updates (every 4 hours)
- Status page (internal): "Investigating security incident"

**Incident Resolved**:
- All-hands email: Summary of incident, actions taken
- Postmortem meeting: Within 72 hours

### External Communication

**Customer Notification** (if breach confirmed):
- Email to affected customers (HIPAA-compliant notification)
- FAQ page on website
- Customer support trained on incident response

**Regulatory Notification**:
- HHS breach portal submission (if >500 individuals)
- State AG notification (if required by state law)

**Media Statement** (if required):
- Prepared by CEO + Legal Counsel
- Coordinated with PR firm (if applicable)
- Focus on actions taken, patient protection measures

### Breach Notification Template

**Email Subject**: Important Notice: PazPaz Data Security Incident

```
Dear [CLIENT_NAME],

We are writing to notify you of a data security incident that may have affected your personal health information stored in the PazPaz practice management system.

WHAT HAPPENED
On [DATE], we discovered that [BRIEF_DESCRIPTION_OF_INCIDENT]. We immediately launched an investigation and took steps to contain the incident.

WHAT INFORMATION WAS INVOLVED
The information potentially accessed includes:
- Your name, contact information (phone, email, address)
- [Medical history and treatment notes] (if applicable)
- [Session documentation (SOAP notes)] (if applicable)
- [Photos uploaded during sessions] (if applicable)

WHAT WE ARE DOING
Upon discovering this incident, we:
- Immediately secured our systems and blocked unauthorized access
- Launched a forensic investigation with external cybersecurity experts
- Notified law enforcement and regulatory authorities
- [Rotated encryption keys to prevent further unauthorized access] (if applicable)
- Implemented additional security measures to prevent recurrence

WHAT YOU CAN DO
While we have no evidence that your information has been misused, we recommend:
- Monitor your accounts for suspicious activity
- [Consider placing a fraud alert on your credit reports] (if SSN involved)
- [Enroll in complimentary credit monitoring services (details below)] (if offered)
- Report any suspicious activity to local law enforcement

FOR MORE INFORMATION
We have established a dedicated helpline to answer your questions:
- Phone: 1-800-XXX-XXXX (Mon-Fri 9am-5pm EST)
- Email: incident-response@pazpaz.com
- Website: https://pazpaz.com/security-incident-faq

We sincerely apologize for this incident and any concern it may cause. Protecting your information is our highest priority.

Sincerely,
[CEO_NAME]
Chief Executive Officer
PazPaz

---
This notification is provided pursuant to the Health Insurance Portability and Accountability Act (HIPAA) Privacy Rule, 45 C.F.R. § 164.404.
```

---

## Post-Incident Review

### Postmortem Meeting

**Timeline**: Within 72 hours of incident resolution
**Attendees**: Incident Response Team + affected engineers + management
**Duration**: 90 minutes

**Agenda**:
1. Incident timeline (5-10 min)
2. Root cause analysis (20-30 min)
3. Response effectiveness (15-20 min)
4. Lessons learned (20-30 min)
5. Action items (15-20 min)

### Postmortem Report Template

```
SECURITY INCIDENT POSTMORTEM

Incident ID: INC-2025-XXX
Date: [INCIDENT_DATE]
Severity: [Critical/High/Medium/Low]
Status: Resolved

EXECUTIVE SUMMARY
[2-3 sentences describing what happened and impact]

TIMELINE
[Chronological list of key events]

00:00 - Incident detection (alert triggered)
00:15 - Severity assessment (classified as High)
00:30 - Containment actions initiated (attacker IP blocked)
01:00 - Vulnerability identified (SQL injection in /api/v1/clients)
02:00 - Patch deployed (emergency code release)
04:00 - Normal operations resumed
08:00 - Monitoring period began (7 days enhanced logging)

IMPACT ASSESSMENT
- Users affected: [NUMBER]
- PHI records accessed: [NUMBER]
- Service downtime: [DURATION]
- Data loss: [YES/NO - describe if yes]
- Breach notification required: [YES/NO]

ROOT CAUSE ANALYSIS
Primary Cause:
[What caused the incident?]

Contributing Factors:
1. [Factor 1]
2. [Factor 2]
3. [Factor 3]

Why it wasn't caught earlier:
[Gap in monitoring, testing, code review, etc.]

RESPONSE EFFECTIVENESS
What went well:
- [Positive aspect 1]
- [Positive aspect 2]

What could be improved:
- [Improvement 1]
- [Improvement 2]

LESSONS LEARNED
1. [Lesson 1]
2. [Lesson 2]
3. [Lesson 3]

ACTION ITEMS
| Action | Owner | Priority | Due Date | Status |
|--------|-------|----------|----------|--------|
| [Action 1] | [Name] | Critical | [Date] | [Open/In Progress/Done] |
| [Action 2] | [Name] | High | [Date] | [Open/In Progress/Done] |
| [Action 3] | [Name] | Medium | [Date] | [Open/In Progress/Done] |

PREVENTION MEASURES
Short-term (0-30 days):
- [Measure 1]
- [Measure 2]

Long-term (30-90 days):
- [Measure 1]
- [Measure 2]

APPROVALS
Incident Commander: _____________ Date: _______
Security Officer: _____________ Date: _______
CEO: _____________ Date: _______
```

---

## Evidence Collection & Chain of Custody

### Evidence Types

**Digital Evidence**:
- Server logs (application, web server, database)
- Network packet captures (tcpdump, Wireshark)
- Disk images (compromised servers)
- Memory dumps (running processes)
- Audit logs (database queries, API requests)
- Email communications (phishing attempts)

**Physical Evidence**:
- Compromised devices (laptops, servers)
- USB drives (malware vectors)
- Printed documents (if applicable)

### Collection Procedure

```bash
# 1. Preserve logs immediately (before rotation)
mkdir -p /forensics/INC-2025-XXX/logs
cp /var/log/pazpaz/*.log /forensics/INC-2025-XXX/logs/
chmod 400 /forensics/INC-2025-XXX/logs/*  # Read-only

# 2. Export audit logs from database
psql -c "\COPY (SELECT * FROM audit_events WHERE created_at >= '2025-10-19 00:00:00' AND created_at <= '2025-10-19 23:59:59') TO '/forensics/INC-2025-XXX/audit_logs.csv' CSV HEADER;"

# 3. Capture network traffic (if attack ongoing)
tcpdump -i eth0 -w /forensics/INC-2025-XXX/network-capture.pcap

# 4. Take disk snapshot (AWS EBS)
aws ec2 create-snapshot \
  --volume-id vol-compromised \
  --description "Forensic snapshot INC-2025-XXX" \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Incident,Value=INC-2025-XXX},{Key=Date,Value=2025-10-19}]'

# 5. Hash all evidence files (integrity verification)
cd /forensics/INC-2025-XXX
sha256sum * > SHA256SUMS
gpg --clearsign SHA256SUMS
```

### Chain of Custody Form

```
CHAIN OF CUSTODY FORM

Incident ID: INC-2025-XXX
Evidence ID: EVID-001
Description: Application server logs (pazpaz-api-20251019.log)

Collection:
  Date/Time: [TIMESTAMP]
  Collected By: [NAME]
  Location: /var/log/pazpaz/
  Method: File copy + SHA256 hash
  Hash: [SHA256_HASH]

Transfers:
  1. [DATE/TIME] - From [NAME] to [NAME] - Purpose: [REASON]
  2. [DATE/TIME] - From [NAME] to [NAME] - Purpose: [REASON]

Storage:
  Location: /forensics/INC-2025-XXX/ (encrypted volume)
  Access: Security Officer + Law Enforcement only

Signatures:
  Collected by: _____________ Date: _______
  Received by: _____________ Date: _______
```

---

**Document Owner**: Security Officer + HIPAA Compliance Officer
**Review Schedule**: Annually
**Next Review**: 2026-10-19
**Approved By**: Security Officer, Legal Counsel, CEO
