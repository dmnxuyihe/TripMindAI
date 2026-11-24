"""路段：通行时间 + 道路折线，统一的缓存与降级。"""
from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .amap import MapError, driving_route, walking_route

# (mode, lon1, lat1, lon2, lat2) → (timestamp, minutes, mode_label, source, path)
_CACHE: dict[tuple, tuple] = {}
_TTL_SECONDS = 6 * 3600


def _r(value) -> float:
    return round(float(value), 4)


def key_of(a: dict, b: dict) -> tuple:
    return (_r(a['lon']), _r(a['lat']), _r(b['lon']), _r(b['lat']))


def _haversine_km(a: dict, b: dict) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (float(a['lat']), float(a['lon']),
                                               float(b['lat']), float(b['lon'])))
    t = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(t)))


def estimate_minutes(a: dict | None, b: dict) -> tuple[int, str]:
    if not a:
        return 0, '起点'
    distance = _haversine_km(a, b)
    if distance <= 2.5:
        return max(5, int(round(distance / 4.5 * 60 / 5.0)) * 5), '步行'
    return max(5, int(round((distance / 18.0 * 60 + 5) / 5.0)) * 5), '驾车'


def _from_cache(a: dict, b: dict):
    hit = _CACHE.get(key_of(a, b))
    if hit and time.time() - hit[0] < _TTL_SECONDS:
        return hit
    return None


def fetch_leg(a: dict, b: dict, *, settings, client=None):
    """返回 (分钟, 方式, 来源, 折线或 None)。"""
    hit = _from_cache(a, b)
    if hit:
        return hit[1], hit[2], hit[3], hit[4]
    if settings.amap_api_key:
        distance = _haversine_km(a, b)
        try:
            if distance <= 2.5:
                route = walking_route(a, b, key=settings.amap_api_key,
                                      timeout=max(1.0, settings.amap_timeout_seconds), client=client)
                if route and route.get('duration_s'):
                    minutes = max(1, int(round(route['duration_s'] / 60)))
                    _CACHE[key_of(a, b)] = (time.time(), minutes, '步行', 'walking', route.get('path'))
                    return minutes, '步行', 'walking', route.get('path')
            else:
                route = driving_route(a, b, key=settings.amap_api_key,
                                      timeout=max(1.0, settings.amap_timeout_seconds), client=client)
                if route and route.get('driving_duration_min'):
                    minutes = max(1, int(route['driving_duration_min']))
                    _CACHE[key_of(a, b)] = (time.time(), minutes, '驾车', 'driving', route.get('polyline'))
                    return minutes, '驾车', 'driving', route.get('polyline')
        except MapError:
            pass
    minutes, mode = estimate_minutes(a, b)
    return minutes, mode, 'estimate', None


def prefetch(pairs, *, settings, budget_seconds=5.0, max_workers=4, client=None) -> dict:
    """并发预热一批路段；返回 {key: (分钟, 方式, 来源, 折线)}，超预算的段不返回。"""
    result: dict[tuple, tuple] = {}
    pending = []
    for start, end in pairs:
        hit = _from_cache(start, end)
        if hit:
            result[key_of(start, end)] = (hit[1], hit[2], hit[3], hit[4])
        else:
            pending.append((start, end))
    if not pending:
        return result
    deadline = time.monotonic() + max(1.0, budget_seconds)
    pool = ThreadPoolExecutor(max_workers=min(max_workers, len(pending)))
    futures = {pool.submit(fetch_leg, start, end, settings=settings, client=client): key_of(start, end)
               for start, end in pending}
    try:
        for future in as_completed(futures, timeout=max(1.0, deadline - time.monotonic())):
            try:
                result[futures[future]] = future.result()
            except Exception:
                pass
    except TimeoutError:
        pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return result


def lookup_from(prefetched: dict):
    """给排程用的查表函数，返回 (分钟, 方式)。"""
    def lookup(a: dict, b: dict):
        hit = prefetched.get(key_of(a, b))
        if not hit:
            cached = _from_cache(a, b)
            if cached:
                return cached[1], cached[2]
            return None
        return hit[0], hit[1]
    return lookup


def clear_cache():
    _CACHE.clear()
