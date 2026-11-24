"""回归用例：本次压测发现的边界（缺坐标、缺名称、出发时间过晚）。"""
import copy

SPOTS = [
    {'id': 'S1', 'name': '测试园林甲', 'lat': 31.30, 'lon': 120.60, 'tags': ['园林'], 'duration_hours': 1.5},
    {'id': 'S2', 'name': '测试寺庙乙', 'lat': 31.31, 'lon': 120.61, 'tags': ['寺庙'], 'duration_hours': 1.0},
]


def _plan():
    return {
        'city': '苏州', 'origin': '上海', 'days': 1, 'clustering': 'kmeans', 'routing': 'greedy',
        'pace': 'relaxed', 'day_start': '09:00',
        'center': {'lat': 31.30, 'lon': 120.60},
        'daily': [{'day': 1, 'theme': '园林', 'spots': copy.deepcopy(SPOTS)}],
        'unscheduled': [],
    }


def test_reschedule_tolerates_spot_without_coordinates(client):
    plan = _plan()
    plan['daily'][0]['spots'][0].pop('lat', None)
    plan['daily'][0]['spots'][0].pop('lon', None)

    response = client.post('/api/plan/reschedule', json={'plan': plan})

    assert response.status_code == 200, response.text
    body = response.json()
    scheduled = [spot['name'] for day in body['daily'] for spot in day['spots']]
    assert '测试园林甲' not in scheduled
    assert any(item.get('name') == '测试园林甲' for item in body['unscheduled'])


def test_reschedule_tolerates_spot_without_name(client):
    plan = _plan()
    plan['daily'][0]['spots'][0]['name'] = None

    response = client.post('/api/plan/reschedule', json={'plan': plan})

    assert response.status_code == 200, response.text
    names = [spot['name'] for day in response.json()['daily'] for spot in day['spots']]
    assert '未命名景点' in names


def test_plan_rejects_too_late_start(client):
    response = client.post('/api/plan', json={'city': '苏州', 'days': 1, 'day_start': '23:00'})

    assert response.status_code == 422
    assert '太晚' in response.json()['detail']


def test_plan_rejects_start_exactly_at_end_of_window(client):
    response = client.post('/api/plan', json={'city': '苏州', 'days': 1, 'day_start': '17:00'})

    assert response.status_code == 422
