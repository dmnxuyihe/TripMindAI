"""Unit tests for app/itinerary.py: visit hours, travel time, opening window, packing."""
from __future__ import annotations

import copy
import json

import pytest

from app.itinerary import (
    DEFAULT_VISIT_HOURS,
    apply_schedule,
    travel_minutes,
    visit_hours,
    window_of,
)

# 1 degree of latitude along a meridian, using the module's earth radius.
KM_PER_DEG_LAT = 111.1949


def spot(sid='S1', name='测试点', lat=30.25, lon=120.15, hours=1.5, tags=None):
    return {'id': sid, 'name': name, 'lat': lat, 'lon': lon,
            'tags': list(tags or []), 'duration_hours': hours}


def plan_of(day_spots, days=None, city='杭州'):
    """Build a raw (unscheduled) plan: one list of spots per day."""
    return {'city': city, 'days': days or len(day_spots),
            'daily': [{'day': index + 1, 'spots': copy.deepcopy(spots)}
                      for index, spots in enumerate(day_spots)]}


def north(lat, km):
    return {'lat': lat + km / KM_PER_DEG_LAT, 'lon': 120.0}


def street_spots(count, hours=0.8):
    """Nearby shopping-street spots: 0.8 h each, ~15 min walk apart."""
    names = 'ABCDEFGH'
    return [spot(f'S{index + 1}', f'测试商业街{names[index]}',
                 30.250 + index * 0.01, 120.150 + index * 0.01, hours=hours)
            for index in range(count)]


# --------------------------------------------------------------------------- #
# visit_hours
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize('attraction, expected_hours', [
    ({'name': '苏州博物馆'}, 2.0),
    ({'name': '某某展馆', 'tags': ['美术馆']}, 2.0),
    ({'name': '寒山寺'}, 1.0),
    ({'name': '灵隐寺', 'tags': ['寺庙', '文化']}, 1.0),
    ({'name': '苏州园林'}, 1.5),
    ({'name': '某某园林', 'tags': ['古典园林']}, 1.5),
    ({'name': '平江路商业街'}, 0.8),
    ({'name': '某某购物中心'}, 0.8),
    ({'name': '某某风景区'}, 3.5),
    ({'name': '黄山'}, 3.5),
    ({'name': '灵岩山'}, 3.5),
])
def test_visit_hours_by_category(attraction, expected_hours):
    assert visit_hours(attraction) == expected_hours


def test_scenic_park_keywords_are_not_shadowed_by_generic_park():
    """VISIT_HOURS 把「森林公园 / 地质公园」列为 3.5h，但它们都含「公园」，
    而「公园」所在的 2.0h 分组更靠前，导致这两类永远命中 2.0h（分支不可达）。"""
    assert visit_hours({'name': '某某森林公园'}) == 3.5
    assert visit_hours({'name': '某某地质公园'}) == 3.5


def test_visit_hours_temple_beats_mountain_keyword():
    """「寒山寺」含“山”字，但必须按寺庙算 1 小时，而不是按山算 3.5 小时。"""
    hours = visit_hours({'name': '寒山寺', 'tags': []})
    assert hours == 1.0
    assert hours != 3.5


@pytest.mark.parametrize('attraction, expected_hours', [
    ({'name': '某某故居', 'duration_hours': 2.2}, 2.2),
    ({'name': '某某故居', 'duration_hours': '2.5'}, 2.5),
    ({'name': '某某故居', 'duration_hours': None}, DEFAULT_VISIT_HOURS),
    ({'name': '某某故居', 'duration_hours': 'abc'}, DEFAULT_VISIT_HOURS),
    ({'name': '某某故居'}, DEFAULT_VISIT_HOURS),
])
def test_visit_hours_falls_back_to_duration(attraction, expected_hours):
    assert visit_hours(attraction) == expected_hours


# --------------------------------------------------------------------------- #
# travel_minutes
# --------------------------------------------------------------------------- #
def test_travel_from_start_point_costs_nothing():
    assert travel_minutes(None, {'lat': 30.0, 'lon': 120.0}) == (0, '起点')


@pytest.mark.parametrize('km', [0.0, 0.3, 1.0, 1.5, 2.4])
def test_short_legs_are_walked(km):
    minutes, mode = travel_minutes({'lat': 30.0, 'lon': 120.0}, north(30.0, km))
    assert mode == '步行'
    assert minutes >= 5
    assert minutes % 5 == 0


@pytest.mark.parametrize('km', [3.0, 8.0, 11.1, 25.0])
def test_long_legs_are_driven(km):
    minutes, mode = travel_minutes({'lat': 30.0, 'lon': 120.0}, north(30.0, km))
    assert mode == '驾车'
    assert minutes >= 5
    assert minutes % 5 == 0


@pytest.mark.parametrize('km', [0.01, 0.6, 2.4, 2.6, 5.0, 17.3, 40.0])
def test_travel_minutes_always_positive_multiple_of_five(km):
    minutes, mode = travel_minutes({'lat': 30.0, 'lon': 120.0}, north(30.0, km))
    assert isinstance(minutes, int)
    assert minutes >= 5
    assert minutes % 5 == 0
    assert mode == ('步行' if km <= 2.4 else '驾车')


# --------------------------------------------------------------------------- #
# window_of
# --------------------------------------------------------------------------- #
def test_window_of_prefers_real_opening_hours():
    assert window_of({'name': '某某', 'open_min': 540, 'close_min': 1020}) == (540, 1020, 'real')
    assert window_of({'name': '某某', 'open_min': 0, 'close_min': 1439}) == (0, 1439, 'real')


