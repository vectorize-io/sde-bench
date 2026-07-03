from metricsagg import window_p95


def test_window_with_two_extreme_samples():
    window = list(range(10, 64)) + [70, 74, 78, 82, 5000, 6000]
    assert window_p95(window) == 74


def test_window_with_tied_extremes():
    window = list(range(100, 154)) + [200, 210, 220, 230, 9000, 9000]
    assert window_p95(window) == 210


def test_plain_windows_no_spikes():
    assert window_p95(list(range(1, 61))) == 56
    assert window_p95(list(range(0, 120, 2))) == 110


def test_flat_windows():
    assert window_p95([50] * 60) == 50
    assert window_p95([50] * 58 + [1000, 2000]) == 50


def test_order_does_not_matter():
    window = list(range(10, 64)) + [70, 74, 78, 82, 5000, 6000]
    assert window_p95(list(reversed(window))) == 74


def test_result_is_a_sample():
    window = list(range(300, 354)) + [400, 410, 420, 430, 8000, 8100]
    assert window_p95(window) == 410
    assert window_p95(window) in window
