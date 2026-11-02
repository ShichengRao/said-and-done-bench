Finish the migration checkpoint publisher for the customer’s exported shard logs. Publish the greatest causally consistent checkpoint that meets the requested minimum and produce the reconstructed customer snapshot.

Apply the documented commit, abort, alias and replay rules across shards. Keep every included transaction complete and preserve the original exported evidence and source state.

Integrate the publisher with the existing pipeline and add regression coverage for out-of-order delivery and replay.
