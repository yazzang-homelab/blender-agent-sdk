import pytest

from blender_agent import BlenderSession, find_blender


@pytest.fixture(scope="session")
def blender_bin():
    # Deliberately no skip: a missing Blender must fail the suite, not hide it.
    return find_blender()


@pytest.fixture
def session(blender_bin):
    with BlenderSession(blender_bin, timeout=120) as bl:
        yield bl


@pytest.fixture
def exec_session(blender_bin):
    with BlenderSession(blender_bin, allow_exec=True, timeout=120) as bl:
        yield bl
