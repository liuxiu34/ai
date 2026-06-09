from src.utils import normalize_yahoo_symbol, parse_market_cap


def test_normalize_yahoo_symbol_replaces_dot_with_dash():
    assert normalize_yahoo_symbol("BF.A") == "BF-A"
    assert normalize_yahoo_symbol(" brk.b ") == "BRK-B"


def test_parse_market_cap_handles_nasdaq_style_strings():
    assert parse_market_cap("$1,234,567,890") == 1234567890.0
    assert parse_market_cap("$1.5B") == 1500000000.0
    assert parse_market_cap("N/A") == 0.0
