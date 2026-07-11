# IT Security Policies

## Information Security Policy

### Purpose
Protect company information assets from unauthorized access, disclosure, modification, or destruction.

### Scope
Applies to all employees, contractors, vendors, and third parties with access to company systems.

### Policy Owner
Director of IT and Information Security Officer

## Access Control

### Account Management
- Unique user IDs for each person
- No shared accounts (except service accounts)
- Immediate deprovisioning on termination
- Quarterly access reviews

### Authentication
- Passwords: Minimum 12 characters, complex
- MFA required for all cloud services
- SSO where possible
- Biometric for mobile devices

### Password Requirements
- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, symbols
- Changed every 90 days
- No reuse of last 12 passwords
- No dictionary words

### Privileged Access
- Admin accounts separate from regular use
- Just-in-time access for elevated privileges
- Logging of all admin actions
- Monthly admin access review

## Data Protection

### Data Classification

| Level | Description | Examples |
|-------|-------------|----------|
| Public | No restriction | Marketing materials, website |
| Internal | Company use | Internal memos, org charts |
| Confidential | Limited access | Customer data, financials |
| Restricted | Highest protection | SSNs, health data, passwords |

### Handling Requirements

**Confidential**
- Encryption in transit and at rest
- Need-to-know access
- No email to personal accounts
- Approved sharing only

**Restricted**
- Encryption required (AES-256)
- Logging of all access
- Masking where possible
- Special approval for access

### Data Storage
- Company data on approved systems only
- No local storage of confidential data
- Cloud storage approved providers only
- USB drives require encryption

## Endpoint Security

### Device Requirements
- Company-owned or approved devices only
- MDM enrollment required
- Antivirus/EDR installed
- Disk encryption enabled
- Auto-lock after 5 minutes

### Mobile Devices
- Passcode/PIN required
- Biometric enabled
- Remote wipe capability
- No jailbroken/rooted devices
- Business apps only from approved sources

### Personal Devices
- BYOD not permitted for work data
- No company email on personal devices
- No work apps on personal devices

## Network Security

### Office Network
- Separate guest and corporate networks
- WPA3 encryption
- Network access control (NAC)
- Segmentation by department

### Remote Access
- VPN required for all remote access
- Split tunneling disabled
- Session timeout: 8 hours
- No public Wi-Fi without VPN

### Network Monitoring
- Traffic analysis
- Intrusion detection
- Anomaly alerting
- Monthly review of logs

## Email Security

### Email Protection
- Spam filtering
- Phishing detection
- Attachment sandboxing
- Link protection

### Email Usage
- No confidential data in subject lines
- Encrypt emails with sensitive attachments
- Verify recipient before sending
- Report suspicious emails

### Phishing Response
- Do not click suspicious links
- Do not open unexpected attachments
- Report to: phishing@company.com
- Delete after reporting

## Incident Response

### Security Incident Types
- Malware infection
- Phishing success
- Unauthorized access
- Data breach
- Lost/stolen device
- Insider threat

### Reporting
- Immediate notification to IT
- Email: security@company.com
- Slack: #security-incidents
- Call: (555) 0100 (urgent)

### Response Process
1. **Detection**: Identify and report
2. **Containment**: Limit damage
3. **Investigation**: Determine scope
4. **Eradication**: Remove threat
5. **Recovery**: Restore operations
6. **Lessons Learned**: Prevent recurrence

### Breach Notification
- Internal: Immediate
- Customers: As required by contract/law
- Regulators: Per GDPR/state laws
- 72 hours for GDPR

## Security Awareness

### Training Requirements
- New hire: Security orientation
- Annual: Security awareness training
- Phishing simulations: Quarterly
- Role-specific: Developers, admins

### Security Tips
- Think before you click
- Verify requests for sensitive data
- Use strong, unique passwords
- Lock your workstation
- Report suspicious activity

## Vendor Security

### Due Diligence
- Security questionnaire
- SOC 2 review
- Penetration test results
- Data processing agreement

### Contract Requirements
- Security obligations
- Breach notification clause
- Right to audit
- Data return/deletion

## Compliance

### Standards
- SOC 2 Type II
- ISO 27001
- GDPR (data protection)
- CCPA (California privacy)

### Audits
- Internal: Quarterly
- External: Annual
- Penetration testing: Annual
- Vulnerability scanning: Continuous

## Enforcement

### Policy Violations
- First offense: Warning and retraining
- Second offense: Written warning
- Third offense: Disciplinary action
- Severe violations: Immediate termination

### Monitoring
- System activity logged
- DLP monitoring
- Access reviews
- Compliance audits

## Questions?
Contact: security@company.com or #security Slack channel
