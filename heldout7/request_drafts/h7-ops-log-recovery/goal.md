Finish the recovery service and restore the customer’s requested consistent checkpoint from the exported transaction logs and seals.

Honor cross-shard dependencies, commit and abort decisions and the recorded before-images. Apply an advance atomically, preserve evidence identity and make replay and competing-process updates safe.

Exercise the supplied recovery history and add regression coverage for partial delivery, rollback and restart.
