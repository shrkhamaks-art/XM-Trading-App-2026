import pytest
from app.ledger_rules import validate_posting, LedgerValidationError

def test_balanced():
    assert str(validate_posting([{"account_id":1,"debit":"12.50"},{"account_id":2,"credit":"12.50"}],"USD")) == "12.50"

@pytest.mark.parametrize("lines", [
    [{"account_id":1,"debit":"10"},{"account_id":2,"credit":"9"}],
    [{"account_id":1,"debit":"-1"},{"account_id":2,"credit":"-1"}],
    [{"account_id":1,"debit":"NaN"},{"account_id":2,"credit":"NaN"}],
    [{"account_id":1,"debit":"1","credit":"1"},{"account_id":2,"credit":"1"}],
    [{"account_id":1,"debit":"1.00001"},{"account_id":2,"credit":"1.00001"}],
])
def test_reject_invalid(lines):
    with pytest.raises(LedgerValidationError):
        validate_posting(lines,"USD")
