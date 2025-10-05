# TLS and Mutual TLS (mTLS)

RestMachine supports TLS/SSL and mutual TLS authentication for secure communications. This guide covers TLS setup with ASGI servers, AWS integration, and client certificate authentication.

## TLS with ASGI Servers

### Uvicorn with TLS

Run Uvicorn with TLS certificates:

```bash
# Generate self-signed certificates for development
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout key.pem -out cert.pem -days 365 \
  -subj "/CN=localhost"

# Run with TLS
uvicorn app:asgi_app \
  --host 0.0.0.0 \
  --port 8443 \
  --ssl-keyfile key.pem \
  --ssl-certfile cert.pem
```

Production configuration:

```bash
# With Let's Encrypt certificates
uvicorn app:asgi_app \
  --host 0.0.0.0 \
  --port 443 \
  --ssl-keyfile /etc/letsencrypt/live/example.com/privkey.pem \
  --ssl-certfile /etc/letsencrypt/live/example.com/fullchain.pem \
  --workers 4
```

### Hypercorn with TLS

Run Hypercorn with TLS support:

```bash
# Basic TLS
hypercorn app:asgi_app \
  --bind 0.0.0.0:8443 \
  --certfile cert.pem \
  --keyfile key.pem

# Production with HTTP/2
hypercorn app:asgi_app \
  --bind 0.0.0.0:443 \
  --certfile /etc/letsencrypt/live/example.com/fullchain.pem \
  --keyfile /etc/letsencrypt/live/example.com/privkey.pem \
  --workers 4 \
  --worker-class uvloop
```

### Hypercorn Configuration File

Use a configuration file for advanced settings:

```toml
# hypercorn_config.toml
bind = ["0.0.0.0:443"]
certfile = "/etc/letsencrypt/live/example.com/fullchain.pem"
keyfile = "/etc/letsencrypt/live/example.com/privkey.pem"
workers = 4
worker_class = "uvloop"
accesslog = "-"
errorlog = "-"
```

Run with config:

```bash
hypercorn app:asgi_app -c hypercorn_config.toml
```

## Mutual TLS (mTLS)

### Client Certificate Authentication

Enable client certificate verification:

#### Uvicorn with mTLS

```bash
# Run with client certificate verification
uvicorn app:asgi_app \
  --host 0.0.0.0 \
  --port 8443 \
  --ssl-keyfile server-key.pem \
  --ssl-certfile server-cert.pem \
  --ssl-ca-certs ca-cert.pem \
  --ssl-cert-reqs 2  # CERT_REQUIRED
```

#### Hypercorn with mTLS

```toml
# hypercorn_mtls_config.toml
bind = ["0.0.0.0:8443"]
certfile = "server-cert.pem"
keyfile = "server-key.pem"
ca_certs = "ca-cert.pem"
verify_mode = "CERT_REQUIRED"
```

### Accessing Client Certificate

RestMachine provides client certificate information through the TLS extension:

```python
from restmachine import RestApplication, Request
from restmachine.extensions.tls import TLSExtension

app = RestApplication()

# Enable TLS extension
app.add_extension(TLSExtension())

@app.dependency()
def client_cert(request: Request):
    """Extract client certificate from request."""
    tls = request.extensions.get('tls')

    if not tls:
        raise ValueError("TLS information not available")

    client_cert = tls.get('client_cert')

    if not client_cert:
        raise ValueError("Client certificate required")

    return client_cert

@app.dependency()
def authenticated_user(client_cert):
    """Extract user identity from certificate."""
    subject = client_cert.get('subject', {})

    # Extract Common Name (CN)
    cn = None
    for rdn in subject.get('rdnSequence', []):
        for attr in rdn:
            if attr.get('type') == 'commonName':
                cn = attr.get('value')
                break

    if not cn:
        raise ValueError("Certificate missing Common Name")

    return {
        'id': cn,
        'cert_serial': client_cert.get('serialNumber'),
        'cert_issuer': client_cert.get('issuer')
    }

@app.get('/api/secure')
def secure_endpoint(authenticated_user):
    """Endpoint requiring client certificate."""
    return {
        "message": f"Hello, {authenticated_user['id']}",
        "cert_serial": authenticated_user['cert_serial']
    }
```

### Certificate Validation

Implement custom certificate validation:

