from metricsagg import window_p95


def test_p95_not_inflated():
    window = list(range(10, 64)) + [70, 74, 78, 82, 5000, 6000]
    assert window_p95(window) < 80
