# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of Gmail Cleaner seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### Please Do NOT:

- Open a public GitHub issue for security vulnerabilities
- Disclose the vulnerability publicly before it has been addressed

### Please DO:

1. **Email us directly** at [your-email@example.com] with:
   - A description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact
   - Any suggested fixes (if available)

2. **Allow us time to respond**: We will acknowledge receipt within 48 hours and provide a more detailed response within 7 days.

3. **Work with us**: We may ask for additional information or guidance.

## Security Measures

Gmail Cleaner implements several security measures:

### Authentication
- **OAuth 2.0**: Secure authentication via Google's OAuth 2.0 flow
- **Local credentials**: All credentials stored locally, never transmitted to external servers
- **Token management**: Secure token storage with automatic refresh

### Data Privacy
- **No external services**: No data sent to external analytics or tracking services
- **Local processing**: All email processing happens locally or via Gmail API
- **User control**: Users explicitly select what to delete
- **Trash only**: Emails moved to trash, not permanently deleted

### Application Security
- **Input validation**: All user inputs validated and sanitized
- **CORS protection**: Proper CORS configuration for API endpoints
- **WebSocket security**: Authenticated WebSocket connections
- **Protected emails**: Automatic protection of important/starred/labeled emails

### Infrastructure
- **Docker isolation**: Containerized deployment for isolation
- **Minimal permissions**: Gmail API scopes limited to necessary permissions only
- **No persistence**: No database or persistent storage of email content

## Security Best Practices for Users

When using Gmail Cleaner:

1. **Download from official sources**: Only download from the official GitHub repository
2. **Verify credentials**: Ensure OAuth credentials are from your own Google Cloud Console
3. **Use preview mode**: Always preview deletions before executing
4. **Review selections**: Carefully review domain selections before cleanup
5. **Keep updated**: Use the latest version for security patches
6. **Monitor OAuth apps**: Regularly review authorized apps in your Google Account
7. **Secure your machine**: Keep your local machine secure as credentials are stored locally

## OAuth 2.0 Security

Gmail Cleaner uses OAuth 2.0 for authentication:

- **Scopes**: Only requests `gmail.modify` scope (minimum required)
- **Consent screen**: Clear disclosure of what access is requested
- **Token storage**: Tokens stored locally with file permissions
- **Token refresh**: Automatic token refresh without re-authentication
- **Revocation**: Users can revoke access anytime via Google Account settings

## Known Limitations

- Credentials stored in plaintext on local filesystem (protected by file permissions)
- No encryption at rest for local token storage
- Requires user to manage Google Cloud Console credentials

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine affected versions
2. Audit code to find similar problems
3. Prepare fixes for all supported versions
4. Release security patches as soon as possible
5. Publish a security advisory on GitHub

## Comments on this Policy

If you have suggestions on how this policy could be improved, please submit a pull request or open an issue.

---

**Last updated**: January 2025
