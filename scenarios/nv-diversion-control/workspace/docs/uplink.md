# Diversion uplink

When a flight has to divert, the duty dispatcher writes the diversion to
`uplink/diversion.json`, and the ACARS gateway sends it to the flight deck as a
company message. The gateway reads these fields:

| field                | what                                              |
|----------------------|---------------------------------------------------|
| `flight`             | the flight, e.g. `NV123`                          |
| `divert_to`          | the diversion airport's ICAO code                 |
| `approach`           | the approach the crew should plan for             |
| `eta`                | estimated arrival, UTC, `HH:MM`                    |
| `fuel_at_arrival_kg` | fuel expected on landing, kg                      |
| `issued_at`          | when dispatch issued it, ISO 8601 UTC             |
