"""路线与聚类的业务适配层，距离均为大圆距离，不冒充真实公路里程。"""
from __future__ import annotations
from .storage import get_spots
from .travel_core import benchmark, cities_data, make_plan, haversine


def plan_from_db(db, city: str, origin: str, days: int, clustering: str, routing: str):
    spots = get_spots(db, city)
    if not spots:
        raise ValueError(f'暂未收录“{city}”景点；当前版本支持的城市可在左侧规划页选择')
    source = cities_data().get(city)
    center = source['center'] if source else {
        'lat': sum(s['lat'] for s in spots)/len(spots),
        'lon': sum(s['lon'] for s in spots)/len(spots),
    }
    result = make_plan(city, origin, days, clustering, routing, external_spots=spots, center=center)
    result['data_source'] = '本地 PostgreSQL 景点库（演示坐标）'
    origin_city = origin.replace('市', '').strip()
    if origin_city in cities_data():
        a = cities_data()[origin_city]['center']
        result['intercity_route'] = {
            'origin': origin_city, 'destination': city,
            'start': {**a, 'name': origin_city}, 'end': {**center, 'name': city},
            'straight_km': round(haversine(a, center), 1),
        }
    else:
        result['intercity_route'] = None
    result['map_note'] = '路线图为景点坐标直线示意（含已收录城市的跨城直线连线），不是高德真实道路导航；交通方式、用时未计算。'
    return result


def comparison_from_db(db, city: str, days: int):
    spots = get_spots(db, city)
    if not spots:
        raise ValueError(f'未知城市：{city}')
    source = cities_data().get(city)
    center = source['center'] if source else {'lat': spots[0]['lat'], 'lon': spots[0]['lon']}
    return benchmark(city, days, external_spots=spots, center=center)
