# Security Configuration Guide

## Current Status (Development)

✅ **Application is running with security features enabled:**
- Request ID tracking
- Activity logging
- XSS protection
- Encrypted sessions (Fernet AES-128)
- Session fingerprinting
- Input body size limiting (5MB)
- CORS configured for localhost

⚠️ **Development-only settings (not production-ready):**
- HTTP allowed on localhost (no HTTPS requirement)
- CSRF protection disabled (for faster development)
- Security headers disabled

---

## Gradual Security Enablement

You can gradually enable stricter security features by modifying `.env` file settings:

### Step 1: Enable CSRF Protection
```dotenv
CSRF_ENABLED="true"
```
**Effect:** All form submissions must include valid CSRF tokens
**Recommendation:** Enable when you've verified all forms have CSRF tokens

### Step 2: Enable Security Headers
```dotenv
HSTS_ENABLED="true"
```
**Effect:** Adds HSTS, CSP, X-Frame-Options, X-Content-Type-Options headers
**Recommendation:** Enable in staging environment first to test

### Step 3: Enable HTTPS (Localhost)
```dotenv
FORCE_HTTPS="true"
```
**Effect:** All HTTP requests redirect to HTTPS
**Note:** For localhost development, you can still access via HTTPS with self-signed certificates

**To test locally with HTTPS:**
```bash
# Generate self-signed certificate (Windows PowerShell):
$cert = New-SelfSignedCertificate -certstorelocation cert:\currentuser\my -dnsname localhost, 127.0.0.1
Export-PfxCertificate -cert $cert -FilePath cert.pfx -Password (ConvertTo-SecureString -String "password" -AsPlainText -Force)

# Update .env:
TLS_CERT_FILE="C:\path\to\cert.pem"
TLS_KEY_FILE="C:\path\to\key.pem"

# Run with TLS:
python Security/run_tls.py
```

### Step 4: Full Production Mode
```dotenv
FORCE_HTTPS="true"
ALLOW_INSECURE_LOCALHOST="false"
CSRF_ENABLED="true"
HSTS_ENABLED="true"
SESSION_HTTPS_ONLY="true"
```

---

## Environment Variables Reference

| Variable | Default | Dev | Prod | Purpose |
|----------|---------|-----|------|---------|
| `FORCE_HTTPS` | false | false | true | Redirect HTTP to HTTPS |
| `ALLOW_INSECURE_LOCALHOST` | true | true | false | Allow unencrypted localhost access |
| `CSRF_ENABLED` | false | false | true | Enforce CSRF token validation |
| `HSTS_ENABLED` | false | false | true | Enable security headers |
| `SESSION_HTTPS_ONLY` | false | false | true | Restrict sessions to HTTPS |
| `SESSION_MAX_AGE` | 600 | 600 | 3600 | Session timeout (seconds) |
| `SESSION_IDLE_TIMEOUT` | 600 | 600 | 1800 | Idle timeout (seconds) |
| `SESSION_FINGERPRINT` | true | true | true | Validate session fingerprint |
| `MAX_BODY_BYTES` | 5242880 | 5MB | 5MB | Max request body size |
| `CORS_ORIGINS` | localhost | - | - | Allowed CORS origins |

---

## Recommended Configurations

### Development (.env)
```dotenv
FORCE_HTTPS="false"
ALLOW_INSECURE_LOCALHOST="true"
CSRF_ENABLED="false"
HSTS_ENABLED="false"
SESSION_HTTPS_ONLY="false"
```
**Benefits:** Fast development, minimal restrictions

### Staging (.env)
```dotenv
FORCE_HTTPS="true"
ALLOW_INSECURE_LOCALHOST="false"
CSRF_ENABLED="true"
HSTS_ENABLED="true"
SESSION_HTTPS_ONLY="true"
```
**Benefits:** Tests production security, catches issues before deployment

### Production (.env)
```dotenv
FORCE_HTTPS="true"
ALLOW_INSECURE_LOCALHOST="false"
CSRF_ENABLED="true"
HSTS_ENABLED="true"
SESSION_HTTPS_ONLY="true"
SESSION_MAX_AGE="3600"
SESSION_IDLE_TIMEOUT="1800"
```
**Benefits:** Maximum security, industry best practices

