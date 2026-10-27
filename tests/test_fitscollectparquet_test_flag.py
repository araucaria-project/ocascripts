#!/usr/bin/env python3
"""Tests for TEST=1 frame handling in fitscollectparquet."""

import sys

import pandas as pd
import pytest

from ocascripts import fitscollectparquet


def _write_report(path, with_test_column=True):
    data = {
        'id': ['zb08c_1100_00001', 'zb08c_1100_00002', 'zb08c_1100_00003'],
        'IMAGETYP': ['science'] * 3,
        'TELESCOP': ['zb08'] * 3,
        'OBJECT': ['SS_For'] * 3,
    }
    if with_test_column:
        data['TEST'] = [0.0, 1.0, None]
    pd.DataFrame(data).to_parquet(path / 'zb08_report.parquet')


def _run(monkeypatch, capsys, tmp_path, *extra):
    monkeypatch.setattr(sys, 'argv', ['fitscollectparquet', '-A', str(tmp_path), '-D', str(tmp_path), '-n', *extra])
    assert fitscollectparquet.main() == 0
    return capsys.readouterr().out.split()


def test_default_excludes_test_frames(monkeypatch, capsys, tmp_path):
    _write_report(tmp_path)
    out = _run(monkeypatch, capsys, tmp_path)
    assert len(out) == 2
    assert not any('00002' in name for name in out)


def test_include_test_keeps_all_frames(monkeypatch, capsys, tmp_path):
    _write_report(tmp_path)
    assert len(_run(monkeypatch, capsys, tmp_path, '-T')) == 3


def test_only_test_outputs_test_frames(monkeypatch, capsys, tmp_path):
    _write_report(tmp_path)
    out = _run(monkeypatch, capsys, tmp_path, '--only-test')
    assert len(out) == 1
    assert '00002' in out[0]


def test_values_respects_default_exclusion(monkeypatch, capsys, tmp_path):
    _write_report(tmp_path)
    assert _run(monkeypatch, capsys, tmp_path, '--values', 'TEST') == ['0.0']


def test_missing_column_means_no_test_frames(monkeypatch, capsys, tmp_path):
    _write_report(tmp_path, with_test_column=False)
    assert len(_run(monkeypatch, capsys, tmp_path)) == 3
    assert len(_run(monkeypatch, capsys, tmp_path, '-T')) == 3
    assert _run(monkeypatch, capsys, tmp_path, '--only-test') == []


def test_include_and_only_are_mutually_exclusive(monkeypatch, tmp_path):
    _write_report(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['fitscollectparquet', '-A', str(tmp_path), '-T', '--only-test'])
    with pytest.raises(SystemExit):
        fitscollectparquet.main()
