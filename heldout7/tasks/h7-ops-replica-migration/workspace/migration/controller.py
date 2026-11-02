import copy

from migration.errors import MigrationError
from migration.fleet import active_links
from migration.safety import violations


class MigrationController:
    """Executes start/ready/commit actions against an in-memory model of the fleet.

    Every action is checked against the transport routes, the copy protocol and the
    safety rules before it changes state; a rejected action changes nothing.
    """

    def __init__(self, fleet):
        self.fleet = copy.deepcopy(fleet)
        self.links = active_links(self.fleet)
        self.positions = dict(self.fleet['initial']['positions'])
        self.images = dict(self.fleet['initial']['images'])
        self.shadow = None
        self.journal = []
        problems = violations(self.fleet, self.positions)
        if problems:
            raise MigrationError('initial fleet is unsafe: ' + '; '.join(problems))

    def state(self):
        return {'positions': dict(self.positions), 'images': dict(self.images),
                'shadow': None if self.shadow is None else list(self.shadow)}

    def apply(self, action):
        kind, unit, node = action
        if unit not in self.positions or node not in self.fleet['nodes']:
            raise MigrationError(f'unknown unit or node in {action}')
        if kind == 'start':
            if self.shadow is not None:
                raise MigrationError('another copy is already in progress')
            if (self.positions[unit], node) not in self.links:
                raise MigrationError(f'no active transport route {self.positions[unit]}->{node}')
            shadow = [unit, node, 'copying']
            problems = violations(self.fleet, self.positions, shadow)
            if problems:
                raise MigrationError('; '.join(problems))
            self.shadow = shadow
        elif kind == 'ready':
            if self.shadow != [unit, node, 'copying']:
                raise MigrationError('ready does not match a copying shadow')
            self.shadow = [unit, node, 'ready']
        elif kind == 'commit':
            if self.shadow != [unit, node, 'ready']:
                raise MigrationError('commit does not match a ready shadow')
            positions = dict(self.positions, **{unit: node})
            problems = violations(self.fleet, positions)
            if problems:
                raise MigrationError('; '.join(problems))
            self.positions = positions
            self.images[unit] = 'new'
            self.shadow = None
        else:
            raise MigrationError(f'unknown action {kind}')
        self.journal.append([kind, unit, node])

    def run(self, actions):
        for action in actions:
            self.apply(list(action))
        return self.state()

    def at_target(self):
        return (self.shadow is None and self.positions == self.fleet['target']
                and all(image == 'new' for image in self.images.values()))
