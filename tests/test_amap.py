"""Unit tests for app/amap.py parsing helpers (no network involved)."""
from __future__ import annotations

import pytest

from app.amap import _dedupe, parse_opentime


@pytest.mark.parametrize('raw, expected', [
    ('09:00-17:00', {'open_min': 540, 'close_min': 1020}),
    ('09:00 - 17:00', {'open_min': 540, 'close_min': 1020}),
    ('周一至周日 08:30-17:00', {'open_min': 510, 'close_min': 1020}),
    ('周一至周五 09:00-17:00;周六至周日 10:00-18:00',
     {'open_min': 540, 'close_min': 1020}),
    ('8:30-17:00', {'open_min': 510, 'close_min': 1020}),
    ('09:00~17:00', {'open_min': 540, 'close_min': 1020}),
    ('09:00至17:00', {'open_min': 540, 'close_min': 1020}),
    ('24小时营业', {'open_min': 0, 'close_min': 23 * 60 + 59}),
    ('全天开放', {'open_min': 0, 'close_min': 23 * 60 + 59}),
])
def test_parse_opentime_supported_formats(raw, expected):
    assert parse_opentime(raw) == expected


@pytest.mark.parametrize('raw', [
    None,
    '',
    '   ',
    '暂无信息',
    '请咨询景区',
    '17:00-09:00',          # 结束早于开始，不做猜测
    '09:00-09:00',          # 开闭门时间相同，视为无效
])
def test_parse_opentime_unparsable_returns_none(raw):
    assert parse_opentime(raw) is None


def test_parse_opentime_only_reads_first_period():
    assert parse_opentime('09:00-17:00;18:00-21:00') == {'open_min': 540, 'close_min': 1020}


def test_parse_opentime_close_equal_open_is_invalid():
    assert parse_opentime('09:00-09:00') is None


def test_dedupe_keeps_single_copy_of_same_name():
    spots = [
        {'name': '西湖', 'lat': 30.2500, 'lon': 120.1500},
        {'name': '西湖', 'lat': 31.0000, 'lon': 121.0000},
    ]
    assert [s['lat'] for s in _dedupe(spots)] == [30.25]


def test_dedupe_treats_name_containment_as_duplicate():
    spots = [
        {'name': '西湖', 'lat': 30.2500, 'lon': 120.1500},
        {'name': '西湖景区', 'lat': 31.0000, 'lon': 121.0000},
        {'name': '灵隐寺', 'lat': 30.2400, 'lon': 120.1400},
    ]
    kept = _dedupe(spots)
    assert [s['name'] for s in kept] == ['西湖', '灵隐寺']


def test_dedupe_ignores_spaces_in_names():
    spots = [
        {'name': '西湖', 'lat': 30.2500, 'lon': 120.1500},
        {'name': '西 湖', 'lat': 31.0000, 'lon': 121.0000},
    ]
    assert len(_dedupe(spots)) == 1


def test_dedupe_drops_nearby_points_with_different_names():
    spots = [
        {'name': '甲景点', 'lat': 30.2500, 'lon': 120.1500},
        {'name': '乙景点', 'lat': 30.2505, 'lon': 120.1505},
    ]
    assert [s['name'] for s in _dedupe(spots)] == ['甲景点']


def test_dedupe_boundary_of_0_001_degree_keeps_both():
    spots = [
        {'name': '甲景点', 'lat': 30.2500, 'lon': 120.1500},
        {'name': '乙景点', 'lat': 30.2510, 'lon': 120.1500},
    ]
    assert len(_dedupe(spots)) == 2


def test_dedupe_keeps_spots_without_coordinates():
    spots = [
        {'name': '甲景点'},
        {'name': '乙景点'},
        {'name': None, 'lat': 30.1, 'lon': 120.1},
    ]
    kept = _dedupe(spots)
    assert [s['name'] for s in kept] == ['甲景点', '乙景点', None]


def test_dedupe_ignores_broken_coordinates():
    spots = [
        {'name': '甲景点', 'lat': 'oops', 'lon': 120.1500},
        {'name': '乙景点', 'lat': None, 'lon': None},
    ]
    assert len(_dedupe(spots)) == 2


def test_dedupe_returns_first_occurrence():
    spots = [
        {'name': '甲景点', 'lat': 30.2500, 'lon': 120.1500},
        {'name': '乙景点', 'lat': 30.2501, 'lon': 120.1501},
    ]
    kept = _dedupe(spots)
    assert len(kept) == 1
    assert kept[0]['name'] == '甲景点'
