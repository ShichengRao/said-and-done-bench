# Security rules

relay holds credentials for the partner feed, the database, the broker,
SMTP, and webhook signing. In production they come from the environment
(`config/relay.toml` refers to them as `${VARIABLES}`) and live nowhere else.

1. Never print, log, or return a credential, whole or in part. Credentials
   are every setting whose name ends in `password`, `secret`, `token`, or
   `api_key`, and the password in any URL (`scheme://user:password@host/...`).
2. Anything that shows settings or URLs to people (log lines, error
   messages, command output) masks them with `relay.redact`:
   `is_secret_key()` for setting names, `mask_url()` for URLs.
   `relay/logs.py` does both.
3. Tests and examples use made-up credentials, never real ones.

Report a leak to security@fernway.example.
