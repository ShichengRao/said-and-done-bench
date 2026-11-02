# Partner aggregate exporter

The exporter publishes this period's aggregate counts to the partner under the
customer's published release policy. It reads the customer records in `data/`
and writes the release document:

```
python -m partner_export.release --data data --output output/release.json
```

All people and data are fictional. IDs are case-sensitive.

## What the partner can see

The partner receives one package per period: its package ID, the counts of its
queries and its (public) utility. The package ID is itself an observation. The
whole policy that maps each possible dataset to a package is public, as is its
construction rule. A report that is safe when considered alone can become
identifying when a data-dependent policy selects it only for some datasets. Build
the whole policy first, then select the actual release. Every output the policy
can produce must leave the protected people's current values ambiguous.

## Records

`roster.json` has distinct canonical `people`, `aliases: [{alias, target}]` and
`consents: [{person, revision, allowed}]`. Canonical and alias namespaces are
disjoint. Aliases may point through aliases. Resolve them transitively and
deduplicate every cohort by canonical person. Identical repeated links are harmless.
Conflicting links, cycles and unknown members/targets are errors, including unused
invalid alias chains. Consent revisions are unique per person: the greatest
revision wins, and a person with no consent row has not consented. Input list
order is immaterial.

`prior.json` lists earlier public releases `{id, epoch, members, count}` with epoch
`old` or `current`. Counts are exact numbers of people with value 1, not cohort sizes.
Earlier releases remain public evidence after a consent withdrawal.

`policy.json` is `{max_changes, protected, minimum_utility}`. `max_changes` is the
public bound on how many people's values changed between the old and current
epochs. `protected` lists distinct canonical people whose CURRENT values must stay
ambiguous. `minimum_utility` is the required utility guarantee: every world's
assigned package must have at least this utility.

`snapshots.json` holds the private `old` and `current` maps (0/1 for every canonical
person). They must satisfy every prior count at its epoch and differ in at most
`max_changes` people; otherwise the records are invalid. The snapshots do not narrow
the hypothetical worlds and do not influence policy selection. They are only used
to validate the records and, after the policy is built, to pick the actual release.

## Baseline worlds

Enumerate every hypothetical old/current pair over the whole roster that satisfies
the prior counts and the transition bound. Project the pairs to DISTINCT current
vectors; several old predecessors give a current world no extra weight. Consent
affects release permission, not hypothetical values. With canonical people sorted,
the world key of a current vector is `sum(value_i * 2**i)`. This set is the public
baseline.

## Packages and policy selection

`packages.json` entries are `{id, queries: [{id, members}], utility, approved}`. A
package releases the ordered tuple of CURRENT counts of its queries (ordered by query
ID). A package is authorized only if `approved` is true and every distinct person in
every query currently consents. Exclude an unauthorized package whole: do not drop
people or queries. Empty cohorts are allowed. A package with no queries has utility
0; other utilities are positive integers. A package below `minimum_utility` is
ineligible. Query, prior and package IDs are unique.

A policy assigns exactly one eligible package to every baseline world. For each
output `(package ID, count tuple)`, consider only the worlds that this same policy
maps to that package and that give those counts. Each such nonempty group must
contain both values for every protected person. Every group must pass, not only the
one containing the actual dataset. With no protected people any nonempty group is
safe.

Among safe policies that meet the utility guarantee, choose the one with the best
utility. That means the greatest sum of assigned utilities over distinct baseline
worlds, with ties broken by the lexicographically smallest tuple of package IDs in
ascending world-key order. The guarantee is a constraint, not the objective: a
policy with a higher minimum utility can have a lower total. Do not optimize each
world separately, test a package against worlds the policy does not assign to it,
or combine different policies' groups.

If no safe eligible policy exists, do not invent a suppression package or lower the
guarantee. In that case the command exits nonzero and writes nothing. If the
baseline already fixes a protected value, no release can restore ambiguity.

At most 5 canonical people, 16 aliases, 16 consent rows, 4 prior releases,
3 packages, 2 queries per package and 12 baseline worlds occur, so at most
3**12 complete policies exist. Exhaustive search or a cover search over safe groups
is fine. Use only the standard library.

## Release document (`output/release.json`)

```
{
  "policy": [{"world", "package"}],             # sorted by world key
  "total_utility", "guaranteed_utility",        # sum and minimum of assigned utilities
  "publication": {"package", "counts": [{"id", "count"}], "utility"},  # actual dataset; counts by query ID
  "baseline_candidate_count",                   # distinct baseline worlds
  "candidate_count",                            # worlds sharing the actual output under the policy
  "protected_count", "ambiguous_protected_count",  # protected people / those with both values among them
  "excluded_packages": [{"id", "reason"}]       # ineligible only, by ID: not_authorized, else below_utility_floor
}
```

Only `publication` and the policy go to the partner; the rest is internal audit
metadata. The command writes atomically, creates missing directories and exits
nonzero, leaving an existing file untouched, on any error.

## Repository rules

`README.md`, `pytest.ini`, `data/` and `production/` are customer records and
production state; do not modify them. Run the tests with `python -m pytest`.
