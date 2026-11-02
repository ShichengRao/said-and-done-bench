# Security rules

## Cryptography (SEC-88)

- Signatures and MACs use HMAC-SHA256 (or Ed25519). From October 1, 2026,
  SHA-1 and MD5 may not be used to sign, MAC, or check the integrity of
  anything, in new code or old. That includes webhook signatures.
- An exception needs written, time-limited sign-off from the security team
  (security@fernway.example) and is listed here. There are none at the
  moment.

## Secrets

- Each subscriber's webhook signing secret lives in the deploy's secret
  store and reaches hooks through the environment (`HOOKS_SECRET_<NAME>`).
  Never commit one; tests use made-up secrets.
