from phomemo_studio.updater import parse_version

def test_versions():
    assert parse_version('v4.0.1') > parse_version('3.2.1')
    assert parse_version('4.0.0') == (4,0,0)
