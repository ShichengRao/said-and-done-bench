From: Tomasz Wiśniewski <t.wisniewski@northwind-logistics.example>
To: integrations@fernway.example
Date: Thu, 22 Oct 2026 16:12:40 +0200
Subject: Fernway webhooks failing our signature check since Oct 1

Hello,

Since October 1 every webhook you send us fails our signature check, so our
warehouse system drops your orders, and our people have been keying them in
from your portal by hand. Nothing changed on our side: attached is the
verification code we run (verify_webhook.py), which hasn't changed since we
integrated with you in April 2025.

We can't ship a change to that service before our next release window on
January 12. Could you make your webhooks pass it again before then?

Thanks,
Tomasz
Integration team, Northwind Logistics
