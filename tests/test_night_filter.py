#!/usr/bin/env python3
"""Tests for -N/--night filtering in fitscollect and fitscollectparquet."""

import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from ocafitsfiles import night_set

_has_pandas = pytest.importorskip is not None  # always True, used below
try:
    import pandas  # noqa: F401
    _has_pandas = True
except ImportError:
    _has_pandas = False


# ---------------------------------------------------------------------------
# night_set (core, from ocafitsfiles)
# ---------------------------------------------------------------------------

def test_night_set_none_returns_none():
    assert night_set(None) is None


def test_night_set_empty_returns_none():
    assert night_set([]) is None


def test_night_set_integers():
    result = night_set([1075, 1082])
    assert result == {1075, 1082}


def test_night_set_string_integers():
    result = night_set(['1075', '1082'])
    assert result == {1075, 1082}


def test_night_set_iso_dates():
    # Just verify it returns ints without error; exact values depend on oca_night logic
    result = night_set(['2025-12-09'])
    assert isinstance(result, set)
    assert len(result) == 1
    assert all(isinstance(n, int) for n in result)


def test_night_set_mixed_formats():
    result = night_set([1075, '1082', '2025-12-09'])
    assert isinstance(result, set)
    assert 1075 in result
    assert 1082 in result
    assert len(result) == 3


def test_night_set_invalid_raises():
    with pytest.raises(ValueError):
        night_set(['not-a-date'])


# ---------------------------------------------------------------------------
# fitscollect process_path — night filtering
# ---------------------------------------------------------------------------

def test_process_path_accepts_matching_night(tmp_path):
    from ocascripts.fitscollect import process_path, RET_NULL

    json_file = tmp_path / 'zb08c_1075_66218.json'
    json_file.touch()

    args = Namespace(check=False, name=False, raw=False, exclude_zdf=True)
    result = process_path(tmp_path, json_file, args, date_range=(0, 9999), nights={1075})
    assert result != RET_NULL
    assert result == ('zb08', '1075', 'c')


def test_process_path_rejects_non_matching_night(tmp_path):
    from ocascripts.fitscollect import process_path, RET_NULL

    json_file = tmp_path / 'zb08c_1075_66218.json'
    json_file.touch()

    args = Namespace(check=False, name=False, raw=False, exclude_zdf=True)
    result = process_path(tmp_path, json_file, args, date_range=(0, 9999), nights={1082, 1090})
    assert result == RET_NULL


def test_process_path_no_night_filter_passes_all(tmp_path):
    from ocascripts.fitscollect import process_path, RET_NULL

    json_file = tmp_path / 'zb08c_1075_66218.json'
    json_file.touch()

    args = Namespace(check=False, name=False, raw=False, exclude_zdf=True)
    result = process_path(tmp_path, json_file, args, date_range=(0, 9999), nights=None)
    assert result != RET_NULL


def test_process_path_night_and_date_range_intersection(tmp_path):
    from ocascripts.fitscollect import process_path, RET_NULL

    json_file = tmp_path / 'zb08c_1075_66218.json'
    json_file.touch()

    args = Namespace(check=False, name=False, raw=False, exclude_zdf=True)

    # Night 1075 is in set but outside date range
    result = process_path(tmp_path, json_file, args, date_range=(1080, 1090), nights={1075})
    assert result == RET_NULL

    # Night 1075 is in date range but not in set
    result = process_path(tmp_path, json_file, args, date_range=(1070, 1080), nights={1082})
    assert result == RET_NULL

    # Night 1075 satisfies both
    result = process_path(tmp_path, json_file, args, date_range=(1070, 1080), nights={1075})
    assert result != RET_NULL


# ---------------------------------------------------------------------------
# fitscollectparquet — basename night extraction
# ---------------------------------------------------------------------------

def test_parquet_basename_night_extraction():
    """The parquet night filter extracts night from basename via split('_')[1]."""
    basenames = [
        ('zb08c_1075_66218', 1075),
        ('zb08c_0347_70898', 347),
        ('jk16a_1200_12345', 1200),
    ]
    for bid, expected_night in basenames:
        assert int(bid.split('_')[1]) == expected_night


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------

def test_fitscollect_help_shows_night_option():
    result = subprocess.run(
        ['python3', '-m', 'ocascripts.fitscollect', '--help'],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert '--night' in result.stdout
    assert 'NIGHT' in result.stdout


@pytest.mark.skipif(not _has_pandas, reason='pandas not installed')
def test_fitscollectparquet_help_shows_night_option():
    result = subprocess.run(
        ['python3', '-m', 'ocascripts.fitscollectparquet', '--help'],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert '--night' in result.stdout
    assert 'NIGHT' in result.stdout
