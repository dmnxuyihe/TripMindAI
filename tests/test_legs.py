"""Unit tests for app/legs.py with monkeypatched AMap route helpers (no network)."""
from __future__ import annotations

from dataclasses import replace

import pytest

from app import legs
from app.config import Settings

PATH = [[120.10, 30.10], [120.20, 30.20]]


def amap_settings(**overrides):
    values = {'amap_api_key': 'test-key', 'amap_timeout_seconds': 3.0}
    values.update(overrides)
    return replace(Settings(), **values)


def point(lat, lon):
    return {'lat': lat, 'lon': lon}


@pytest.fixture()
def walking_calls(monkeypatch):
    """Replace app.legs.walking_route with a counting fake."""
    calls = []

    def fake_walking_route(start, end, *, key, timeout=12, client=None):
        calls.append({'start': dict(start), 'end': dict(end), 'key': key, 'timeout': timeout})
        return {'path': [list(p) for p in PATH], 'distance_m': 900, 'duration_s': 900}

    monkeypatch.setattr(legs, 'walking_route', fake_walking_route)
    return calls


def test_fetch_leg_returns_route_tuple(walking_calls):
    start, end = point(30.10, 120.10), point(30.11, 120.11)
    result = legs.fetch_leg(start, end, settings=amap_settings())

    assert result == (15, '步行', 'walking', PATH)
    assert len(walking_calls) == 1
    assert walking_calls[0]['key'] == 'test-key'
    assert walking_calls[0]['start'] == {'lat': 30.10, 'lon': 120.10}


def test_fetch_leg_second_call_hits_cache(walking_calls):
    start, end = point(30.10, 120.10), point(30.11, 120.11)
    settings = amap_settings()

    first = legs.fetch_leg(start, end, settings=settings)
    second = legs.fetch_leg(start, end, settings=settings)

    assert second == first
    assert len(walking_calls) == 1, '第二次调用命中缓存后不应再请求高德'


def test_fetch_leg_without_key_estimates_and_never_calls_amap(walking_calls):
    start, end = point(30.10, 120.10), point(30.11, 120.11)
    minutes, mode, source, path = legs.fetch_leg(start, end, settings=amap_settings(amap_api_key=''))

    assert walking_calls == []
    assert (mode, source, path) == ('步行', 'estimate', None)
    assert minutes == 20
    assert minutes % 5 == 0


def test_fetch_leg_estimates_when_amap_returns_nothing(monkeypatch):
    monkeypatch.setattr(legs, 'walking_route', lambda *args, **kwargs: None)
    start, end = point(30.10, 120.10), point(30.11, 120.11)

    minutes, mode, source, path = legs.fetch_leg(start, end, settings=amap_settings())

    assert source == 'estimate'
    assert path is None
    assert mode == '步行'
    assert minutes >= 5


def test_fetch_leg_estimates_when_amap_raises(monkeypatch):
    def broken(*args, **kwargs):
        raise legs.MapError('boom')

    monkeypatch.setattr(legs, 'walking_route', broken)
    start, end = point(30.10, 120.10), point(30.11, 120.11)

    minutes, mode, source, path = legs.fetch_leg(start, end, settings=amap_settings())

    assert source == 'estimate'
    assert (mode, path) == ('步行', None)
    assert minutes >= 5


def test_fetch_leg_uses_driving_branch_for_long_distance(monkeypatch):
    calls = []

    def fake_driving_route(start, end, *, key, timeout=12, client=None):
        calls.append((start, end))
        return {'driving_distance_km': 12.5, 'driving_duration_min': 27,
                'polyline': [[120.3, 30.3], [120.4, 30.4]]}

    monkeypatch.setattr(legs, 'driving_route', fake_driving_route)
    start, end = point(30.00, 120.00), point(30.10, 120.10)

    result = legs.fetch_leg(start, end, settings=amap_settings())

    assert result == (27, '驾车', 'driving', [[120.3, 30.3], [120.4, 30.4]])
    assert len(calls) == 1


def test_lookup_from_reads_prefetched_entries():
    start, end, other = point(30.10, 120.10), point(30.11, 120.11), point(30.50, 120.50)
    prefetched = {legs.key_of(start, end): (12, '步行', 'walking', PATH)}

    lookup = legs.lookup_from(prefetched)

    assert lookup(start, end) == (12, '步行')
    assert lookup(start, other) is None


def test_lookup_from_falls_back_to_process_cache(walking_calls):
    start, end = point(30.10, 120.10), point(30.11, 120.11)
    legs.fetch_leg(start, end, settings=amap_settings())

    lookup = legs.lookup_from({})

    assert lookup(start, end) == (15, '步行')
    assert len(walking_calls) == 1


def test_prefetch_returns_keyed_concurrent_result(walking_calls):
    a, b, c = point(30.10, 120.10), point(30.11, 120.11), point(30.12, 120.12)

    result = legs.prefetch([(a, b), (b, c)], settings=amap_settings(), budget_seconds=5.0)

    assert set(result) == {legs.key_of(a, b), legs.key_of(b, c)}
    for value in result.values():
        assert isinstance(value, tuple) and len(value) == 4
        minutes, mode, source, path = value
        assert minutes == 15
        assert mode == '步行'
        assert source == 'walking'
        assert path == PATH
    assert len(walking_calls) == 2


def test_prefetch_reuses_cache_without_refetching(walking_calls):
    a, b = point(30.10, 120.10), point(30.11, 120.11)
    settings = amap_settings()
    legs.fetch_leg(a, b, settings=settings)
    assert len(walking_calls) == 1

    result = legs.prefetch([(a, b)], settings=settings)

    assert len(walking_calls) == 1
    assert result[legs.key_of(a, b)][:2] == (15, '步行')


def test_prefetch_without_pairs_returns_empty_dict():
    assert legs.prefetch([], settings=amap_settings()) == {}


def test_key_of_is_stable_across_dict_order_and_rounding():
    a = {'lat': 30.123456, 'lon': 120.654321}
    b = {'lon': 120.111111, 'lat': 30.222222}
    assert legs.key_of(a, b) == (120.6543, 30.1235, 120.1111, 30.2222)
    assert legs.key_of(dict(reversed(list(a.items()))), b) == legs.key_of(a, b)


def test_clear_cache_forces_new_request(walking_calls):
    start, end = point(30.10, 120.10), point(30.11, 120.11)
    settings = amap_settings()
    legs.fetch_leg(start, end, settings=settings)
    legs.clear_cache()
    legs.fetch_leg(start, end, settings=settings)
    assert len(walking_calls) == 2
