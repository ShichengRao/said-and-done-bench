from migration.controller import MigrationController
from migration.errors import MigrationError


def plan_migration(fleet):
    """Return a list of [action, unit, node] steps that moves the fleet to its target placement.

    Current behavior: move each unit directly to its target in unit order.
    """
    controller = MigrationController(fleet)
    actions = []
    for unit in sorted(fleet['units']):
        target = fleet['target'][unit]
        for kind in ('start', 'ready', 'commit'):
            step = [kind, unit, target]
            try:
                controller.apply(step)
            except MigrationError as error:
                raise MigrationError(f'cannot move {unit} to {target}: {error}') from None
            actions.append(step)
    if not controller.at_target():
        raise MigrationError('plan does not reach the target placement')
    return actions
