# relay

Moves events from the partner feed to our broker, and emails ops when it
can't. One relay runs per region.

## Settings

`relay/config.py` resolves them, in this order: its defaults, the config
file (`$RELAY_CONFIG`, or `config/relay.toml`, production's), then
`RELAY_<SECTION>_<KEY>` environment variables, such as
`RELAY_SERVICE_WORKERS=12`. Credentials aren't in the config file: it names
them as `${VARIABLES}` from the environment.

To run relay here, load the made-up credentials first:

    set -a; . config/dev.env; set +a
    python3 -m relay check
    python3 -m relay run --once

## Tests

    python3 -m pytest
