"""relay's logging: one line per event, credentials masked."""

import logging

from relay.redact import MASK, is_secret_key, mask_url


class RedactingFilter(logging.Filter):
    """Masks credentials in a record's extra fields before any handler sees them."""

    def filter(self, record):
        for name, value in list(vars(record).items()):
            if name.startswith('_') or not isinstance(value, str):
                continue
            if is_secret_key(name) and value:
                setattr(record, name, MASK)
            elif '://' in value:
                setattr(record, name, mask_url(value))
        return True


def setup(level='INFO'):
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root = logging.getLogger('relay')
    root.handlers[:] = [handler]
    root.setLevel(level)
    return root
