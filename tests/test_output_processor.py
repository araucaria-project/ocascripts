#!/usr/bin/env python3
"""Tests for JSON list parsing used by fitscollectjson."""

from ocascripts.fitscollectjson import parse_indented_list


def test_parse_indented_list_creates_observations():
    lines = [
        'zb08c_0571_24540_zdf.fits\n',
        'zb08c_0571_24541_zdf.fits\n',
    ]

    observations = parse_indented_list(lines, root_path=None)

    assert [o['observation'] for o in observations] == ['zb08c_0571_24540_zdf', 'zb08c_0571_24541_zdf']
    assert all(o['files'] == [] for o in observations)


def test_parse_indented_list_attaches_first_level_children():
    lines = [
        'zb08c_0571_24540_zdf.fits\n',
        ' zb08c_0571_24540_master_f_V.fits\n',
        ' zb08c_0571_24540_master_d.fits\n',
    ]

    observations = parse_indented_list(lines, root_path=None)

    assert len(observations) == 1
    assert observations[0]['name'] == 'zb08c_0571_24540_zdf.fits'
    assert [f['name'] for f in observations[0]['files']] == [
        'zb08c_0571_24540_master_f_V.fits',
        'zb08c_0571_24540_master_d.fits',
    ]


def test_parse_indented_list_ignores_blank_lines():
    lines = [
        '\n',
        'zb08c_0571_24540_zdf.fits\n',
        '   \n',
        ' zb08c_0571_24540_master_f_V.fits\n',
    ]

    observations = parse_indented_list(lines, root_path=None)

    assert len(observations) == 1
    assert len(observations[0]['files']) == 1

