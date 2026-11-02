"""Splitting a file into the parts of a multipart upload."""

from dataclasses import dataclass


class TooManyParts(ValueError):
    pass


@dataclass(frozen=True)
class Part:
    number: int  # From 1.
    offset: int
    length: int


def plan_parts(size, part_size, max_parts):
    """Parts of `part_size` bytes that cover `size` bytes; the last may be smaller.

    An empty file is one empty part.
    """
    if part_size <= 0:
        raise ValueError('part_size must be positive')
    count = max(1, -(-size // part_size))
    if count > max_parts:
        raise TooManyParts(f'{size} bytes in {part_size}-byte parts is {count} parts; the store allows {max_parts}')
    return [Part(n + 1, n * part_size, min(part_size, size - n * part_size)) for n in range(count)]
