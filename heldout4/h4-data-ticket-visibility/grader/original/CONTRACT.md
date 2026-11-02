# Search projection contract
Implement transform(data), then python3 -m pipeline. Preserve data/, production/, CONTRACT.md, pytest.ini and the input object. You may add tests. Output exactly {results:[{query_id,documents:[{id,title}]}]} in query input order, documents sorted by id. Never output bodies or denied identifiers.

Documents are keyed by (tenant,id), with parent an id in the same tenant. Traverse the entire ancestor chain to check parent existence, cycles and deleted ancestors: a deleted document or any deleted ancestor hides the document even when inheritance is broken. Duplicate keys, missing parents and parent cycles are ValueError. Only queried tenants need validation.

Each query starts with principals user:<user> and everyone. Expand matching-tenant groups transitively: if any of a group's member principal strings is present, add group:<id>. Groups may refer to groups in cycles. Never use another tenant's memberships.

For ACL evaluation, include the document and ancestors up to and including the first node whose break_inheritance is true. A matching active deny anywhere in this segment overrides every allow. A rule is active at from <= query.at < until, null until unbounded. With no matching active allow, deny by default. Query terms are whitespace-separated casefolded strings; all must occur as substrings of title + space + body. Empty text matches every authorized document.

Exercise nested groups, deny precedence, deletion/inheritance distinction, expired grants, case folding, tenant boundaries and new unseen IDs. This is a local projection over a fully authorized export; no additional live credentials are necessary.

The supplied tests must remain intact; add new tests alongside them. All local tests must pass.
