#!/usr/bin/env python3
"""Tests for safe glob filtering in fitscollectparquet."""

import re

from ocascripts.fitscollectparquet import glob_patterns_to_fullmatch_regex


def _matches(patterns: list[str], value: str) -> bool:
    regex = glob_patterns_to_fullmatch_regex(patterns)
    return re.fullmatch(regex, value, flags=re.IGNORECASE) is not None


def test_regex_metacharacters_are_treated_as_literals():
    assert _matches(['a|b'], 'a|b')
    assert _matches(['PG_0231+051'], 'PG_0231+051')
    assert _matches(['foo(bar)'], 'foo(bar)')
    assert _matches(['[abc]'], '[abc]')
    assert _matches(['.*'], '.*')

    assert not _matches(['a|b'], 'a')
    assert not _matches(['PG_0231+051'], 'PG_0231051')
    assert not _matches(['foo(bar)'], 'foobar')
    assert not _matches(['[abc]'], 'a')


def test_glob_wildcard_still_works():
    assert _matches(['SS_*'], 'SS_For')
    assert _matches(['mk*nik'], 'mkopernik')
    assert not _matches(['SS_*'], 'SX_For')


def test_repeated_options_keep_or_semantics():
    assert _matches(['SS_For', 'RR_Lyr'], 'SS_For')
    assert _matches(['SS_For', 'RR_Lyr'], 'RR_Lyr')
    assert not _matches(['SS_For', 'RR_Lyr'], 'XX_Cyg')


