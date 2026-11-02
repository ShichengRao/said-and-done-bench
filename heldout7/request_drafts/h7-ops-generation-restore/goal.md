Finish the restore routine and recover the customer’s original generation from the attached fragment export. The customer needs the exact original bytes, and the restore must honor the documented tolerance of up to two corrupted fragment values.

Use the current generation’s admitted fragments and the existing encoding format. Validate exported records against their checksums and preserve the source fragments. The checksum contract describes what those checksums authenticate.

Wire the restored generation into the recovery command and add regression coverage for the documented corruption cases.
