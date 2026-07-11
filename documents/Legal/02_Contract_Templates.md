# Contract Templates and Playbooks

## Available Templates

### Customer Agreements
- **Master Service Agreement (MSA)**: Standard customer contract
- **Order Form**: Subscription details under MSA
- **Statement of Work (SOW)**: Professional services
- **Data Processing Agreement (DPA)**: GDPR/data protection

### Vendor Agreements
- **Vendor Agreement**: Standard vendor terms
- **Software License**: SaaS/tool subscriptions
- **Professional Services**: Consultant agreements
- **Independent Contractor**: 1099 contractor agreement

### Employment Agreements
- **Offer Letter**: Employment offer template
- **Employee Confidentiality**: IP and confidentiality
- **Severance Agreement**: Separation terms
- **Employee Invention Assignment**: IP ownership

### Other Templates
- **Mutual NDA**: Two-way confidentiality
- **One-Way NDA**: Customer or vendor NDA
- **Partnership Agreement**: Strategic partnership
- **Referral Agreement**: Referral partner terms

## Approval Matrix

| Contract Type | Value | Approvers |
|---------------|-------|-----------|
| Standard MSA | Any | Sales Director + Legal |
| Modified MSA | Any | Legal + VP Sales |
| MSA (Enterprise) | >$250K | Legal + CFO + CEO |
| Vendor Agreement | <$50K | Department Head |
| Vendor Agreement | $50K-250K | Department Head + Legal |
| Vendor Agreement | >$250K | Legal + CFO |
| Employment | Any | HR + Legal |
| NDA | Any | Any manager |

## Contract Playbooks

### Customer MSA Negotiation
**Acceptable Changes**
- ✓ Standard liability cap: 12 months fees
- ✓ Standard term: Annual auto-renew
- ✓ Standard termination: 30-day notice
- ✓ Standard governing law: Delaware

**Red Lines (Require Approval)**
- ✗ Unlimited liability
- ✗ Indemnification for our IP (unless standard)
- ✗ Non-standard termination rights
- ✗ Payment terms > Net 30
- ✗ Auto-renewal opt-out <60 days

**Negotiation Tips**
- Start with our template
- Use agreed fallback positions
- Escalate early on red lines
- Document all concessions

### Vendor Agreement Review
**Key Terms to Negotiate**
- Service levels and remedies
- Data security requirements
- Termination rights
- Liability limitations
- Auto-renewal terms

**Security Requirements**
- SOC 2 Type II certification
- Data encryption in transit and at rest
- Incident notification: 24 hours
- Right to audit
- Data deletion on termination

## Contract Lifecycle

### Request
- Submit via Slack #legal-requests
- Include business context
- Attach draft or template needed
- Specify deadline

### Review
- Legal reviews within 2-3 business days
- Comments added to document
- Questions clarified
- Red flags escalated

### Negotiation
- Legal leads red line negotiations
- Business owner participates
- Round tracking maintained
- Approval obtained for concessions

### Execution
- Final version approved
- Signature routing (DocuSign)
- Fully executed copy saved
- Repository updated

### Post-Execution
- Key dates calendared
- Obligations tracked
- Renewal process initiated
- Termination rights monitored

## Contract Repository

### Location
- Primary: Ironclad contract management
- Backup: Shared drive (organized by type)

### Organization
```
Contracts/
├── Customers/
│   ├── Active/
│   └── Expired/
├── Vendors/
│   ├── Active/
│   └── Expired/
├── Employment/
├── NDAs/
└── Templates/
```

### Metadata Tracked
- Counterparty name
- Contract type
- Effective date
- Expiration date
- Renewal terms
- Value
- Key contacts
- Auto-renew flag

## Key Clauses Reference

### Liability
- Mutual limitation to fees paid in last 12 months
- Carve-outs for IP, confidentiality, gross negligence

### Indemnification
- We indemnify: IP infringement, our negligence
- Customer indemnifies: Their data, their negligence

### Termination
- Either party: Convenience with notice (30-90 days)
- For cause: Material breach, uncured
- Data return/retention on exit

### Governing Law
- Preferred: Delaware or New York
- Alternative: Customer's state (if reasonable)

## Training Resources
- Contract basics webinar
- Negotiation skills workshop
- Approval process guide
- Red flag identification guide
