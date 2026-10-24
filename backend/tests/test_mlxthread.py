import threading
import time

from mlxthread import MLXThread


def test_everything_runs_on_one_thread():
    m = MLXThread()
    ids = set()
    results = []

    def work(i):
        ids.add(threading.get_ident())
        return i * 2

    def caller(i):
        results.append(m.call(lambda: work(i)))

    ts = [threading.Thread(target=caller, args=(i,)) for i in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(results) == [0, 2, 4, 6, 8, 10]
    assert len(ids) == 1 and threading.get_ident() not in ids


def test_iterate_streams_in_order_and_propagates_errors():
    m = MLXThread()
    seen = []

    def gen():
        seen.append(threading.get_ident())
        yield from ("a", "b", "c")

    assert list(m.iterate(gen)) == ["a", "b", "c"]

    def bad():
        yield "x"
        raise ValueError("boom")
    got = []
    try:
        for x in m.iterate(bad):
            got.append(x)
        raise AssertionError("should have raised")
    except ValueError as e:
        assert str(e) == "boom" and got == ["x"]


def test_abandoning_a_stream_frees_the_worker():
    m = MLXThread()
    closed = threading.Event()

    def endless():
        try:
            n = 0
            while True:
                n += 1
                yield n
                time.sleep(0.001)
        finally:
            closed.set()

    it = m.iterate(endless)
    assert next(it) == 1
    it.close()
    assert closed.wait(2)
    assert m.call(lambda: "free") == "free"


def test_cancel_event_stops_generation():
    m = MLXThread()
    cancel = threading.Event()
    out = []
    for x in m.iterate(lambda: iter(range(10_000_000)), cancel):
        out.append(x)
        if x == 3:
            cancel.set()
    assert out[:4] == [0, 1, 2, 3] and len(out) < 1000
