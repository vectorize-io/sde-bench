import pytest
from infraconf import parse_quantity


def test_memory_suffixes_are_binary():
    assert parse_quantity("1K", "memory") == 1024
    assert parse_quantity("1M", "memory") == 1024 ** 2
    assert parse_quantity("1G", "memory") == 1024 ** 3
    assert parse_quantity("1T", "memory") == 1024 ** 4


def test_memory_suffix_case_insensitive():
    assert parse_quantity("2g", "memory") == 2 * 1024 ** 3
    assert parse_quantity("8k", "memory") == 8 * 1024


def test_bare_memory_number():
    assert parse_quantity("256", "memory") == 256 * 1024 ** 2
    assert parse_quantity("1", "memory") == 1024 ** 2


def test_disk_suffixes_are_decimal():
    assert parse_quantity("1M", "disk") == 1000 ** 2
    assert parse_quantity("1G", "disk") == 1000 ** 3
    assert parse_quantity("1T", "disk") == 1000 ** 4


def test_disk_suffix_case_insensitive():
    assert parse_quantity("40g", "disk") == 40 * 1000 ** 3


def test_bare_disk_number():
    assert parse_quantity("2", "disk") == 2 * 1000 ** 3


def test_disk_kilobyte_suffix_rejected():
    with pytest.raises(ValueError):
        parse_quantity("64K", "disk")
    with pytest.raises(ValueError):
        parse_quantity("64k", "disk")


def test_memory_kilobyte_suffix_allowed():
    assert parse_quantity("512K", "memory") == 512 * 1024


def test_larger_values():
    assert parse_quantity("16G", "memory") == 16 * 1024 ** 3
    assert parse_quantity("750G", "disk") == 750 * 1000 ** 3
