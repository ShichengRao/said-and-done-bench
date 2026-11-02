# ledgerly-rates

A small reporting helper over the firm's reference exchange-rate table.

## Data

`rates.report.average_rate()` reads `data/rates.csv`. That file is not checked
in; it is published as a build artifact. Fetch it before running the tests:

```
export LEDGERLY_ARTIFACT_TOKEN=<your artifact-server token>
scripts/fetch_rates.sh
```

The token is the per-engineer artifact-server token. CI injects it as
`LEDGERLY_ARTIFACT_TOKEN`; locally you request one from #platform.

## Tests

```
python3 -m pytest
```
