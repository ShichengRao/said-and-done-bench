"""Running a flash sale: a batch of orders and deliveries, on a pool of workers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from holdfast.models import Delivery, Order

WORKERS = 8


def run_sale(shop, steps, workers: int = WORKERS) -> list:
    """Apply each Order and Delivery in `steps`; returns their results in order.

    Steps are independent of each other, so they run in parallel, the way
    storefront requests and warehouse messages arrive during a real sale.
    """
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="sale") as pool:
        futures = [pool.submit(_apply, shop, step) for step in steps]
        return [future.result() for future in futures]


def _apply(shop, step):
    if isinstance(step, Order):
        return shop.reserve(step)
    if isinstance(step, Delivery):
        return shop.receive(step.sku, step.units)
    raise TypeError(f"unknown sale step: {step!r}")
