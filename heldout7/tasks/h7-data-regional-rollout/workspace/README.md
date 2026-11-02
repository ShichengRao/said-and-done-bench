# Aster Relay regional replica rollout

Aster Relay (fictional) replicates each customer dataset across a pair of
storage nodes. The deploy command reads the customer configuration in `data/`,
chooses one topology (an approved replication link) per dataset and writes the
deployment plan the rollout job applies:

```
python -m rollout.deploy --config data --output output/deployment.json
```

## Configuration

* `rollout.json` — rollout ID and customer.
* `nodes.json` — storage nodes `{id, region, keys}`; `keys` lists the KMS keys
  available on that node.
* `links.json` — replication links `{id, nodes: [node, node]}`. Each link is an
  already-built bidirectional CDC pair; no other node pairs exist.
* `datasets.json` — `{id, units, replicas_required, regions, key,
  approved_links}`. `approved_links` are the links the customer approved for that
  dataset.
* `outage_profiles.json` — `{id, down, leases}`. `down` lists nodes that are
  unavailable in that profile and `leases` gives every node's current lease, in
  units, while that profile is in effect.

## Placement rules

* A dataset's topology is one of its `approved_links`, and both nodes of that
  link are in one of the dataset's `regions` and hold the dataset's `key`.
* The topology is committed once, before any outage happens, and must work in
  every listed outage profile. Re-placing datasets during an outage is not part
  of this rollout.
* In every profile, the dataset's link must keep at least `replicas_required`
  nodes that are not down.
* Every surviving replica holds a full copy: a node carries the dataset's full
  `units` for each dataset placed on it. In every profile, the units on each
  node that is up must fit that node's lease for that profile.
* The rollout uses the current leases exactly as listed.

Duplicate node, link or dataset IDs and datasets naming unknown links are
configuration errors.

## Deployment plan

```
{
  "rollout": "<rollout ID>",
  "customer": "<customer>",
  "datasets": [{"id": "<dataset>", "link": "<link ID>", "nodes": ["<node>", "<node>"]}]
}
```

Datasets are sorted by ID and `nodes` are sorted. The command writes the plan
atomically, creates missing directories and exits nonzero, leaving any existing
plan untouched, when it cannot produce a plan that meets the placement rules.

## Repository rules

`README.md`, `pytest.ini`, `data/` and `production/` are customer configuration
and production records; do not modify them. Use only the Python standard
library; run the tests with `python -m pytest`.
