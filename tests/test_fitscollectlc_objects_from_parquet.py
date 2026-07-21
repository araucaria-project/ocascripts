#!/usr/bin/env python3
"""Tests for objects_from_parquet SCIPROG filtering in fitscollectlc."""

import pytest

pd = pytest.importorskip('pandas')
pytest.importorskip('pyarrow')

from ocascripts.fitscollectlc import objects_from_parquet


@pytest.fixture
def analytic_dir(tmp_path):
    df = pd.DataFrame({
        'OBJECT': ['UX_Car', 'ss_for', 'RR_Lyr', 'SX_For', None],
        'SCIPROG': ['FT2025B-1', 'FT2025B-1', 'FT2025A-9', 'FT2025B-1', 'FT2025B-1'],
    })
    df.to_parquet(tmp_path / 'wk06_report.parquet')
    return tmp_path


def test_filters_by_sciprog_and_lowercases_objects(analytic_dir):
    objects = objects_from_parquet(analytic_dir, ['FT2025B-1'], '*')
    assert objects == ['ss_for', 'sx_for', 'ux_car']


def test_sciprog_glob_pattern(analytic_dir):
    objects = objects_from_parquet(analytic_dir, ['FT2025*'], '*')
    assert objects == ['rr_lyr', 'ss_for', 'sx_for', 'ux_car']


def test_no_matching_sciprog_returns_empty(analytic_dir):
    assert objects_from_parquet(analytic_dir, ['NO-MATCH'], '*') == []


def test_specific_telescope_uses_matching_parquet_file(analytic_dir, tmp_path):
    other = pd.DataFrame({'OBJECT': ['OTHER_OBJ'], 'SCIPROG': ['FT2025B-1']})
    other.to_parquet(tmp_path / 'wk05_report.parquet')

    objects = objects_from_parquet(analytic_dir, ['FT2025B-1'], 'wk06')
    assert 'other_obj' not in objects
    assert objects == ['ss_for', 'sx_for', 'ux_car']
