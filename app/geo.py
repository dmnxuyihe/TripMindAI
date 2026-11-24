"""WGS-84 / GCJ-02 坐标转换。

高德返回的是 GCJ-02（国测局加密坐标），而 OpenStreetMap 及大多数开源底图使用
WGS-84。把 GCJ-02 坐标直接画在 OSM 上，在中国境内会偏移约 300～700 米，肉眼可辨，
因此需要转换后再上图；同时保留原始 GCJ-02 坐标，供“在高德地图查看”链接使用。

算法为公开的 GCJ-02 加偏公式的逆运算：先用正算得到偏差量，再从 GCJ 坐标里减掉，
迭代两轮把残差压到亚米级。
"""
from __future__ import annotations

import math

_A = 6378245.0                      # 克拉索夫斯基椭球长半轴
_EE = 0.00669342162296594323         # 偏心率平方
_PI = math.pi


def out_of_china(lat: float, lon: float) -> bool:
    """粗略判断是否在加偏范围之外（境外不做偏移）。"""
    return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * _PI) + 20.0 * math.sin(2.0 * x * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * _PI) + 40.0 * math.sin(y / 3.0 * _PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * _PI) + 320 * math.sin(y * _PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * _PI) + 20.0 * math.sin(2.0 * x * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * _PI) + 40.0 * math.sin(x / 3.0 * _PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * _PI) + 300.0 * math.sin(x / 30.0 * _PI)) * 2.0 / 3.0
    return ret


def _delta(lat: float, lon: float) -> tuple[float, float]:
    d_lat = _transform_lat(lon - 105.0, lat - 35.0)
    d_lon = _transform_lon(lon - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * _PI
    magic = math.sin(rad_lat)
    magic = 1 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrt_magic) * _PI)
    d_lon = (d_lon * 180.0) / (_A / sqrt_magic * math.cos(rad_lat) * _PI)
    return d_lat, d_lon


def wgs84_to_gcj02(lat: float, lon: float) -> tuple[float, float]:
    """WGS-84 → GCJ-02。"""
    lat, lon = float(lat), float(lon)
    if out_of_china(lat, lon):
        return lat, lon
    d_lat, d_lon = _delta(lat, lon)
    return round(lat + d_lat, 6), round(lon + d_lon, 6)


def gcj02_to_wgs84(lat: float, lon: float, iterations: int = 2) -> tuple[float, float]:
    """GCJ-02 → WGS-84（迭代逼近，默认两轮，残差 < 0.5 m）。"""
    lat, lon = float(lat), float(lon)
    if out_of_china(lat, lon):
        return lat, lon
    wgs_lat, wgs_lon = lat, lon
    for _ in range(max(1, iterations)):
        gcj_lat, gcj_lon = wgs84_to_gcj02(wgs_lat, wgs_lon)
        wgs_lat += lat - gcj_lat
        wgs_lon += lon - gcj_lon
    return round(wgs_lat, 6), round(wgs_lon, 6)


def add_wgs84_fields(point: dict) -> dict:
    """给含 GCJ-02 坐标的字典补上 wgs_lat / wgs_lon（原地修改并返回）。

    没有坐标或坐标非法的点原样返回，不补字段，避免前端把缺失坐标当成 0。
    """
    try:
        lat = float(point['lat'])
        lon = float(point['lon'])
    except (KeyError, TypeError, ValueError):
        return point
    wgs_lat, wgs_lon = gcj02_to_wgs84(lat, lon)
    point['wgs_lat'] = wgs_lat
    point['wgs_lon'] = wgs_lon
    point['coord_system'] = 'gcj02'
    return point
