"""Canonical people, alias resolution, cohort masks and current consent."""


class Roster:
    def __init__(self, roster):
        self.people = sorted(roster['people'])
        self.index = {name: i for i, name in enumerate(self.people)}
        self.links = {}
        for row in roster['aliases']:
            if row['alias'] in self.links and self.links[row['alias']] != row['target']:
                raise ValueError('conflicting alias %s' % row['alias'])
            self.links[row['alias']] = row['target']
        for name in self.links:  # unused invalid chains are still errors
            self.resolve(name)
        latest = {}
        for row in roster['consents']:
            if row['person'] not in latest or row['revision'] > latest[row['person']]['revision']:
                latest[row['person']] = row
        self.consent = {name: latest[name]['allowed'] if name in latest else False for name in self.people}

    def resolve(self, name):
        seen = set()
        while name not in self.index:
            if name in seen or name not in self.links:
                raise ValueError('unknown member or alias cycle at %s' % name)
            seen.add(name)
            name = self.links[name]
        return name

    def mask(self, members):
        """Bit mask of distinct canonical people (bit i = i-th sorted person)."""
        return sum(1 << self.index[name] for name in {self.resolve(m) for m in members})

    def consents(self, mask):
        return all(self.consent[name] for i, name in enumerate(self.people) if mask >> i & 1)
