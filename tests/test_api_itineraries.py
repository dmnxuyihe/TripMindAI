"""HTTP interface tests for /api/itineraries (save/share) and /api/plan/edit (fine tuning)."""
from __future__ import annotations

import copy

import pytest

from app.itinerary import apply_schedule


def spot(sid, name, lat, lon, hours=0.8):
    return {'id': sid, 'name': name, 'lat': lat, 'lon': lon,
            'tags': ['商业街'], 'duration_hours': hours}


S1 = spot('S1', '测试商业街A', 30.250, 120.150)
S2 = spot('S2', '测试商业街B', 30.260, 120.160)
S3 = spot('S3', '测试商业街C', 30.270, 120.170)


def one_day_plan(spots):
    return {'city': '杭州', 'days': 1, 'daily': [{'day': 1, 'spots': copy.deepcopy(spots)}]}


@pytest.fixture()
def saved_plan():
    """A realistic already-scheduled plan (two spots on day 1)."""
    scheduled = apply_schedule(one_day_plan([S1, S2]), 'relaxed')
    assert len(scheduled['daily'][0]['spots']) == 2
    return scheduled


@pytest.fixture()
def two_spot_plan():
    return apply_schedule(one_day_plan([S1, S2]), 'relaxed')


# --------------------------------------------------------------------------- #
# /api/itineraries
# --------------------------------------------------------------------------- #
def test_save_itinerary_returns_id_and_share_url(client, saved_plan):
    response = client.post('/api/itineraries', json={'title': '杭州一日游', 'plan': saved_plan})

    assert response.status_code == 201
    body = response.json()
    assert body['id']
    assert body['title'] == '杭州一日游'
    assert body['url'] == f'/?trip={body["id"]}'


def test_save_itinerary_with_default_title(client, saved_plan):
    response = client.post('/api/itineraries', json={'plan': saved_plan})

    assert response.status_code == 201
    assert response.json()['title'] == '我的行程'


def test_get_itinerary_returns_identical_plan(client, saved_plan):
    itinerary_id = client.post('/api/itineraries', json={'plan': saved_plan}).json()['id']

    response = client.get(f'/api/itineraries/{itinerary_id}')

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == itinerary_id
    assert body['city'] == '杭州'
    assert body['plan'] == saved_plan
    assert body['created_at'].endswith('+00:00')


def test_list_itineraries_contains_saved_one(client, saved_plan):
    itinerary_id = client.post('/api/itineraries', json={'title': '列表测试', 'plan': saved_plan}).json()['id']

    body = client.get('/api/itineraries').json()

    assert [row['id'] for row in body['itineraries']] == [itinerary_id]
    assert body['itineraries'][0]['created_at'].endswith('+00:00')


def test_save_itinerary_with_empty_plan_returns_422(client):
    response = client.post('/api/itineraries', json={'plan': {}})

    assert response.status_code == 422
    assert '行程数据' in response.json()['detail']


def test_save_itinerary_without_daily_returns_422(client):
    response = client.post('/api/itineraries', json={'plan': {'city': '杭州', 'days': 1}})

    assert response.status_code == 422


def test_save_itinerary_rejects_extra_fields(client, saved_plan):
    response = client.post('/api/itineraries',
                           json={'plan': saved_plan, 'unexpected': 'x'})

    assert response.status_code == 422


def test_delete_itinerary_then_get_returns_404(client, saved_plan):
    itinerary_id = client.post('/api/itineraries', json={'plan': saved_plan}).json()['id']

    deleted = client.delete(f'/api/itineraries/{itinerary_id}')

    assert deleted.status_code == 200
    assert deleted.json() == {'deleted': True}
    assert client.get(f'/api/itineraries/{itinerary_id}').status_code == 404


def test_delete_missing_itinerary_returns_404(client):
    assert client.delete('/api/itineraries/does-not-exist').status_code == 404
    assert client.get('/api/itineraries/does-not-exist').status_code == 404


# --------------------------------------------------------------------------- #
# /api/plan/edit — remove
# --------------------------------------------------------------------------- #
def test_plan_edit_remove_drops_spot_from_day(client, two_spot_plan):
    response = client.post('/api/plan/edit',
                           json={'plan': two_spot_plan, 'op': 'remove', 'day': 1, 'spot_id': 'S1'})

    assert response.status_code == 200
    body = response.json()
    assert [item['id'] for item in body['daily'][0]['spots']] == ['S2']
    assert body['spot_count'] == 1


def test_plan_edit_remove_records_unscheduled_entry(client, two_spot_plan):
    """手动移除的景点应出现在 unscheduled 里。"""
    response = client.post('/api/plan/edit',
                           json={'plan': two_spot_plan, 'op': 'remove', 'day': 1, 'spot_id': 'S1'})

    assert response.status_code == 200
    body = response.json()
    assert len(body['unscheduled']) == 1
    assert body['unscheduled'][0]['name'] == '测试商业街A'


