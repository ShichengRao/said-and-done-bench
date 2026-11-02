"""python3 -m costsplit INVOICE.csv CENTERS.csv: each center's share of each line, and its total."""

import sys

from costsplit.invoice import read_centers, read_lines, split_invoice


def money(cents):
    sign = '-' if cents < 0 else ''
    return f'{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}'


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    lines, centers = read_lines(argv[0]), read_centers(argv[1])
    split = split_invoice(lines, centers)
    width = max(len(line.description) for line in lines) if lines else 10
    print(' ' * width + ''.join(f'{name:>12}' for name, _ in centers))
    for index, line in enumerate(lines):
        print(f'{line.description:<{width}}' + ''.join(f'{money(split[name][index]):>12}' for name, _ in centers))
    print(f'{"total":<{width}}' + ''.join(f'{money(sum(split[name])):>12}' for name, _ in centers))
    return 0


if __name__ == '__main__':
    sys.exit(main())
