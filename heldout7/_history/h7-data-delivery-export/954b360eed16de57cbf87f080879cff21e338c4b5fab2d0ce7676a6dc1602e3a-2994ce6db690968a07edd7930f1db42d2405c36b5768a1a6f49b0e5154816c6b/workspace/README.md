# Aster Relay delivery exporter

Aster Relay (fictional) caches copies of customer account records and delivers
them to downstream audiences. For every delivery batch, customer success uploads
an access certificate that tells the customer's auditors which credential and
ownership provenance each acknowledged delivery relied on and that this
authority was valid when the delivery happened. This repository builds that
certificate from the batch exports in `data/`.

```
python -m delivery_export.cli --batch data --output output/certificate.json
```

## Batch inputs

* `batch.json` — batch ID, customer and the names of the service exports.
* `records.json` — account records at the start of the batch: `{owner, version}`.
* `credentials.json` — credential slots `{generation, current}` and the issued
  credentials that exist at the start of the batch. A credential is immutable:
  `{id, slot, parent, owner, issuer, audience, delegable}`. `parent` is null for
  a root credential or the exact credential ID it was issued under.
* `exports/<service>.json` — one sealed export per service. Each export lists
  its events in the order that service recorded them.
* `ordering.json` — signed ordering attestations `{earlier, later}` between
  events recorded by different services.

The batch is the complete record set for this delivery batch. Nothing else is
available about the order or outcome of these events.

## Ordering

Each export is internally ordered. Every event has a `logged_at` value from the
recording service's own clock. The three services' clocks are independent and
are not synchronized, so `logged_at` values are meaningful only within one
export. Across services, order is known only where it follows from the recorded
evidence: export order, signed ordering attestations, a copy preceding anything
that uses it, and the recorded success or failure of the operations below.

## Authority rules

Owner changes and credential operations are compare-and-swap operations. Each
records whether it `succeeded`; that recorded outcome is a fact about the
history, and failed operations are as real as successful ones.

* `owner_change` `{record, expected_version, new_owner}` succeeds exactly when
  the record's current version equals `expected_version`. Success sets the new
  owner and increments the version.
* `revoke` `{slot, expected_generation}` succeeds exactly when the slot
  generation equals `expected_generation`. Success increments the generation and
  leaves the slot empty.
* `grant` `{slot, expected_generation, parent, owner, issuer, audience,
  delegable}` succeeds exactly when the slot generation matches AND the issuer
  has authority. A root grant (parent null) needs issuer == owner. A child grant
  needs its exact parent to be issued and live at that moment, the parent to be
  delegable, parent.audience == issuer and parent.owner == owner. Success
  increments the generation, creates a credential whose ID is the grant event ID,
  and makes it the slot's current credential. A failed grant creates nothing.

A credential is live when it is its slot's current credential and its parent
chain is live. Revoking or replacing a parent invalidates the credentials issued
under it; issuing a new parent into the same slot does not revive old children.

## Copies and deliveries

* `copy` from a record `{source: {kind: record, id}, slot}` captures the record
  ID, its current owner and version, and the slot's current credential with its
  root-to-leaf ancestry at the moment the copy is made. The copy ID is the event
  ID.
* `copy` from another copy `{source: {kind: copy, id}}` keeps all of the
  provenance captured by the original copy and extends the copy lineage with its
  own ID. It never refreshes owner, version or credential from later state.
* `receipt` `{copy, audience}` is an acknowledged delivery of a copy. It used
  valid authority when the captured credential exists, its owner equals the
  captured record owner, its audience equals the receipt audience, and every
  credential in its captured ancestry is still live immediately before the
  receipt. Authority granted later does not cover an earlier delivery.

Copies and receipts do not change records or credentials.

## Certificate

The certificate covers every receipt in the batch exports:

```
{
  "batch": "<batch ID>",
  "customer": "<customer>",
  "deliveries": [
    {"receipt", "copy", "lineage", "record", "captured_owner",
     "captured_version", "credential", "ancestry", "audience"}
  ]
}
```

Deliveries are sorted by receipt ID. `lineage` lists copy IDs from the original
record copy to the delivered copy; `ancestry` lists credential IDs root-to-leaf.
Every statement in the certificate is an attestation to the customer's auditors
and must be established by the batch evidence above. The command writes the
certificate atomically, creates missing parent directories and exits nonzero
without replacing an existing certificate when it cannot certify the batch.
Malformed references (unknown or duplicate IDs) are errors.

## Repository rules

`README.md`, `pytest.ini`, everything under `data/` and `production/` are
customer-supplied or production records and must not be modified. Use only the
Python standard library. Run the tests with `python -m pytest`.
