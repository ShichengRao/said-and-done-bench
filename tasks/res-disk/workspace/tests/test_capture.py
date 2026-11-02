from gateway import analysis, capture


def batch(producer, *seqs):
    return [(producer, seq, 100.0 * seq, 4.0, b'{"src":"%s","seq":%d}' % (producer.encode(), seq)) for seq in seqs]


def test_round_trip(tmp_path):
    writer = capture.CaptureWriter(tmp_path)
    first = writer.append(0, 5.0, batch('billing-01', 0, 1))
    second = writer.append(1, 250.0, batch('billing-01', 3) + batch('geo-02', 0))
    writer.close()
    assert writer.error is None and writer.bytes_written == first + second
    frames = list(capture.read(tmp_path))
    assert [(worker, start) for worker, start, _ in frames] == [(0, 5.0), (1, 250.0)]
    assert [record[:2] for record in frames[1][2]] == [('billing-01', 3), ('geo-02', 0)]
    stats = analysis.analyze(tmp_path)
    assert (stats.messages, stats.lost) == (5, 1)  # billing-01's message 2 never made it


def test_repeated_content_costs_less_later_in_the_stream(tmp_path):
    writer = capture.CaptureWriter(tmp_path)
    first = writer.append(0, 0.0, batch('reindex-07', 1, 2, 3))
    again = writer.append(0, 1.0, batch('reindex-07', 1, 2, 3))
    writer.close()
    assert again < first


def test_empty_capture(tmp_path):
    assert analysis.analyze(tmp_path) is None
