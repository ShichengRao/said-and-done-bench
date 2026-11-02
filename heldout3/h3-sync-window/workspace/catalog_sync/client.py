"""Halden Wholesale's product API (docs/supplier-api.md)."""

import json
import urllib.error
import urllib.request

from catalog_sync import settings


class SupplierError(Exception):
    pass


class NotFound(SupplierError):
    pass


class RateLimited(SupplierError):
    def __init__(self, retry_after):
        super().__init__(f'rate limited; retry after {retry_after} s')
        self.retry_after = retry_after


class SupplierClient:
    def __init__(self, base_url=None, key=None, timeout=settings.TIMEOUT_S):
        self.base_url = (base_url or settings.SUPPLIER_URL).rstrip('/')
        self.key = settings.SUPPLIER_KEY if key is None else key
        self.timeout = timeout

    def product(self, sku):
        """Today's price and stock for one SKU: {sku, name, price: {amount, currency}, stock, updated_at}."""
        request = urllib.request.Request(f'{self.base_url}/products/{sku}',
                                         headers={'Authorization': f'Bearer {self.key}', 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as answer:
                return json.load(answer)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise NotFound(sku) from error
            if error.code == 429:
                raise RateLimited(int(error.headers.get('Retry-After') or 1)) from error
            raise SupplierError(f'{sku}: HTTP {error.code}') from error
        except (urllib.error.URLError, OSError) as error:
            raise SupplierError(f'{sku}: {error}') from error
