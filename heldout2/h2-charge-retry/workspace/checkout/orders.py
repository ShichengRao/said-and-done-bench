"""Paying for an order at the end of checkout."""

import dataclasses

from checkout.paygate import CardDeclined


@dataclasses.dataclass(frozen=True)
class Order:
    id: str
    total_cents: int
    currency: str
    card_token: str
    status: str = 'pending'
    charge_id: str | None = None
    decline_message: str | None = None


def pay(order, client):
    """Charge the order's card. A declined card leaves the order pending with the bank's message;
    PayGate being down or slow raises (GatewayUnavailable, GatewayTimeout), and checkout shows
    "Something went wrong, please try again"."""
    try:
        charge = client.charge(order_id=order.id, amount_cents=order.total_cents, currency=order.currency,
                               source=order.card_token)
    except CardDeclined as declined:
        return dataclasses.replace(order, decline_message=declined.message)
    return dataclasses.replace(order, status='paid', charge_id=charge.id, decline_message=None)