```python
from datetime import datetime

@app.dependency()
def validate_client_cert(client_cert):
    """Validate client certificate."""
    # Check expiration
    not_after = client_cert.get('notAfter')
    if not_after:
        expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
        if expiry < datetime.now():
            raise ValueError("Certificate expired")

    # Check issuer
    issuer = client_cert.get('issuer', {})
    org = None
    for rdn in issuer.get('rdnSequence', []):
        for attr in rdn:
            if attr.get('type') == 'organizationName':
                org = attr.get('value')
                break

    if org != 'Trusted CA Inc':
        raise ValueError("Certificate from untrusted CA")

    return client_cert

@app.get('/api/validated')
def validated_endpoint(validate_client_cert):
    """Endpoint with certificate validation."""
    subject = validate_client_cert.get('subject', {})
    return {"status": "authenticated", "subject": subject}
```

## AWS Integration

### Application Load Balancer (ALB) with TLS

ALB terminates TLS and forwards requests to RestMachine:

```python
from restmachine import RestApplication, Request

app = RestApplication()

@app.dependency()
def client_cert_from_alb(request: Request):
    """Extract client certificate from ALB headers."""
    # ALB adds client cert to X-Amzn-Mtls-Clientcert header
    cert_header = request.headers.get('x-amzn-mtls-clientcert')

    if not cert_header:
        raise ValueError("Client certificate required")

    # Decode URL-encoded certificate
    import urllib.parse
    cert_pem = urllib.parse.unquote(cert_header)

    # Parse certificate
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend

    cert = x509.load_pem_x509_certificate(
        cert_pem.encode(),
        default_backend()
    )

    return {
        'subject': cert.subject.rfc4514_string(),
        'issuer': cert.issuer.rfc4514_string(),
        'serial': str(cert.serial_number),
        'not_before': cert.not_valid_before.isoformat(),
        'not_after': cert.not_valid_after.isoformat()
    }

@app.dependency()
def authenticated_user_alb(client_cert_from_alb):
    """Get user from ALB client certificate."""
    # Extract CN from subject
    subject = client_cert_from_alb['subject']
    cn = None

    for part in subject.split(','):
        if part.strip().startswith('CN='):
            cn = part.strip()[3:]
            break

    if not cn:
        raise ValueError("Certificate missing CN")

    return {'id': cn, 'cert': client_cert_from_alb}

@app.get('/api/alb-secure')
def alb_secure_endpoint(authenticated_user_alb):
    """Endpoint with ALB mTLS."""
    return {
        "message": f"Hello from ALB, {authenticated_user_alb['id']}",
        "cert_info": authenticated_user_alb['cert']
    }
```

#### ALB Configuration

Configure ALB for mTLS:

```yaml
# CloudFormation/Terraform example
Listener:
  Port: 443
  Protocol: HTTPS
  Certificates:
    - CertificateArn: arn:aws:acm:region:account:certificate/id
  MutualAuthentication:
    Mode: verify  # or 'passthrough'
    TrustStoreArn: arn:aws:elasticloadbalancing:region:account:truststore/name/id
  DefaultActions:
    - Type: forward
      TargetGroupArn: !Ref TargetGroup
```

### API Gateway with TLS

API Gateway with mutual TLS:

```python
from restmachine import RestApplication, Request

app = RestApplication()

@app.dependency()
def client_cert_from_apigw(request: Request):
    """Extract client certificate from API Gateway."""
    # API Gateway adds certificate info to request context
    # Accessed via APIGW-specific event structure

    # For RestMachine with API Gateway, certificate info
    # is in the request context
    context = getattr(request, 'request_context', {})

    identity = context.get('identity', {})
    cert_info = identity.get('clientCert', {})

    if not cert_info:
        raise ValueError("Client certificate required")

    return {
        'subject_dn': cert_info.get('subjectDN'),
        'issuer_dn': cert_info.get('issuerDN'),
        'serial': cert_info.get('serialNumber'),
        'validity': {
            'not_before': cert_info.get('validity', {}).get('notBefore'),
            'not_after': cert_info.get('validity', {}).get('notAfter')
        }
    }

@app.dependency()
def authenticated_user_apigw(client_cert_from_apigw):
    """Get user from API Gateway client certificate."""
    subject_dn = client_cert_from_apigw['subject_dn']

    # Parse subject DN (e.g., "CN=user,OU=dept,O=org")
    cn = None
    for part in subject_dn.split(','):
        if part.strip().startswith('CN='):
            cn = part.strip()[3:]
            break

    if not cn:
        raise ValueError("Certificate missing CN")

    return {'id': cn, 'cert': client_cert_from_apigw}

@app.get('/api/apigw-secure')
def apigw_secure_endpoint(authenticated_user_apigw):
    """Endpoint with API Gateway mTLS."""
    return {
        "message": f"Hello from API Gateway, {authenticated_user_apigw['id']}",
        "cert_info": authenticated_user_apigw['cert']
    }

# For AWS Lambda with API Gateway
from restmachine_aws import AwsApiGatewayAdapter

adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

#### API Gateway Configuration

Configure API Gateway for mTLS:

```yaml
# API Gateway REST API with mTLS
DomainName:
  DomainName: api.example.com
  MutualTlsAuthentication:
    TruststoreUri: s3://bucket-name/truststore.pem
    TruststoreVersion: version-id
  RegionalCertificateArn: arn:aws:acm:region:account:certificate/id

