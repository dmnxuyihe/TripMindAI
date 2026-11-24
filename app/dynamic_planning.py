"""Live AMap discovery -> PostgreSQL cache -> educational route optimization.
Database's 100 bundled demo spots are never silently substituted for live POIs.
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from hashlib import sha256
from sqlalchemy import delete, select
from .amap import MapError, amap_place_url, search_pois, geocode, driving_route
from .geo import add_wgs84_fields
from .legs import lookup_from, prefetch
from .itinerary import apply_schedule
from .models import PoiCache
from .travel_core import make_plan, benchmark, centroid, haversine


def discover(db, settings, city, keyword='景点', limit=16, *, amap_client=None, refresh=False):
    city, keyword = city.strip()[:50], (keyword.strip() or '景点')[:65]
    if not city:
        raise ValueError('目的地不能为空')
    now = datetime.now(timezone.utc)
    # Cache query is restricted by exact destination and exact keyword.
    rows = db.scalars(select(PoiCache).where(PoiCache.city == city, PoiCache.keyword == keyword)).all()
    if rows and not refresh:
        recent = all(((now - (r.retrieved_at.replace(tzinfo=timezone.utc) if r.retrieved_at.tzinfo is None else r.retrieved_at)).total_seconds() < settings.poi_cache_hours * 3600) for r in rows)
        # 缓存条数少于本次需要的数量时视为未命中，重新取一次（历史上按更小 limit 写过的缓存会由此补全）
        if recent and len(rows) >= limit:
            return [json.loads(row.data_json) for row in rows[:limit]], 'amap_cache'
    if not settings.amap_api_key:
        raise MapError('缺少 AMAP_WEB_KEY；无法为该目的地获取真实景点（实验室示例数据不会冒充高德结果）。')
    points = search_pois(city, keyword=keyword, limit=limit, key=settings.amap_api_key,
                         timeout=settings.amap_timeout_seconds, client=amap_client)
    if not points:
        raise MapError(f'高德未检索到“{city}”的“{keyword}”相关 POI，请尝试城市全称或其他关键词。')
    # Avoid replacing cache when external API fails; commit only successful results.
    db.execute(delete(PoiCache).where(PoiCache.city == city, PoiCache.keyword == keyword))
    for point in points:
        db.add(PoiCache(id=point['id'] + ':' + sha256(f'{city}|{keyword}'.encode()).hexdigest()[:12], city=city,
                        keyword=keyword, name=point['name'], lat=point['lat'], lon=point['lon'],
                        data_json=json.dumps(point, ensure_ascii=False), retrieved_at=now))
    db.commit()
    return points, 'amap_live'


def build_live_plan(db, settings, city, origin, days, interests='', must_visit=None,
                    clustering='kmeans', routing='greedy', *, pace=None, spot_ids=None,
                    spot_names=None, day_start=None, lodging=None, amap_client=None):
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 7:
        raise ValueError('旅行天数必须是 1～7 天')
    if clustering not in ('kmeans', 'dbscan') or routing not in ('greedy', 'dp'):
        raise ValueError('算法仅支持 kmeans/dbscan 和 greedy/dp')
    if not city or len(city) > 50:
        raise ValueError('目的地不能为空且不得超过 50 字')
    city = city.strip()
    origin = (origin or '未指定')[:50]
    # AMap POI keyword searches; no manual city whitelist.
    keyword = '旅游景点'
    # 一次取满 16 个候选：多出来的由时间排程决定是否排入，而不是一开始就少取
    spots, provenance = discover(db, settings, city, keyword, 16, amap_client=amap_client)
    missing_selection = []
    if spot_ids or spot_names:
        by_id = {p['id']: p for p in spots}
        by_name = {p['name']: p for p in spots}
        selected = []
        for want in [str(x) for x in (spot_ids or [])]:
            if want in by_id:
                selected.append(by_id[want])
            else:
                missing_selection.append(want)
        # id 对不上时按名称回退（候选排序或缓存刷新会让 id 与名称错位）
        for name in [str(n).strip() for n in (spot_names or []) if str(n).strip()]:
            if any(p['name'] == name for p in selected):
                continue
            hit = by_name.get(name)
            if hit is None:
                try:
                    extra, _ = discover(db, settings, city, name, 4, amap_client=amap_client)
                except MapError:
                    extra = []
                hit = extra[0] if extra else None
            if hit is not None and hit not in selected:
                selected.append(hit)
        if selected:
            spots = selected
            missing_selection = []
    must_visit = [str(p)[:50] for p in (must_visit or [])[:5] if str(p).strip()]
    # Respect explicitly requested landmarks using additional verified POI lookups.
    for name in must_visit:
        if any(name in p['name'] or p['name'] in name for p in spots):
            continue
        try:
            exact, _ = discover(db, settings, city, name, 4, amap_client=amap_client)
            if exact:
                spots.insert(0, exact[0])
        except MapError:
            pass
    unique = list({p['id']: p for p in spots}.values())[:16]
    center = centroid(unique)
    result = make_plan(city, origin, days, clustering, routing, external_spots=unique, center=center)
    result['data_source'] = '高德地图 POI 实时接口' if provenance == 'amap_live' else '高德地图 POI 缓存'
    result['amap_source'] = provenance
    result['preferences'] = (interests or '')[:200]
    result['selected_count'] = len(spots)

    result['map_note'] = '景点位置来自高德 GCJ-02 坐标，已在响应中附带 wgs_lat/wgs_lon 供开源底图使用；景点之间为直线距离算法估计，不代表道路导航或实时交通。'
    for d in result['daily']:
        for p in d['spots']:
            # 同时保留 GCJ-02（lat/lon，用于高德链接）与 WGS-84（wgs_lat/wgs_lon，用于 OSM 底图）
            add_wgs84_fields(p)
            p['map_url'] = amap_place_url(p)
    result['intercity_route'] = None
    result['intercity_note'] = None
    # 住宿基点：用户填了酒店/住处时，每天从那里出发
    if lodging:
        hotel = None
        try:
            hotel = geocode(lodging, key=settings.amap_api_key,
                            timeout=max(1.0, min(3.0, settings.amap_intercity_budget_seconds)),
                            client=amap_client)
        except MapError:
            hotel = None
        if hotel:
            result['lodging'] = {'name': lodging[:60], **hotel}
            result['center'] = hotel
            result['map_note'] = (result.get('map_note') or '') + ' 每日以住宿地为出发点。'
        else:
            result['lodging'] = None
            result['lodging_note'] = f'住宿地「{lodging[:40]}」未能定位，行程仍以城市中心为起点。'

    # 跨城市道路距离是可选的展示信息，给它独立的时间预算：
    # 地理编码/驾车接口抖动时不拖慢整个规划请求，超时即降级为“仅直线距离”。
    if origin not in ('未指定', city):
        budget = max(1.0, settings.amap_intercity_budget_seconds)
        deadline = time.monotonic() + budget
        per_call_timeout = max(1.2, min(2.5, settings.amap_timeout_seconds, budget))

        def route_timeout():
            return max(1.0, min(per_call_timeout, deadline - time.monotonic()))

        try:
            start = None
            end = None
            if time.monotonic() < deadline:
                start = geocode(origin, key=settings.amap_api_key,
                                timeout=route_timeout(), client=amap_client)
            if start and time.monotonic() < deadline:
                end = geocode(city, key=settings.amap_api_key,
                              timeout=route_timeout(), client=amap_client)
            if start and end and time.monotonic() < deadline:
                route = driving_route(start, end, key=settings.amap_api_key,
                                      timeout=route_timeout(), client=amap_client)
                result['intercity_route'] = {'origin': origin, 'destination': city,
                    'start': add_wgs84_fields({**start, 'name': origin}),
                    'end': add_wgs84_fields({**end, 'name': city}),
                    'straight_km': round(haversine(start, end), 1), **(route or {})}
            if result['intercity_route'] is None:
                result['intercity_note'] = (
                    f'跨城道路数据未在 {budget:g} 秒预算内取得，已省略；'
                    '页面只展示两地直线距离，不代表驾车里程。')
        except MapError:
            result['intercity_note'] = '跨城道路数据获取失败，已省略；页面只展示直线距离。'
    # 用真实通行时间排程：先把当天相邻景点之间的路段一次性取好
    if pace:
        pairs = []
        for day in result.get('daily') or []:
            spots = day.get('spots') or []
            pairs.extend(zip(spots, spots[1:]))
        prefetched = prefetch(pairs, settings=settings,
                              budget_seconds=settings.amap_legs_budget_seconds,
                              client=amap_client)
        apply_schedule(result, pace, day_start or '09:00', '18:00',
                       travel_lookup=lookup_from(prefetched))
    return result


def benchmark_live(db, settings, city, days, *, amap_client=None):
    points, provenance = discover(db, settings, city, '旅游景点', min(16, max(8, days * 3)), amap_client=amap_client)
    return {'city': city, 'days': days, 'source': provenance, 'rows': benchmark(city, days, external_spots=points, center=centroid(points)),
            'note': '算法距离为经纬度直线距离，不能冒充现实道路时间或公里数。'}
