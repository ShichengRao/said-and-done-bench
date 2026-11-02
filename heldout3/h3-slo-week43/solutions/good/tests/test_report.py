from slo import logs, report

TARGETS = {'api': {'availability': 99.9, 'p95_ms': 300}, 'checkout': {'availability': 99.9, 'p95_ms': 450}}


def line(svc, status, dur, route='/v1/orders'):
    return logs.parse(f'2026-10-12T09:00:00.000Z svc={svc} route={route} status={status} dur_ms={dur} sample_rate=1')


def test_parse():
    record = logs.parse('2026-10-12T09:14:03.120Z svc=api route=/v1/orders status=200 dur_ms=87 sample_rate=1\n')
    assert record == {'ts': '2026-10-12T09:14:03.120Z', 'svc': 'api', 'route': '/v1/orders', 'status': 200,
                      'dur_ms': 87, 'sample_rate': 1}


def test_nearest_rank():
    assert report.nearest_rank(list(range(1, 101)), 95) == 95
    assert report.nearest_rank([5], 95) == 5
    assert report.nearest_rank([10, 20, 30, 40], 95) == 40
    assert report.nearest_rank([10, 20, 30, 40], 50) == 20


def test_availability_counts_only_5xx_as_failed():
    records = [line('api', 200, 50)] * 996 + [line('api', 404, 10)] * 2 + [line('api', 503, 900)] * 2
    found = report.figures(records)['api']
    assert found['requests'] == 1000 and found['failed'] == 2
    assert round(found['availability'], 3) == 99.8


def test_health_checks_do_not_count():
    records = [line('api', 200, 50)] * 10 + [line('api', 200, 1, route='/healthz')] * 50
    assert report.figures(records)['api']['requests'] == 10


def test_table_says_which_slo_was_missed():
    records = [line('api', 200, 120)] * 1000 + [line('checkout', 200, 500)] * 999 + [line('checkout', 500, 600)] * 2
    lines = report.table(report.figures(records), TARGETS)
    assert lines[2] == '| api | 1,000 | 100.00% | 99.90% | 120 ms | 300 ms | yes |'
    assert lines[3] == '| checkout | 1,001 | 99.80% | 99.90% | 500 ms | 450 ms | no (availability, latency) |'


def sampled(svc, status, dur, rate):
    return logs.parse(f'2026-10-21T09:00:00.000Z svc={svc} route=/v1/orders status={status} dur_ms={dur} '
                      f'sample_rate={rate}')


def test_a_sampled_line_counts_for_its_sample_rate():
    records = [sampled('api', 200, 50, 10)] * 99 + [sampled('api', 503, 900, 1)] * 10
    found = report.figures(records)['api']
    assert found['requests'] == 1000 and found['failed'] == 10
    assert round(found['availability'], 3) == 99.0


def test_p95_weighs_sampled_lines():
    # 950 requests at 100 ms (95 lines) and 50 at 400 ms (kept in full): the p95 is 100 ms, not 400.
    records = [sampled('api', 200, 100, 10)] * 95 + [sampled('api', 404, 400, 1)] * 50
    assert report.figures(records)['api']['p95_ms'] == 100
