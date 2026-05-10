from app.utils.persian import normalize_persian


def test_folds_arabic_yeh_to_persian_yeh() -> None:
    assert normalize_persian("علي") == normalize_persian("علی")


def test_folds_arabic_kaf_to_persian_kaf() -> None:
    assert normalize_persian("ساكن") == normalize_persian("ساکن")


def test_folds_alef_maksura() -> None:
    assert normalize_persian("کبرى") == normalize_persian("کبری")


def test_strips_zwnj() -> None:
    # Word with ZWNJ (دسته‌بندی) should match the same word without it.
    with_zwnj = "دسته" + "‌" + "بندی"
    assert normalize_persian(with_zwnj) == normalize_persian("دسته بندی")


def test_normalizes_persian_and_arabic_digits() -> None:
    assert normalize_persian("۱۲۳") == "123"
    assert normalize_persian("١٢٣") == "123"


def test_strips_diacritics() -> None:
    assert normalize_persian("سَلام") == normalize_persian("سلام")


def test_returns_empty_for_none_or_blank() -> None:
    assert normalize_persian(None) == ""
    assert normalize_persian("   ") == ""
