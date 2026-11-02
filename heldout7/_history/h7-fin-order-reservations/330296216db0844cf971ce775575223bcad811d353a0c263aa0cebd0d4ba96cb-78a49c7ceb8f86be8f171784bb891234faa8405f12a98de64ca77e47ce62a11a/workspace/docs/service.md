# Reservation service contract

`procurement.service` implements `initialize(path,catalog)`, `apply(path,command)` and `snapshot(path)` using standard-library SQLite. Planning rules are in `planning.md`. Changes to several baskets can be applied atomically without temporarily releasing other customers' stock.

## Durable identity, time and initialization
initialize returns the CURRENT snapshot-shaped state, without advancing clock or history. Equal catalog reinitialization is a no-op; stock row order is ignored, all other arrays retain order. Changed catalog raises ValueError. snapshot returns {clock,stock,baskets,history}; clock starts 0; stock rows sort by (warehouse,ingredient) and expose {warehouse,ingredient,on_hand,held,available}; baskets sort by ID; history lists immutable accepted responses in commit order.

Every command has operation_id,at,kind. Exact structural JSON replay returns the ORIGINAL response BEFORE time/expiry/version checks, including after restart. Changed reuse raises ValueError. New requests require at>=clock. Tentatively expire every held basket with expires<=at, changing status expired and incrementing version once while retaining its plan. Errors roll back ALL changes, including expirations, clock, operation identity and history. Accepted unavailable outcomes still commit clock and expirations. No real wall clock is used. Inputs and returned historical objects must not share mutable identity. All calls are serialized transactions across processes and survive restart; SQLite JSON state is acceptable. All semantic errors raise ValueError; error text is unconstrained.

## Commands
reserve adds {basket,until,request}. ID must never have existed; until>at. Optimize this one basket against current availability. If no valid plan exists, result unavailable, baskets:[], no partial reservation; basket ID remains reusable. Otherwise create held/version 1, result reserved.

exchange adds {entries:[{basket,expected_version,until,request}]}. Entries unique/nonempty. Every referenced basket must be held AFTER tentative expiry, versions exact, until>at. Optimize ALL replacement requests jointly, crediting ALL selected baskets' old holds while keeping every other hold. If a joint plan exists, replace all selected plans/requests/expiries together and increment each version once, result exchanged. If no valid joint plan exists, result unavailable and return selected OLD baskets unchanged (including status,plan,version,expiry); do not release a failed replacement's holds. Other due expirations and clock still commit.

commit or release adds {basket,expected_version}; requires held and exact version after expiry. Commit atomically subtracts its ingredient plan from physical stock; release leaves physical stock unchanged. Set status committed/released, increment version, preserve plan. Terminal IDs cannot be reused. tick has no extra fields and only commits clock/expiry, result ticked.

Each accepted response is exactly {operation_id,result,baskets:[post-operation selected baskets sorted ID]}; tick has an empty list. Responses and history are immutable snapshots, not live aliases. An exchange's unavailable response includes every selected old basket. A rejected operation ID can be reused after correcting its payload.
