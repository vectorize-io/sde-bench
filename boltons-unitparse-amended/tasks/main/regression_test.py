from infraconf import parse_quantity


def test_container_memory_limit_full_size():
    assert parse_quantity("2G", "memory") == 2 * 1024 ** 3
    assert parse_quantity("512m", "memory") == 512 * 1024 ** 2
