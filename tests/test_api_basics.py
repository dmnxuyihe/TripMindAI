"""HTTP interface tests: read-only endpoints plus /api/plan and /api/route-geometry
validation branches (no AMap key is configured, so no outbound calls happen)."""
from __future__ import annotations

import pytest

from app.travel_core import cities_data

SEEDED_ATTRACTIONS = sum(len(entry['spots']) for entry in cities_data().values())


def test_health_reports_database_and_seed_count(client):
    response = client.get('/api/health')

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    assert body['database'] == 'ok'
    assert body['attractions'] == SEEDED_ATTRACTIONS
    assert body['qwen_configured'] is True
    assert body['amap_configured'] is False
    assert response.headers['X-Response-Time-ms'].isdigit()


def test_models_lists_configured_models_and_default(client):
    response = client.get('/api/models')

    assert response.status_code == 200
    body = response.json()
    ids = [model['id'] for model in body['models']]
    assert ids, '至少应返回一个可选模型'
    assert body['default'] in ids
    assert all(model['configured'] is True for model in body['models'])
    assert all(model['name'] == model['id'] for model in body['models'])


def test_cities_endpoint_lists_seed_cities(client):
    response = client.get('/api/cities')

    assert response.status_code == 200
    cities = response.json()['cities']
    names = [entry['city'] for entry in cities]
    assert len(names) == len(cities_data())
    assert names == sorted(names)
    assert {'city': '杭州', 'count': 10} in cities


def test_attractions_for_known_city(client):
    response = client.get('/api/attractions', params={'city': '杭州'})

    assert response.status_code == 200
    body = response.json()
    assert body['found'] is True
    assert body['city'] == '杭州'
    assert len(body['spots']) == 10
    first = body['spots'][0]
    for key in ('id', 'name', 'lat', 'lon', 'tags', 'duration_hours'):
        assert key in first
    assert isinstance(first['tags'], list)


def test_attractions_for_unknown_city_returns_empty_result(client):
    response = client.get('/api/attractions', params={'city': '不存在的城市'})

    assert response.status_code == 200
    body = response.json()
    assert body['found'] is False
    assert body['spots'] == []
    assert '不存在的城市' in body['note']


def test_attractions_requires_city_parameter(client):
    assert client.get('/api/attractions').status_code == 422


VALID_PLAN = {'city': '杭州', 'days': 2}


@pytest.mark.parametrize('overrides', [
    {'days': 0},
    {'days': 8},
    {'days': -1},
    {'days': 'two'},
    {'pace': 'fast'},
    {'pace': ''},
    {'day_start': '9点'},
    {'day_start': '25:00'},
    {'day_start': '0900'},
    {'clustering': 'mystery'},
    {'routing': 'random'},
    {'unexpected_field': 1},
])
def test_plan_rejects_invalid_payloads(client, overrides):
    response = client.post('/api/plan', json={**VALID_PLAN, **overrides})

    assert response.status_code == 422


def test_plan_requires_city(client):
    assert client.post('/api/plan', json={'days': 1}).status_code == 422


def test_plan_without_amap_key_returns_422(client):
    """校验通过后，缺少 AMAP_WEB_KEY 时以 422 说明原因（不冒用本地演示数据）。"""
    response = client.post('/api/plan', json={'city': '杭州', 'days': 1})

    assert response.status_code == 422
    assert 'AMAP_WEB_KEY' in response.json()['detail']


def test_route_geometry_without_amap_key_returns_422(client):
    # 空 segments 不触发外部调用，应返回 200；这里用非空请求验证缺 Key 分支
    segment = {'start': [120.1, 30.1], 'end': [120.2, 30.2]}
    response = client.post('/api/route-geometry', json={'segments': [segment]})

    assert response.status_code == 422
    assert 'AMAP_WEB_KEY' in response.json()['detail']


def test_route_geometry_empty_segments_returns_empty_legs(client_with_amap_key):
    response = client_with_amap_key.post('/api/route-geometry', json={'segments': []})

    assert response.status_code == 200
    body = response.json()
    assert body['legs'] == []
    assert body['note']


def test_route_geometry_defaults_to_no_segments(client_with_amap_key):
    response = client_with_amap_key.post('/api/route-geometry', json={})

    assert response.status_code == 200
    assert response.json()['legs'] == []


@pytest.mark.parametrize('segments', [
    [{'start': [120.1, 30.1]}],                       # 缺少 end
    [{'start': [120.1], 'end': [120.2, 30.2]}],       # start 不是二元组
    [{'start': ['a', 'b'], 'end': [120.2, 30.2]}],    # 坐标不是数字
    [{'start': [120.1, 30.1], 'end': [120.2, 30.2], 'extra': 1}],  # 多余字段
])
def test_route_geometry_rejects_malformed_segments(client_with_amap_key, segments):
    response = client_with_amap_key.post('/api/route-geometry', json={'segments': segments})

    assert response.status_code == 422
