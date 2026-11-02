"""Reading the catalog export (CSV: id,title) and writing its slugs."""

import csv
import sys

from catalog.slugs import unique_slugs


def read_catalog(path):
    """[(id, title)] from a catalog export, in catalog order."""
    with open(path, newline='', encoding='utf-8') as handle:
        return [(int(row['id']), row['title']) for row in csv.DictReader(handle)]


def main(argv=None):
    """python3 -m catalog.export CATALOG.csv: print id,slug for every product."""
    argv = sys.argv[1:] if argv is None else argv
    products = read_catalog(argv[0])
    writer = csv.writer(sys.stdout, lineterminator='\n')
    writer.writerow(['id', 'slug'])
    for (product_id, _), slug in zip(products, unique_slugs(title for _, title in products)):
        writer.writerow([product_id, slug])


if __name__ == '__main__':
    main()
