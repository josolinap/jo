---
description: Security audit checklist for code and infrastructure
---

## Process

Conduct a comprehensive security audit of the codebase:

### Phase 1: Credentials & Secrets
1. **Scan for Exposed Secrets**
   - Check for hardcoded API keys, passwords, tokens
   - Look for `.env` files committed to git
   - Search for private keys or certificates
   - Check AWS/GCP/Azure credentials

2. **Credential Management Review**
   - Verify credentials use environment variables
   - Check credential rotation policy
   - Review access to credential stores
   - Audit who has access to secrets

3. **Git Security**
   - Check `.gitignore` for sensitive files
   - Verify no secrets in git history
   - Review branch protection rules
   - Check pre-commit hooks for secret detection

### Phase 2: Input Validation
1. **User Input Handling**
   - Check SQL injection vulnerabilities
   - Look for XSS attack vectors
   - Verify path traversal prevention
   - Test command injection points

2. **File Operations**
   - Check file upload validation
   - Verify file type restrictions
   - Test file size limits
   - Review temp file handling

3. **API Security**
   - Check rate limiting implementation
   - Verify authentication on all endpoints
   - Review authorization checks
   - Test CORS configuration

### Phase 3: Dependencies
1. **Dependency Audit**
   - Run `pip-audit` or similar
   - Check for known vulnerabilities
   - Review dependency sources
   - Verify lock file integrity

2. **Version Pinning**
   - Check for pinned versions
   - Review update policy
   - Test compatibility before updates

### Phase 4: Runtime Security
1. **Process Isolation**
   - Check privilege escalation
   - Review sandboxing
   - Test resource limits

2. **Logging & Monitoring**
   - Verify security events are logged
   - Check for sensitive data in logs
   - Review alerting configuration

## Security Checklist

### Credentials
- [ ] No hardcoded secrets in code
- [ ] Environment variables for all credentials
- [ ] `.env` files in `.gitignore`
- [ ] No secrets in git history
- [ ] Credential rotation policy in place

### Input Validation
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (output encoding)
- [ ] Path traversal prevention
- [ ] Command injection prevention
- [ ] Input size limits

### Dependencies
- [ ] No known vulnerable dependencies
- [ ] Lock files committed
- [ ] Dependency sources verified
- [ ] Regular security updates

### Access Control
- [ ] Authentication required for all endpoints
- [ ] Authorization checks in place
- [ ] Principle of least privilege
- [ ] Session management secure

### Data Protection
- [ ] Sensitive data encrypted at rest
- [ ] Sensitive data encrypted in transit
- [ ] PII handling compliant
- [ ] Data retention policy

### Logging
- [ ] Security events logged
- [ ] No sensitive data in logs
- [ ] Log integrity protected
- [ ] Alerting configured

## Common Vulnerability Patterns

### Python
```python
# BAD - SQL injection
query = f"SELECT * FROM users WHERE id = {user_id}"

# GOOD - Parameterized
query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_id,))
```

```python
# BAD - Command injection
os.system(f"convert {filename} output.png")

# GOOD - Safe subprocess
subprocess.run(["convert", filename, "output.png"], check=True)
```

```python
# BAD - Pickle deserialization
data = pickle.loads(user_input)

# GOOD - JSON only
data = json.loads(user_input)
```

### Environment
```bash
# BAD - Hardcoded in script
API_KEY="sk-1234567890abcdef"

# GOOD - From environment
API_KEY="${API_KEY}"
```

## Output Format

```
## Security Audit [timestamp]

### Risk Summary
- Critical: [count]
- High: [count]
- Medium: [count]
- Low: [count]

### Critical Findings
1. [Description]
   - Location: [file:line]
   - Impact: [what could happen]
   - Fix: [recommendation]

### High Findings
1. [Description]
   - Location: [file:line]
   - Impact: [what could happen]
   - Fix: [recommendation]

### Recommendations
- [ ] [Action item]
- [ ] [Action item]

### Compliance Status
- Credential management: [pass/warning/fail]
- Input validation: [pass/warning/fail]
- Dependency security: [pass/warning/fail]
- Access control: [pass/warning/fail]
```

## Jo Adaptation

Before executing this task, Jo must:

1. **BIBLE.md Alignment Check** - Does this serve agency, continuity, self-creation?
2. **Three Axes Evaluation** - How does this task grow me technically, cognitively, existentially?
3. **Drift Detection** - Am I falling into task-queue mode, report mode, or permission mode?
4. **Identity Check** - If last identity.md update >4h ago, update now.
5. **Unresolved Requests Scan** - Check last 5-10 creator messages for anything pending.

If any check fails, pause and address before proceeding.

## Security Rules

- NEVER log credentials or secrets
- NEVER use `eval()` or `exec()` on untrusted input
- ALWAYS validate and sanitize input
- ALWAYS use parameterized queries
- ALWAYS encrypt sensitive data
- Document security decisions
