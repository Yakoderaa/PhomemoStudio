from types import SimpleNamespace
from phomemo_studio.printer import D30Printer, _Seen


def test_candidate_ranking_prefers_d30_and_saved_address():
    d1 = SimpleNamespace(address="AA:BB", name="D30")
    d2 = SimpleNamespace(address="CC:DD", name="Other")
    a = _Seen(d1, "D30", set(), -80)
    b = _Seen(d2, "Other", set(), -20)
    assert D30Printer._candidate_score(a, None) > D30Printer._candidate_score(b, None)
    assert D30Printer._candidate_score(b, "CC:DD") > D30Printer._candidate_score(a, None)


def test_characteristics_recognizes_phomemo_write_hint():
    ch = SimpleNamespace(uuid="0000ff02-0000-1000-8000-00805f9b34fb", properties=["write-without-response"])
    service = SimpleNamespace(uuid="0000ff00-0000-1000-8000-00805f9b34fb", characteristics=[ch])
    client = SimpleNamespace(services=[service])
    write, notify, identity = D30Printer._characteristics(client)
    assert write == ch.uuid
    assert notify is None
    assert identity is True


def test_unknown_generic_writer_is_not_treated_as_d30_identity():
    ch = SimpleNamespace(uuid="12345678-0000-0000-0000-000000000001", properties=["write"])
    service = SimpleNamespace(uuid="12345678-0000-0000-0000-000000000000", characteristics=[ch])
    client = SimpleNamespace(services=[service])
    write, notify, identity = D30Printer._characteristics(client)
    assert write == ch.uuid
    assert identity is False