---

## Security Features Activated

### Always Active (All Environments)
✅ Request ID tracking - Track each request
✅ Activity logging - Log all access to `logs/security.log`
✅ XSS protection headers - Prevent cross-site scripting
✅ Encrypted sessions - Fernet AES-128 encryption
✅ Session fingerprinting - Detect session hijacking
✅ Input validation - Body size limiting
✅ CORS protection - Control cross-origin access
✅ Audit trail - Log security events to `logs/audit.log`

### Conditional (Based on .env settings)
🔒 CSRF protection - Requires `CSRF_ENABLED="true"`
🔒 Security headers - Requires `HSTS_ENABLED="true"`
🔒 HTTPS redirect - Requires `FORCE_HTTPS="true"`
🔒 Session HTTPS-only - Requires `SESSION_HTTPS_ONLY="true"`

---

## Testing Security Features

### 1. Verify Activity Logging
```bash
tail logs/security.log
```
Expected output: Each request logged with method, path, user_id, request_id

### 2. Verify Audit Trail
```bash
tail logs/audit.log
```
Expected output: Security events (login, logout, role changes, etc.)

### 3. Verify Session Encryption
1. Login to application
2. Open browser DevTools → Application → Cookies
3. Check `session` cookie - should be encrypted blob
4. Verify expiration time matches `SESSION_MAX_AGE`

### 4. Test CSRF Protection (when enabled)
1. Set `CSRF_ENABLED="true"` in .env
2. Try submitting a form without CSRF token
3. Expected: 403 Forbidden error

### 5. Test HTTPS Redirect (when enabled)
1. Set `FORCE_HTTPS="true"` in .env
2. Access http://localhost:8000
3. Expected: Redirect to https://localhost:443 (with certificate warning on localhost)

---

## Troubleshooting

### Issue: "CSRF token missing" error
**Solution:** 
- Check if `CSRF_ENABLED="true"` in .env
- Verify all forms have `csrf_token` field
- Temporarily set `CSRF_ENABLED="false"` to test

### Issue: "Session middleware not found" error
**Solution:**
- Verify `SESSION_SECRET_KEY` in .env is set
- Restart application: `Ctrl+C` then `uvicorn main:app --reload`

### Issue: HTTPS localhost certificate warning
**Solution:**
- This is normal for self-signed certificates
- For development only - ignore warning and click "Proceed"
- For production - use valid certificate from Certificate Authority

### Issue: Page loads slowly
**Solution:**
- Check if CSRF middleware is enabled (`CSRF_ENABLED="true"`)
- Disable temporarily and test: `CSRF_ENABLED="false"`
- Check logs for middleware errors

---

## Production Deployment Checklist

- [ ] Set `FORCE_HTTPS="true"`
- [ ] Set `ALLOW_INSECURE_LOCALHOST="false"`
- [ ] Set `CSRF_ENABLED="true"`
- [ ] Set `HSTS_ENABLED="true"`
- [ ] Set `SESSION_HTTPS_ONLY="true"`
- [ ] Configure valid TLS certificates (not self-signed)
- [ ] Update `CORS_ORIGINS` with your production domain
- [ ] Increase `SESSION_MAX_AGE` to appropriate value (e.g., 3600)
- [ ] Review `logs/security.log` and `logs/audit.log`
- [ ] Test login/logout flow
- [ ] Test CSRF protection on all forms
- [ ] Verify HTTPS redirect works
- [ ] Enable security headers testing in browser

---

## Support

All security features are integrated from the 54 security modules in the `Security/` folder.
To understand specific features, check the corresponding module:

- Sessions: `Security/session_security.py`
- CSRF: `Security/csrf_protection.py`
- Headers: `Security/headers_hardening.py`
- Encryption: `Security/data_encryption_at_rest.py`
- Logging: `Security/activity_logging.py`, `Security/audit_trail.py`
