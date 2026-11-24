"""Real AMap POI discovery + optional geocoding/driving, with injectable HTTP client.

No synthetic locations are returned when AMap fails. Coordinates are GCJ-02.
"""
from __future__ import annotations
import time
from urllib.parse import urlencode
import httpx

BASE = 'https://restapi.amap.com'

# 地理编码（地址→坐标）在本机实测为抖动最大的接口（0.4 s ~ 24 s），
# 而城市坐标在一天内不会变化，因此做进程内 TTL 缓存，避免重复的高延迟调用。
GEOCODE_CACHE_TTL_SECONDS = 86400
_GEOCODE_CACHE: dict[str, tuple[float, dict]] = {}


def clear_geocode_cache():
    _GEOCODE_CACHE.clear()


class MapError(Exception):
    pass


def parse_location(value):
    if not isinstance(value, str) or ',' not in value:
        return None
    try:
        lon, lat = (float(x) for x in value.split(',', 1))
        if not (73 <= lon <= 135 and 17 <= lat <= 55):
            return None
        return {'lon': lon, 'lat': lat}
    except (ValueError, TypeError):
        return None


def _get(path: str, params: dict, *, key: str, timeout: float = 12, client=None):
    if not key:
        raise MapError('未配置 AMAP_WEB_KEY，无法实时查询景点或路线。请在 .env 配置高德 Web 服务密钥。')
    try:
        if client is not None:
            response = client.get(BASE + path, params={**params, 'key': key})
        else:
            with httpx.Client(timeout=timeout, follow_redirects=False) as local:
                response = local.get(BASE + path, params={**params, 'key': key})
        response.raise_for_status()
        data = response.json()
        if str(data.get('status')) != '1':
            raise MapError(f'高德接口失败：{str(data.get("info", "unknown"))[:100]}（{data.get("infocode", "")}）')
        return data
    except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise MapError(f'高德网络请求失败：{type(exc).__name__}') from exc
    except ValueError as exc:
        raise MapError('高德返回了无法解析的 JSON') from exc


def search_pois(city: str, *, keyword: str = '景点', limit: int = 16, key: str, timeout: float = 12, client=None):
    city = city.strip()[:50]
    keyword = keyword.strip()[:65] or '景点'
    if not city:
        raise MapError('必须提供目的地城市或区域')
    limit = max(1, min(limit, 25))
    payload = _get('/v5/place/text', {
        'region': city, 'city_limit': 'true', 'keywords': keyword,
        'page_size': min(limit, 25), 'page_num': 1, 'show_fields': 'photos,business', 'output': 'json',
    }, key=key, timeout=timeout, client=client)
    result = []
    ids = set()
    for p in payload.get('pois') or []:
        loc = parse_location(p.get('location'))
        if not loc or not p.get('id') or not p.get('name') or str(p['id']) in ids:
            continue
        ids.add(str(p['id']))
        photos = p.get('photos') if isinstance(p.get('photos'), list) else []
        pic = photos[0].get('url', '') if photos and isinstance(photos[0], dict) else ''
        if not str(pic).startswith('https://'):
            pic = ''
        result.append({
            'id': f'amap:{str(p["id"])[:64]}', 'city': city, 'name': str(p['name'])[:100],
            **loc, 'tags': [str(p.get('type', '')).split(';')[0][:40] or '景点'],
            'description': f"地址：{str(p.get('address') or p.get('adname') or '未提供')[:110]}。来源：高德地图 POI。",
            'address': str(p.get('address') or '')[:150], 'duration_hours': 1.5,
            'photo_url': pic, 'photo_credit': '高德地图 POI', 'photo_source': '',
            'source': 'amap', 'adcode': str(p.get('adcode') or '')[:12]
        })
    return result


def geocode(address: str, *, key: str, timeout=12, client=None, use_cache=True):
    address = address.strip()[:120]
    now = time.monotonic()
    if use_cache:
        hit = _GEOCODE_CACHE.get(address)
        if hit and now - hit[0] < GEOCODE_CACHE_TTL_SECONDS:
            return dict(hit[1])
    data = _get('/v3/geocode/geo', {'address': address, 'output': 'json'}, key=key, timeout=timeout, client=client)
    for obj in data.get('geocodes') or []:
        loc = parse_location(obj.get('location'))
        if loc:
            if use_cache:
                _GEOCODE_CACHE[address] = (now, dict(loc))
            return loc
    return None


def driving_route(start: dict, end: dict, *, key: str, timeout=12, client=None):
    data = _get('/v3/direction/driving', {
        'origin': f'{start["lon"]},{start["lat"]}', 'destination': f'{end["lon"]},{end["lat"]}', 'output': 'json'
    }, key=key, timeout=timeout, client=client)
    paths = (data.get('route') or {}).get('paths') or []
    if not paths:
        return None
    candidate = paths[0]
    try:
        return {'driving_distance_km': round(float(candidate['distance']) / 1000, 1),
                'driving_duration_min': round(float(candidate['duration']) / 60)}
    except (KeyError, ValueError, TypeError):
        return None


def amap_place_url(spot: dict):
    params = urlencode({'position': f'{spot["lon"]},{spot["lat"]}', 'name': spot['name'], 'src': 'tripmind-ai', 'coordinate': 'gaode', 'callnative': 0})
    return 'https://uri.amap.com/marker?' + params