BasePathMapping:
  DomainName: !Ref DomainName
  RestApiId: !Ref RestApi
  Stage: prod
```

## Certificate-Based Authorization

### Role-Based Access from Certificates

Map certificate attributes to roles:

```python
from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    SERVICE = "service"

# Certificate OU to Role mapping
OU_TO_ROLE = {
    'Administrators': Role.ADMIN,
    'Users': Role.USER,
    'Services': Role.SERVICE
}

@app.dependency()
def user_role(client_cert):
    """Extract role from certificate OU."""
    subject = client_cert.get('subject', {})

    # Find OU (Organizational Unit)
    ou = None
    for rdn in subject.get('rdnSequence', []):
        for attr in rdn:
            if attr.get('type') == 'organizationalUnitName':
                ou = attr.get('value')
                break

    if not ou:
        return Role.USER  # Default role

    return OU_TO_ROLE.get(ou, Role.USER)

@app.dependency()
def require_admin_cert(user_role: Role):
    """Require admin certificate."""
    if user_role != Role.ADMIN:
        raise PermissionError(f"Admin certificate required, got: {user_role}")
    return True

@app.get('/admin/users')
def admin_endpoint(require_admin_cert, authenticated_user):
    """Admin-only endpoint requiring admin certificate."""
    return {
        "message": "Admin access granted",
        "user": authenticated_user['id']
    }
```

### Certificate Pinning

Validate specific certificate fingerprints:

```python
import hashlib

# Allowed certificate fingerprints (SHA-256)
ALLOWED_CERT_FINGERPRINTS = {
    'aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99',
    '11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee:ff'
}

@app.dependency()
def pinned_certificate(client_cert):
    """Validate certificate against pinned fingerprints."""
    # Get DER-encoded certificate
    der = client_cert.get('der')

    if not der:
        raise ValueError("Certificate DER encoding not available")

    # Calculate SHA-256 fingerprint
    fingerprint = hashlib.sha256(der).hexdigest()
    fingerprint_formatted = ':'.join(
        fingerprint[i:i+2] for i in range(0, len(fingerprint), 2)
    )

    if fingerprint_formatted not in ALLOWED_CERT_FINGERPRINTS:
        raise ValueError("Certificate not in allowed list")

    return client_cert

@app.get('/api/pinned')
def pinned_endpoint(pinned_certificate, authenticated_user):
    """Endpoint requiring pinned certificate."""
    return {
        "message": "Certificate pinning successful",
        "user": authenticated_user['id']
    }
```

## Complete Examples

### Full mTLS Application

```python
from restmachine import RestApplication, Request
from restmachine.extensions.tls import TLSExtension
from datetime import datetime
from typing import Dict, Any
import logging

app = RestApplication()

# Enable TLS extension
app.add_extension(TLSExtension())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Certificate validation
@app.dependency()
def client_cert(request: Request) -> Dict[str, Any]:
    """Extract and validate client certificate."""
    tls = request.extensions.get('tls')

    if not tls:
        raise ValueError("TLS not enabled")

    cert = tls.get('client_cert')

    if not cert:
        raise ValueError("Client certificate required")

    # Validate expiration
    not_after = cert.get('notAfter')
    if not_after:
        try:
            expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
            if expiry < datetime.now():
                raise ValueError("Certificate expired")
        except ValueError as e:
            logger.warning(f"Could not parse certificate expiry: {e}")

    return cert

