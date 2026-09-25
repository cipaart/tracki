import pytest


@pytest.fixture
def dest(tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    return folder
