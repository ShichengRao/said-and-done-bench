Finish the deployment controller and roll the customer’s services onto their approved target nodes. Keep the rollout able to finish after any one start failure covered by the operating policy.

Respect handoff capacity, node occupancy and quarantine. Process readiness and retirement acknowledgments separately, retain fencing across epochs and make request replay durable and atomic.

Run the attached rollout through the controller and add regression coverage for delayed acknowledgments and failure recovery.
