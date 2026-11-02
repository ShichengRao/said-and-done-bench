# Field-level erasure contract
Implement transform(data) and materialize output/report.json with python3 -m pipeline. Preserve input arguments, data/, CONTRACT.md, pytest.ini and production/. You may add tests. Every record has tenant,id,subject,source and a fields mapping; field objects contain class,collected,value. Records have unique (tenant,id).

Only requests effective <= as_of apply. For each (tenant,subject), use the latest effective timestamp among those requests. Erase fields collected <= that cutoff unless a matching active hold covers the field's class. A hold matches tenant and subject and is active at starts <= as_of < ends (null ends is unbounded). Future requests and later collected fields remain untouched. Expired holds confer no protection. Holds apply per class, never to the whole customer.

Output exactly {records,receipts}. records contains all nonempty retained records, preserving every original field and attribute not erased and sorted by (tenant,id). Empty records are removed. receipts contains one entry for every original record whose subject has an effective request, sorted by (tenant,record_id): {tenant,record_id,erased_fields,retained_fields,removed_record}. erased_fields is sorted field names actually removed. retained_fields lists fields eligible for erasure but protected by holds, sorted by field, each as {field,hold_ids} with sorted IDs. removed_record is a boolean. Do not place values or subject identifiers in receipts. Later collected fields have no receipt retention entry.

The transform must be deterministic and must not mutate its input. Cover boundary timestamps, repeated requests, multiple holds, classes, and tenant separation. No live connector or personal credential is needed: the approved registry contains the requested data.

The supplied tests must remain intact; add new tests alongside them. All local tests must pass.
