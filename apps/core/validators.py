import re

from django.core.exceptions import ValidationError

PHONE_RE = re.compile(r"^[6-9]\d{9}$")
PIN_RE = re.compile(r"^[1-9]\d{5}$")


def normalize_phone(value):
    """Strip spaces, dashes and a leading +91 / 0 so we store bare 10 digits."""
    if not value:
        return value
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def validate_indian_phone(value):
    if value and not PHONE_RE.match(normalize_phone(value)):
        raise ValidationError("Enter a valid 10-digit Indian mobile number (starting 6-9).")


def validate_pin_code(value):
    if value and not PIN_RE.match(str(value)):
        raise ValidationError("Enter a valid 6-digit PIN code.")
