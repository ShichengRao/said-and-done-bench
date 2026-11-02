import pytest

from tallyboard import regions
from tallyboard.regions import Region

PILOT = Region("ne", "North East pilot", 700)


@pytest.fixture
def pilot_region():
    """The pilot store's region and rate, registered for one test."""
    regions.register(PILOT)
    yield PILOT
    regions.unregister(PILOT.code)
