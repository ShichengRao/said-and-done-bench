"""What a restoration plan does to loading: the dead block's load added along the path that picks it up."""

from dataclasses import dataclass


@dataclass
class Loading:
    segment: str
    before_a: float
    after_a: float
    rating_a: float

    @property
    def percent(self):
        return 100 * self.after_a / self.rating_a

    @property
    def over(self):
        return self.after_a > 1.1 * self.rating_a  # Within 10% is fine for a short restoration.


def study(plan, network, emergency=False):
    """Loading on every segment of the plan's pickup path after the plan restores its block."""
    block = network.dead[plan['restores']]
    picked_up = block['load_a']
    return [Loading(segment, network.amps[segment], network.amps[segment] + picked_up,
                    network.rating(segment, emergency))
            for segment in plan['pickup_path']]


def overloads(plan, network, emergency=False):
    return [loading for loading in study(plan, network, emergency) if loading.over]
