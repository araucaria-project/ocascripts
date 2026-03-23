#!/usr/bin/env python3
"""Smoke tests for CLI modules and stable helper behavior."""

import subprocess

from ocascripts.fitscollectjson import parse_indented_list


def test_fitscollect_help():
    result = subprocess.run(
        ['python3', '-m', 'ocascripts.fitscollect', '--help'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'usage' in result.stdout.lower()


def test_fitscollectjson_parse_indented_list_simple_tree():
    lines = [
        'zb08c_0571_24540_zdf.fits\n',
        ' zb08c_0571_24540_master_f_V.fits\n',
    ]
    parsed = parse_indented_list(lines, root_path=None)

    assert len(parsed) == 1
    assert parsed[0]['name'] == 'zb08c_0571_24540_zdf.fits'
    assert len(parsed[0]['files']) == 1
    assert parsed[0]['files'][0]['name'] == 'zb08c_0571_24540_master_f_V.fits'


def test_fitscollectcalib_help():
    result = subprocess.run(
        ['python3', '-m', 'ocascripts.fitscollectcalib', '--help'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'calibration' in result.stdout.lower()


def test_fitscollectjson_help():
    result = subprocess.run(
        ['python3', '-m', 'ocascripts.fitscollectjson', '--help'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'json' in result.stdout.lower()

