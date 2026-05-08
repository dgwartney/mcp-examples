# Security Considerations

## API Key Management

- **Never commit** `api_keys.db` to version control (already in `.gitignore`)
- **Rotate keys regularly** in production environments
- **Use environment variables** for sensitive configuration in production
- **Implement rate limiting** for production deployments
- **Use HTTPS** for all production traffic (ngrok and all cloud platforms provide this automatically)

## Database Security

- The SQLite database uses parameterized queries to prevent SQL injection
- Keys are stored as plain text — for high-security applications, consider hashing keys before storage
- Ensure proper file permissions on `api_keys.db` (readable only by the server process)

## Header Handling

- The server implements case-insensitive header matching per RFC 7230
- All variations of `X-API-Key` header casing are supported
