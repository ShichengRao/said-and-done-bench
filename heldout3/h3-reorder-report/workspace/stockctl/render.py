"""Plain-text tables for the terminal."""


def table(headers, rows, right=()):
    """Columns padded to their widest cell, a dashed line under the headers.

    `right` holds the indexes of columns to right-align (numbers).
    """
    cells = [[str(cell) for cell in row] for row in [headers, *rows]]
    widths = [max(len(row[column]) for row in cells) for column in range(len(headers))]

    def line(row):
        return '  '.join(cell.rjust(widths[i]) if i in right else cell.ljust(widths[i])
                         for i, cell in enumerate(row)).rstrip()

    return '\n'.join([line(cells[0]), '  '.join('-' * width for width in widths), *map(line, cells[1:])])
