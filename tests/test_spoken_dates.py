"""Tests for spoken English and Spanish dates of birth (mcp_server_kit.spoken_dates)."""

from datetime import date

import pytest

from mcp_server_kit.cvs_demo_database import parse_dob
from mcp_server_kit.spoken_dates import parse_spoken_date

JEFF = date(1991, 3, 14)


@pytest.mark.parametrize("text", [
    "March fourteenth nineteen ninety-one",
    "march fourteen nineteen ninety one",
    "the fourteenth of March, nineteen ninety one",
    "the 14th of March 1991",
    "March 14th 1991",
    "Mar 14 1991",
    "It's March fourteenth, 1991",
    "14 de marzo de 1991",
    "catorce de marzo de mil novecientos noventa y uno",
    "Catorce de Marzo del 1991",
    "el 14 de marzo de mil novecientos noventa y uno",
    "catorce marzo mil novecientos noventa y uno",
])
def test_jeff_in_many_forms(text):
    assert parse_spoken_date(text) == JEFF


@pytest.mark.parametrize("text, expected", [
    ("March twenty first nineteen ninety one", date(1991, 3, 21)),
    ("veintiuno de marzo de mil novecientos noventa y uno", date(1991, 3, 21)),
    ("primero de mayo de dos mil cinco", date(2005, 5, 1)),
    ("May first two thousand five", date(2005, 5, 1)),
    ("June third twenty oh five", date(2005, 6, 3)),
    ("treinta y uno de diciembre de mil novecientos ochenta", date(1980, 12, 31)),
    ("September thirtieth nineteen eighty", date(1980, 9, 30)),
    ("1ro de enero de 2000", date(2000, 1, 1)),
    ("dieciséis de septiembre de mil novecientos setenta y dos", date(1972, 9, 16)),
    ("February twelfth nineteen hundred", date(1900, 2, 12)),
])
def test_other_dates(text, expected):
    assert parse_spoken_date(text) == expected


@pytest.mark.parametrize("text", [
    "",
    None,
    "nineteen ninety one",                    # no month
    "March nineteen ninety one",              # no day
    "March fourteenth",                       # no year
    "February thirtieth nineteen ninety one",  # not a date
    "March fourteen fifteen 1991",            # two days
    "March fourteen 1991 1992",               # two years
    "marzo veinte veinte",                    # a mangled run, no year
    "March fourteen seven eight 1991",        # words that don't form a number
    "March twenty ninety 1991",               # tens after tens
    "the march of time",                      # a month word and nothing else
])
def test_rejects(text):
    assert parse_spoken_date(text) is None


def test_parse_dob_falls_back_to_spoken():
    assert parse_dob("catorce de marzo de mil novecientos noventa y uno") == JEFF
    assert parse_dob("03141991") == JEFF
    assert parse_dob("not a date") is None
