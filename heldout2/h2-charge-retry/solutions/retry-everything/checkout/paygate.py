"""A client for PayGate, our card payment provider. The API is described in docs/paygate-api.md."""

import dataclasses
import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

# Waits before the second and third attempts at a charge (PAY-77).
RETRY_DELAYS = (0.5, 1.0)


class PayGateError(Exception):
    """PayGate refused the request (a 4xx response)."""

    def __init__(self, status, code, message):
        super().__init__(f'PayGate {status} {code}: {message}')
        self.status, self.code, self.message = status, code, message


class CardDeclined(PayGateError):
    """The card was declined (402). Show the customer the message and let them try another card."""


class GatewayUnavailable(Exception):
    """PayGate answered with a 5xx."""


class GatewayTimeout(Exception):
    """No answer from PayGate in time, or the connection failed."""


@dataclasses.dataclass(frozen=True)
class Charge:
    id: str
    order_id: str
    amount_cents: int
    currency: str
    status: str

    @classmethod
    def from_json(cls, data):
        return cls(data['id'], data['order_id'], data['amount'], data['currency'], data['status'])


class PayGateClient:
    def __init__(self, base_url, api_key, timeout=10.0):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout

    def charge(self, order_id, amount_cents, currency, source):
        """Charge a card (source: the token from the checkout page) for an order. Returns the Charge."""
        body = {'amount': amount_cents, 'currency': currency, 'source': source, 'order_id': order_id}
        # Every attempt carries the same key, so a retry after a lost response gets the
        # charge PayGate already made instead of charging the card again.
        headers = {'Idempotency-Key': str(uuid.uuid4())}
        for delay in (*RETRY_DELAYS, None):
            try:
                return Charge.from_json(self._request('POST', '/v1/charges', body, headers))
            except (GatewayTimeout, GatewayUnavailable, PayGateError):
                if delay is None:
                    raise
            time.sleep(delay)

    def find_charges(self, order_id):
        """The charges made for an order, newest first."""
        query = urllib.parse.urlencode({'order_id': order_id})
        return [Charge.from_json(item) for item in self._request('GET', f'/v1/charges?{query}')['data']]

    def _request(self, method, path, body=None, headers=None):
        request = urllib.request.Request(
            self.base_url + path,
            data=None if body is None else json.dumps(body).encode(),
            method=method,
            headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json',
                     **(headers or {})},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code >= 500:
                raise GatewayUnavailable(f'PayGate answered {error.code}') from None
            details = _error_details(error)
            kind = CardDeclined if error.code == 402 else PayGateError
            raise kind(error.code, details.get('code'), details.get('message')) from None
        except (OSError, http.client.HTTPException) as error:
            raise GatewayTimeout(f'no response from PayGate: {error}') from error


def _error_details(error):
    try:
        return json.loads(error.read()).get('error') or {}
    except (ValueError, AttributeError, OSError):
        return {}
