import pytest
import tempfile
import os

from matryoshka_tester.parse_data import build_containerlist


def test_default_containerlist():
    # assert len makes sure we are reading the default file
    # to check for any eventual TypeErrors
    assert len(build_containerlist()) != 0


def test_buildcontainerlist(tmp_path):
    tmpfile = tmp_path / "temp.json"
    with open(tmpfile, "w") as fw:
        fw.write("{}")
    with pytest.raises(TypeError):
        build_containerlist(tmpfile)
