"""Regression: _norm_name canonicalizes channel/playlist display names so
exported names still match live YouTube titles despite emoji, casing,
whitespace, punctuation, or unicode-form differences. This is what lets the
bulk mapping import resolve subscriptions that previously showed as
'channel not found'.
"""
from app import _norm_name


def test_norm_name_strips_emoji_and_symbols():
    assert _norm_name("1 DIGITAL HUB 🔥") == _norm_name("1 DIGITAL HUB")


def test_norm_name_collapses_whitespace():
    assert _norm_name("12  Pound   Productions") == _norm_name("12 Pound Productions")


def test_norm_name_case_insensitive():
    assert _norm_name("Tech World") == _norm_name("TECH WORLD")


def test_norm_name_fullwidth_unicode():
    assert _norm_name("Ｔｅｃｈ Ｗｏｒｌｄ") == _norm_name("Tech World")


def test_norm_name_strips_punctuation():
    assert _norm_name("Music!!") == _norm_name("Music")


def test_norm_name_distinct_names_stay_distinct():
    assert _norm_name("12 News") != _norm_name("21 News")


def test_norm_name_empty():
    assert _norm_name("") == ""
    assert _norm_name(None) == ""