@app.dependency()
def authenticated_user(client_cert: Dict[str, Any]) -> Dict[str, Any]:
    """Extract user from certificate."""
    subject = client_cert.get('subject', {})

    # Extract attributes
    cn = None
    email = None
    ou = None

    for rdn in subject.get('rdnSequence', []):
        for attr in rdn:
            attr_type = attr.get('type')
            if attr_type == 'commonName':
                cn = attr.get('value')
            elif attr_type == 'emailAddress':
                email = attr.get('value')
            elif attr_type == 'organizationalUnitName':
                ou = attr.get('value')

    if not cn:
        raise ValueError("Certificate missing Common Name")

    user = {
        'id': cn,
        'email': email,
        'department': ou,
        'cert_serial': client_cert.get('serialNumber')
    }

    logger.info(f"User authenticated via mTLS: {cn}")

    return user

# Role-based access
@app.dependency()
def user_role(authenticated_user: Dict[str, Any]) -> str:
    """Determine user role from department."""
    dept = authenticated_user.get('department', '')

    if dept == 'Administrators':
        return 'admin'
    elif dept == 'Services':
        return 'service'
    else:
        return 'user'

@app.dependency()
def require_admin(user_role: str):
    """Require admin role."""
    if user_role != 'admin':
        raise PermissionError("Admin access required")
    return True

# Routes
@app.get('/api/profile')
def get_profile(authenticated_user: Dict[str, Any]):
    """Get user profile from certificate."""
    return {
        "user": authenticated_user,
        "authenticated_via": "mTLS"
    }

@app.get('/api/admin/status')
def admin_status(require_admin, authenticated_user: Dict[str, Any]):
    """Admin endpoint requiring admin certificate."""
    return {
        "status": "OK",
        "admin": authenticated_user['id'],
        "timestamp": datetime.now().isoformat()
    }

@app.get('/api/cert-info')
def cert_info(client_cert: Dict[str, Any]):
    """Get detailed certificate information."""
    return {
        "subject": client_cert.get('subject'),
        "issuer": client_cert.get('issuer'),
        "serial": client_cert.get('serialNumber'),
        "validity": {
            "not_before": client_cert.get('notBefore'),
            "not_after": client_cert.get('notAfter')
        }
    }

# Error handlers
@app.error_handler(401)
def unauthorized(request, message, **kwargs):
    logger.warning(f"Unauthorized access attempt: {message}")
    return {
        "error": "Unauthorized",
        "message": message,
        "hint": "Valid client certificate required"
    }

@app.error_handler(403)
def forbidden(request, message, **kwargs):
    logger.warning(f"Forbidden access attempt: {message}")
    return {
        "error": "Forbidden",
        "message": message
    }

# ASGI
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)

if __name__ == '__main__':
    # Run with uvicorn
    # uvicorn app:asgi_app --host 0.0.0.0 --port 8443 \
    #   --ssl-keyfile server-key.pem \
    #   --ssl-certfile server-cert.pem \
    #   --ssl-ca-certs ca-cert.pem \
    #   --ssl-cert-reqs 2
    pass
```

### AWS ALB mTLS Example

```python
from restmachine import RestApplication, Request
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import urllib.parse
import logging

app = RestApplication()
logger = logging.getLogger(__name__)

@app.dependency()
def alb_client_cert(request: Request):
    """Extract client certificate from ALB."""
    cert_header = request.headers.get('x-amzn-mtls-clientcert')

    if not cert_header:
        raise ValueError("Client certificate required")

    # Decode URL-encoded certificate
    cert_pem = urllib.parse.unquote(cert_header)

    # Parse certificate
    cert = x509.load_pem_x509_certificate(
        cert_pem.encode(),
        default_backend()
    )

    return {
        'subject': cert.subject.rfc4514_string(),
        'issuer': cert.issuer.rfc4514_string(),
        'serial': str(cert.serial_number),
        'not_before': cert.not_valid_before,
        'not_after': cert.not_valid_after,
        'raw_cert': cert
    }

@app.dependency()
def validate_alb_cert(alb_client_cert):
    """Validate ALB client certificate."""
    from datetime import datetime, timezone

    # Check expiration
    now = datetime.now(timezone.utc)
    if alb_client_cert['not_after'] < now:
        raise ValueError("Certificate expired")

    if alb_client_cert['not_before'] > now:
        raise ValueError("Certificate not yet valid")

    # Extract CN
    subject = alb_client_cert['subject']
    cn = None
    for part in subject.split(','):
        if part.strip().startswith('CN='):
            cn = part.strip()[3:]
            break

    if not cn:
        raise ValueError("Certificate missing CN")

    return {'id': cn, 'cert': alb_client_cert}

