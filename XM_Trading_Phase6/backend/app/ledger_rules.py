"""Pure validation for balanced postings; no real-money execution."""
from decimal import Decimal, InvalidOperation

class LedgerValidationError(ValueError):
    pass

def validate_posting(lines, currency):
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha() or currency != currency.upper():
        raise LedgerValidationError("ISO currency code required")
    if not isinstance(lines, (list, tuple)) or len(lines) < 2:
        raise LedgerValidationError("At least two posting lines required")
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    for line in lines:
        if not isinstance(line, dict) or not line.get("account_id"):
            raise LedgerValidationError("Valid account_id required")
        try:
            debit = Decimal(str(line.get("debit", "0")))
            credit = Decimal(str(line.get("credit", "0")))
        except (InvalidOperation, TypeError):
            raise LedgerValidationError("Invalid monetary amount")
        if not debit.is_finite() or not credit.is_finite() or debit < 0 or credit < 0:
            raise LedgerValidationError("Amounts must be finite and nonnegative")
        if (debit == 0) == (credit == 0):
            raise LedgerValidationError("Exactly one of debit or credit must be positive")
        if debit.as_tuple().exponent < -4 or credit.as_tuple().exponent < -4:
            raise LedgerValidationError("Maximum four decimal places")
        debit_total += debit
        credit_total += credit
    if debit_total != credit_total:
        raise LedgerValidationError("Unbalanced posting")
    return debit_total