def test_window_of_real_beats_category_default():
    spot_with_real = {'name': '苏州博物馆', 'open_min': 600, 'close_min': 1200}
    assert window_of(spot_with_real) == (600, 1200, 'real')


@pytest.mark.parametrize('attraction, expected', [
    ({'name': '国家博物馆'}, (9 * 60, 17 * 60)),
    ({'name': '寒山寺'}, (7 * 60, 17 * 60)),
    ({'name': '某某园林'}, (7 * 60 + 30, 17 * 60 + 30)),
    ({'name': '平江路商业街'}, (10 * 60, 22 * 60)),
    ({'name': '太湖风景区'}, (8 * 60, 18 * 60)),
    ({'name': '灵岩山'}, (8 * 60, 18 * 60)),
])
def test_window_of_estimates_by_category(attraction, expected):
    assert window_of(attraction) == (*expected, 'estimated')


def test_window_of_unknown_category_uses_generic_fallback():
    assert window_of({'name': '某某故居'}) == (9 * 60, 18 * 60, 'estimated')


@pytest.mark.parametrize('attraction', [
    {'name': '某某', 'open_min': None, 'close_min': None},
    {'name': '某某', 'open_min': 1020, 'close_min': 540},          # close before open
    {'name': '某某', 'open_min': '540', 'close_min': '1020'},      # not ints
])
def test_window_of_invalid_real_window_is_estimated(attraction):
    open_min, close_min, source = window_of(attraction)
    assert source == 'estimated'
    assert close_min > open_min


# --------------------------------------------------------------------------- #
# apply_schedule
# --------------------------------------------------------------------------- #
def test_relaxed_pace_caps_daily_spots_and_budget():
    plan = apply_schedule(plan_of([street_spots(4)]), 'relaxed')
    day = plan['daily'][0]
    assert [s['id'] for s in day['spots']] == ['S1', 'S2', 'S3']
    assert day['day_load']['spot_count'] == 3
    assert day['day_load']['budget_hours'] == 6.0
    assert day['day_load']['used_hours'] <= 6.0
    assert plan['daily_max_spots'] == 3
    assert plan['pace'] == 'relaxed'


def test_overflowing_spot_lands_in_unscheduled():
    plan = apply_schedule(plan_of([street_spots(4)]), 'relaxed')
    assert [entry['name'] for entry in plan['unscheduled']] == ['测试商业街D']
    assert plan['unscheduled'][0]['reason']
    assert plan['spot_count'] == 3


def test_capacity_ledger_has_required_and_available_hours():
    plan = apply_schedule(plan_of([street_spots(4)]), 'relaxed')
    capacity = plan['capacity']
    for key in ('required_hours', 'available_hours', 'scheduled_hours',
                'recommended_days', 'total_spots', 'scheduled_spots', 'unscheduled_spots'):
        assert key in capacity
    assert capacity['available_hours'] == pytest.approx(6.0)
    assert capacity['required_hours'] > capacity['scheduled_hours']
    assert capacity['total_spots'] == 4
    assert capacity['scheduled_spots'] == 3
    assert capacity['unscheduled_spots'] == 1
    assert capacity['scheduled_spots'] + capacity['unscheduled_spots'] == capacity['total_spots']


def test_multi_day_plan_never_exceeds_daily_cap():
    spots = street_spots(8)
    plan = apply_schedule(plan_of([spots[:4], spots[4:]]), 'relaxed')
    for day in plan['daily']:
        assert len(day['spots']) <= 3
        assert day['day_load']['used_hours'] <= 6.0
    assert plan['spot_count'] == sum(len(day['spots']) for day in plan['daily'])
    assert plan['spot_count'] + len(plan['unscheduled']) == 8


def test_same_input_schedules_identically():
    first = apply_schedule(plan_of([street_spots(4)]), 'relaxed')
    second = apply_schedule(plan_of([street_spots(4)]), 'relaxed')
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == \
        json.dumps(second, ensure_ascii=False, sort_keys=True)


def test_timeline_stays_inside_day_window():
    plan = apply_schedule(plan_of([street_spots(3)]), 'relaxed',
                          day_start='09:00', day_end='18:00')
    for item in plan['daily'][0]['timeline']:
        start_hour, start_minute = (int(part) for part in item['start'].split(':'))
        end_hour, end_minute = (int(part) for part in item['end'].split(':'))
        assert 9 * 60 <= start_hour * 60 + start_minute <= 18 * 60
        assert 9 * 60 <= end_hour * 60 + end_minute <= 18 * 60
        assert (start_hour * 60 + start_minute) <= (end_hour * 60 + end_minute)


def test_travel_lookup_is_used_for_route_minutes():
    """真实通行时间（travel_lookup）优先于直线估算。"""
    calls = []

    def lookup(a, b):
        calls.append((a['id'], b['id']))
        return 35, '步行'

    plan = apply_schedule(plan_of([street_spots(2)]), 'relaxed', travel_lookup=lookup)
    travels = [item for item in plan['daily'][0]['timeline'] if item['kind'] == 'travel']
    assert travels
    assert travels[0]['minutes'] == 35
    assert travels[0]['mode'] == '步行'
    assert calls


def test_travel_lookup_failure_falls_back_to_estimate():
    def broken(a, b):
        raise RuntimeError('boom')

    plan = apply_schedule(plan_of([street_spots(2)]), 'relaxed', travel_lookup=broken)
    travels = [item for item in plan['daily'][0]['timeline'] if item['kind'] == 'travel']
    assert travels
    assert travels[0]['minutes'] > 0
