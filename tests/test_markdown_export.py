import pytest
from viewer.main import format_token_count


@pytest.mark.parametrize("value,expected", [
    (500, "500"),
    (1000, "1.0K"),
    (1500, "1.5K"),
    (1000000, "1.0M"),
    (2500000, "2.5M"),
])
def test_format_token_count(value, expected):
    assert format_token_count(value) == expected
