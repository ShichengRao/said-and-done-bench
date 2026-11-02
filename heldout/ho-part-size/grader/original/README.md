# shipper

Uploads release artifacts (installers, tarballs) to the object store as
multipart uploads.

    python3 -m shipper upload FILE [--key KEY]
    python3 -m shipper plan FILE [--key KEY]     # what `upload` would send, as JSON

## Settings

`shipper/settings.py` builds the settings for the environment named by
`APP_ENV` (`dev` when it isn't set): the defaults in `shipper/defaults.py`,
then `config/base.toml`, then `config/<APP_ENV>.toml`. The release pipeline
runs with `APP_ENV=production`; staging's smoke tests with `APP_ENV=staging`.

## Tests

    python3 -m pytest