def test_plan_edit_remove_unknown_spot_returns_404(client, two_spot_plan):
    response = client.post('/api/plan/edit',
                           json={'plan': two_spot_plan, 'op': 'remove', 'day': 1, 'spot_id': 'NOPE'})

    assert response.status_code == 404
    assert response.json()['detail'] == '这一天的行程里没有该景点'


def test_plan_edit_remove_twice_keeps_all_removals(client):
    """连续移除两个景点后，unscheduled 应保留两条“手动移除”记录。"""
    scheduled = apply_schedule(one_day_plan([S1, S2, S3]), 'relaxed')
    assert [item['id'] for item in scheduled['daily'][0]['spots']] == ['S1', 'S2', 'S3']

    first = client.post('/api/plan/edit',
                        json={'plan': scheduled, 'op': 'remove', 'day': 1, 'spot_id': 'S1'})
    assert first.status_code == 200
    second = client.post('/api/plan/edit',
                         json={'plan': first.json(), 'op': 'remove', 'day': 1, 'spot_id': 'S2'})

    assert second.status_code == 200
    body = second.json()
    assert [item['id'] for item in body['daily'][0]['spots']] == ['S3']
    assert sorted(entry['name'] for entry in body['unscheduled']) == \
        ['测试商业街A', '测试商业街B']


def test_plan_edit_remove_then_add_restores_day(client, two_spot_plan):
    removed = client.post('/api/plan/edit',
                          json={'plan': two_spot_plan, 'op': 'remove', 'day': 1, 'spot_id': 'S1'})
    assert removed.status_code == 200
    plan_after_remove = removed.json()
    assert len(plan_after_remove['daily'][0]['spots']) == 1

    added = client.post('/api/plan/edit',
                        json={'plan': plan_after_remove, 'op': 'add', 'day': 1, 'spot': S1})

    assert added.status_code == 200
    ids = [item['id'] for item in added.json()['daily'][0]['spots']]
    assert sorted(ids) == ['S1', 'S2']


# --------------------------------------------------------------------------- #
# /api/plan/edit — add / validation
# --------------------------------------------------------------------------- #
def test_plan_edit_add_previously_unscheduled_spot(client):
    plan = one_day_plan([S1])
    plan['unscheduled'] = [{'name': '测试商业街B', 'reason': '超出每日时间预算'}]

    response = client.post('/api/plan/edit',
                           json={'plan': plan, 'op': 'add', 'day': 1, 'spot': S2})

    assert response.status_code == 200
    body = response.json()
    assert [item['id'] for item in body['daily'][0]['spots']] == ['S1', 'S2']
    assert all(entry['name'] != '测试商业街B' for entry in body['unscheduled'])


def test_plan_edit_add_keeps_other_unscheduled_entries(client):
    """把 B 加回行程，不应影响仍然排不下的 C/D 记录。"""
    plan = one_day_plan([S1])
    plan['unscheduled'] = [
        {'name': '测试商业街B', 'reason': '超出每日时间预算'},
        {'name': '测试商业街C', 'reason': '超出每日时间预算'},
    ]

    response = client.post('/api/plan/edit',
                           json={'plan': plan, 'op': 'add', 'day': 1, 'spot': S2})

    assert response.status_code == 200
    body = response.json()
    assert [item['id'] for item in body['daily'][0]['spots']] == ['S1', 'S2']
    assert [entry['name'] for entry in body['unscheduled']] == ['测试商业街C']


def test_plan_edit_add_requires_coordinates(client):
    plan = one_day_plan([S1])

    response = client.post('/api/plan/edit',
                           json={'plan': plan, 'op': 'add', 'day': 1,
                                 'spot': {'id': 'S9', 'name': '没有坐标的景点'}})

    assert response.status_code == 422
    assert ('坐标' in response.json()['detail'])


def test_plan_edit_unknown_op_returns_422(client, two_spot_plan):
    response = client.post('/api/plan/edit',
                           json={'plan': two_spot_plan, 'op': 'swap', 'day': 1, 'spot_id': 'S1'})

    assert response.status_code == 422
    assert response.json()['detail'] == '不支持的操作'


def test_plan_edit_day_beyond_plan_returns_422(client, two_spot_plan):
    response = client.post('/api/plan/edit',
                           json={'plan': two_spot_plan, 'op': 'remove', 'day': 2, 'spot_id': 'S1'})

    assert response.status_code == 422
    assert response.json()['detail'] == '天数超出范围'


@pytest.mark.parametrize('day', [0, 8, -1])
def test_plan_edit_day_out_of_model_range_returns_422(client, two_spot_plan, day):
    response = client.post('/api/plan/edit',
                           json={'plan': two_spot_plan, 'op': 'remove', 'day': day, 'spot_id': 'S1'})

    assert response.status_code == 422


def test_plan_edit_without_daily_returns_422(client):
    response = client.post('/api/plan/edit', json={'plan': {}, 'op': 'remove', 'day': 1, 'spot_id': 'S1'})

    assert response.status_code == 422
    assert response.json()['detail'] == '缺少行程数据'
