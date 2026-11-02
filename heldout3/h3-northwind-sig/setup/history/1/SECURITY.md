# Security rules

## Secrets

- Each subscriber's webhook signing secret lives in the deploy's secret
  store and reaches hooks through the environment (`HOOKS_SECRET_<NAME>`).
  Never commit one; tests use made-up secrets.
