"""Region, key and link approval policy."""


def eligible_links(dataset, config):
    """Approved links for the dataset (spare capacity elsewhere is usable)."""
    return sorted(set(dataset['approved_links']))
