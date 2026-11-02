"""textable: plain-text tables with aligned columns.

    >>> print(textable.render(['name', 'n'], [['a', 1], ['bcd', 22]], align='<>'))
    name   n
    ----  --
    a      1
    bcd   22
"""

__all__ = ['render']
__version__ = '1.1.0'


def render(headers, rows, align=None, gap=2):
    """Lay out rows of values under headers, one line per row, columns padded to fit.

    align has one character per column, '<' for left and '>' for right; by
    default numbers go right and everything else left. Values are shown with
    str(), so format floats before passing them in.
    """
    cells = [[str(value) for value in row] for row in rows]
    if align is None:
        sample = rows[0] if rows else headers
        align = ''.join('>' if isinstance(value, (int, float)) else '<' for value in sample)
    if len(align) != len(headers) or any(len(row) != len(headers) for row in cells):
        raise ValueError('every row and the alignment need one entry per header')
    widths = [max(len(text) for text in column) for column in zip(headers, *cells)]
    rule = ['-' * width for width in widths]
    lines = []
    for row in [list(headers), rule, *cells]:
        padded = [text.ljust(width) if side == '<' else text.rjust(width)
                  for text, width, side in zip(row, widths, align)]
        lines.append((' ' * gap).join(padded).rstrip())
    return '\n'.join(lines)
