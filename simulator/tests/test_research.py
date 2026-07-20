import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research import extract_candidate_tickers


def test_extract_candidate_tickers_uses_company_aliases_and_cashtags():
    text = "Netflix rallies while Bank of America upgrades $AMD before earnings"

    assert set(extract_candidate_tickers(text)) == {"NFLX", "BAC", "AMD"}


def test_extract_candidate_tickers_ignores_common_uppercase_words():
    text = "SEC says AI ETF flows rise while Apple shares fall"

    assert extract_candidate_tickers(text) == ["AAPL"]
