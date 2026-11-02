Finish the payout scheduler and release the customer’s entire batch using the signed settlement instructions and approved bridge facilities. The batch must end with all payouts settled and every bridge repaid.

Use actual receipt availability when funding later steps, honor dispatch and bridge activation windows and keep each account within its authorized balance limits. Preserve existing settlements and approvals.

Generate the schedule for the attached batch at `output/release_schedule.json` with the existing `schedule` command, connect it to the replay worker and add regression coverage for delayed receipts. The README and `docs/` describe the records, the replay worker and the schedule format.
