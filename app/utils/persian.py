"""Persian text normalization for search and matching.

Folds the most common Arabic-vs-Persian shape differences and strips
zero-width non-joiners and short vowel marks so that user input matches
stored values regardless of which keyboard the writer used.
"""

import re
from typing import Any

from sqlalchemy import func

_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("ي", "ی"),  # Arabic yeh ي -> Persian yeh ی
    ("ى", "ی"),  # Arabic alef maksura ى -> Persian yeh ی
    ("ك", "ک"),  # Arabic kaf ك -> Persian kaf ک
    ("‌", " "),       # ZWNJ -> space (so word boundaries still match)
    ("‏", ""),        # right-to-left mark
    ("‎", ""),        # left-to-right mark
)

_DIACRITICS_PATTERN = re.compile(
    "[ؐ-ًؚ-ٰٟۖ-ۭ]"
)

_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_persian(value: str | None) -> str:
    if not value:
        return ""
    text = value
    for old, new in _REPLACEMENTS:
        text = text.replace(old, new)
    text = _DIACRITICS_PATTERN.sub("", text)
    text = text.translate(_DIGIT_TRANSLATION)
    return text.casefold().strip()


def normalize_persian_sql(column: Any) -> Any:
    """SQL-side mirror of normalize_persian.

    Implements the same yeh/kaf folding plus ZWNJ stripping. Diacritics
    are rare in saved metadata so we skip them in SQL to avoid bloating
    the WHERE clause; the Python side strips them from the user query so
    matches still work.
    """
    expression = func.lower(column)
    expression = func.replace(expression, "ي", "ی")
    expression = func.replace(expression, "ى", "ی")
    expression = func.replace(expression, "ك", "ک")
    return func.replace(expression, "‌", " ")