@app.get('/api/alb-mtls')
def alb_mtls_endpoint(validate_alb_cert):
    """ALB mTLS endpoint."""
    return {
        "message": f"Authenticated via ALB mTLS",
        "user": validate_alb_cert['id'],
        "cert_serial": validate_alb_cert['cert']['serial']
    }

# ASGI for ALB
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

## Testing mTLS Locally

### Generate Test Certificates

```bash
#!/bin/bash
# generate-mtls-certs.sh

# Create CA
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout ca-key.pem -out ca-cert.pem -days 365 \
  -subj "/CN=Test CA"

# Create server certificate
openssl req -newkey rsa:4096 -nodes \
  -keyout server-key.pem -out server-req.pem \
  -subj "/CN=localhost"

openssl x509 -req -in server-req.pem -days 365 \
  -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
  -out server-cert.pem

# Create client certificate (admin)
openssl req -newkey rsa:4096 -nodes \
  -keyout client-admin-key.pem -out client-admin-req.pem \
  -subj "/CN=admin/OU=Administrators/emailAddress=admin@example.com"

openssl x509 -req -in client-admin-req.pem -days 365 \
  -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
  -out client-admin-cert.pem

# Create client certificate (user)
openssl req -newkey rsa:4096 -nodes \
  -keyout client-user-key.pem -out client-user-req.pem \
  -subj "/CN=user1/OU=Users/emailAddress=user1@example.com"

openssl x509 -req -in client-user-req.pem -days 365 \
  -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
  -out client-user-cert.pem

echo "Certificates generated successfully"
```

### Test with cURL

```bash
# Test with admin certificate
curl https://localhost:8443/api/profile \
  --cert client-admin-cert.pem \
  --key client-admin-key.pem \
  --cacert ca-cert.pem

# Test admin endpoint
curl https://localhost:8443/api/admin/status \
  --cert client-admin-cert.pem \
  --key client-admin-key.pem \
  --cacert ca-cert.pem

# Test with user certificate (should fail for admin endpoint)
curl https://localhost:8443/api/admin/status \
  --cert client-user-cert.pem \
  --key client-user-key.pem \
  --cacert ca-cert.pem

# Test without certificate (should fail)
curl https://localhost:8443/api/profile \
  --cacert ca-cert.pem
```

## Best Practices

### 1. Always Validate Certificate Expiration

```python
@app.dependency()
def validate_cert_expiry(client_cert):
    from datetime import datetime

    not_after = client_cert.get('notAfter')
    if not_after:
        expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
        if expiry < datetime.now():
            raise ValueError("Certificate expired")

    return client_cert
```

### 2. Use Certificate Revocation Lists (CRL)

```python
@app.dependency()
def check_revocation(client_cert):
    """Check if certificate is revoked."""
    serial = client_cert.get('serialNumber')

    # Check against CRL or OCSP
    if is_revoked(serial):
        raise ValueError("Certificate has been revoked")

    return client_cert
```

### 3. Log Certificate Usage

```python
@app.dependency()
def log_cert_usage(authenticated_user, request: Request):
    """Log certificate usage for audit."""
    logger.info(
        "Certificate authentication",
        extra={
            'user': authenticated_user['id'],
            'path': request.path,
            'cert_serial': authenticated_user.get('cert_serial'),
            'timestamp': datetime.now().isoformat()
        }
    )
    return authenticated_user
```

### 4. Use Strong Cipher Suites

```bash
# Uvicorn with strong ciphers
uvicorn app:asgi_app \
  --ssl-ciphers "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
```

### 5. Implement Certificate Rotation

```python
@app.dependency()
def check_cert_age(client_cert):
    """Warn if certificate is old."""
    from datetime import datetime, timedelta

    not_after = client_cert.get('notAfter')
    if not_after:
        expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
        days_until_expiry = (expiry - datetime.now()).days

        if days_until_expiry < 30:
            logger.warning(
                f"Certificate expires in {days_until_expiry} days. "
                f"Serial: {client_cert.get('serialNumber')}"
            )

    return client_cert
```

## Next Steps

- [Authentication →](../guide/authentication.md) - Combine with other auth methods
- [Error Handling →](../guide/error-handling.md) - Handle certificate errors
- [Deployment →](../guide/deployment/aws-lambda.md) - Deploy with mTLS
- [Testing →](../guide/testing.md) - Test mTLS endpoints
