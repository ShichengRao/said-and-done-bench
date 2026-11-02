"""A transaction: money in is positive, money out negative, always exact (Decimal, two places)."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

CENT = Decimal('0.01')


@dataclass(frozen=True)
class Transaction:
    date: dt.date
    amount: Decimal
    description: str
    account: str
    category: str = 'uncategorized'

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            raise TypeError('amount must be a Decimal')
        object.__setattr__(self, 'amount', self.amount.quantize(CENT))

    def to_json(self):
        return {'date': self.date.isoformat(), 'amount': str(self.amount), 'description': self.description,
                'account': self.account, 'category': self.category}

    @classmethod
    def from_json(cls, data):
        return cls(dt.date.fromisoformat(data['date']), Decimal(data['amount']), data['description'],
                   data['account'], data.get('category', 'uncategorized'))
