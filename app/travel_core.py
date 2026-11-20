"""Offline-first itinerary engine: K-means, DBSCAN, greedy and Held-Karp DP.
Distances below are straight-line haversine kilometres, not road-route distances.
"""
from __future__ import annotations
import json
import math
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).parent / 'data' / 'cities.json'

@lru_cache(maxsize=1)
def cities_data():
    return json.loads(DATA_PATH.read_text(encoding='utf-8'))


def haversine(a, b):
    """a and b are dictionaries with lat/lon fields."""
    lat1, lon1, lat2, lon2 = map(math.radians, (float(a['lat']), float(a['lon']), float(b['lat']), float(b['lon'])))
    t = math.sin((lat2 - lat1) / 2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2 - lon1) / 2)**2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(t)))


def centroid(items):
    return {'lat': sum(s['lat'] for s in items)/len(items), 'lon':sum(s['lon'] for s in items)/len(items)}


def kmeans(spots, k, max_iter=50):
    """Deterministic K-means on lat/lon, farthest-first initialization."""
    if not spots: return []
    k = max(1, min(int(k), len(spots)))
    centers = [dict(lat=spots[0]['lat'], lon=spots[0]['lon'])]
    for _ in range(k-1):
        next_spot = max(spots, key=lambda s:min(haversine(s, c) for c in centers))
        centers.append({'lat':next_spot['lat'],'lon':next_spot['lon']})
    labels = [-1] * len(spots)
    for _ in range(max_iter):
        new_labels = [min(range(k),key=lambda i:haversine(s, centers[i])) for s in spots]
        if new_labels == labels: break
        labels = new_labels
        for i in range(k):
            group = [s for s, label in zip(spots, labels) if label == i]
            if group: centers[i] = centroid(group)
    return labels


def dbscan(spots, eps_km=7, min_samples=2):
    """Deterministic density-based spatial clustering. -1 represents noise."""
    n = len(spots)
    labels = [-2] * n
    if not n: return []
    neighborhoods = [[j for j in range(n) if haversine(spots[i],spots[j]) <= eps_km] for i in range(n)]
    cluster = 0
    for i in range(n):
        if labels[i] != -2: continue
        neighbors = neighborhoods[i]
        if len(neighbors) < min_samples:
            labels[i] = -1
            continue
        labels[i] = cluster
        queue = list(neighbors)
        seen = set(queue)
        index = 0
        while index < len(queue):
            j = queue[index]; index += 1
            if labels[j] == -1: labels[j] = cluster
            if labels[j] != -2: continue
            labels[j] = cluster
            if len(neighborhoods[j]) >= min_samples:
                for p in neighborhoods[j]:
                    if p not in seen:
                        seen.add(p); queue.append(p)
        cluster += 1
    return labels


def route_distance(spots, start=None):
    if not spots: return 0.0
    total = haversine(start,spots[0]) if start else 0.0
    total += sum(haversine(spots[i], spots[i+1]) for i in range(len(spots)-1))
    return total


def greedy_route(spots, start):
    remaining = list(spots)
    result = []
    current = start
    while remaining:
        best = min(remaining, key=lambda s: (haversine(current,s),s['id']))
        result.append(best)
        remaining.remove(best)
        current = best
    return result


def dp_route(spots, start, max_n=12):
    """Held-Karp shortest open Hamilton path with a fixed start, O(n²2^n)."""
    n = len(spots)
    if n > max_n: raise ValueError(f'动态规划最多支持 {max_n} 个景点/天（防止指数复杂度失控）')
    if n < 2: return list(spots)
    costs = [[haversine(a,b) for b in spots] for a in spots]
    dp = {}
    for j in range(n): dp[(1 << j,j)] = (haversine(start,spots[j]),(j,))
    for mask in range(1,1 << n):
        for j in range(n):
            if not mask & (1<<j) or (mask,j) not in dp: continue
            cost,path = dp[(mask,j)]
            for k in range(n):
                if mask & (1<<k): continue
                new = (mask | 1<<k,k)
                cand = (cost+costs[j][k],path+(k,))
                if new not in dp or cand[0] < dp[new][0]-1e-9: dp[new] = cand
    full=(1<<n)-1
    best=min((dp[(full,j)] for j in range(n)),key=lambda v:v[0])
    return [spots[j] for j in best[1]]


def choose_days(spots, days, clustering='kmeans'):
    """Assign stops to days with a balanced, cluster-informed strategy."""
    days = int(days)
    if days < 1 or days > 7: raise ValueError('测试版支持 1～7 天的旅行规划')
    if not spots: raise ValueError('当前城市没有可用景点')
    if clustering not in ('kmeans','dbscan'): raise ValueError('聚类算法只支持 kmeans / dbscan')
    n = len(spots)
    k = min(days,n)
    labels = kmeans(spots,k) if clustering == 'kmeans' else dbscan(spots,eps_km=7,min_samples=2)
    groups = {}
    for s,label in zip(spots,labels):
        group_key=label if label >= 0 else f'noise-{s["id"]}'
        groups.setdefault(group_key,[]).append(s)
    # Distribute large clusters across bins; prefer spatial affinity, penalize overfull bins.
    ordered = sorted(groups.values(), key=lambda g:(-len(g), min(x['name'] for x in g)))
    buckets=[[] for _ in range(k)]
    capacity=math.ceil(n/k)
    for group in ordered:
        group=sorted(group,key=lambda x:(x['lon'],x['lat']))
        for s in group:
            candidates=[i for i,b in enumerate(buckets) if len(b)<capacity]
            if not candidates: candidates=list(range(k))
            def score(i):
                b=buckets[i]
                geo=min((haversine(s,p) for p in b), default=0)
                # Strongly avoid empty bins until each has one stop.
                return (0 if b else -100, len(b)*4 + geo*0.18, i)
            chosen=min(candidates,key=score)
            buckets[chosen].append(s)
    # When days > number of sights, empty days are reported as free days.
    buckets += [[] for _ in range(days-k)]
    return buckets, labels


def make_plan(city, origin, days, clustering='kmeans', routing='dp', external_spots=None, center=None):
    data=cities_data()
    if not isinstance(city,str) or not city.strip(): raise ValueError('请提供目的地')
    if city in data:
        source=data[city]
        spots = [dict(s) for s in (external_spots if external_spots is not None else source['spots'])]
        center=center or source['center']
        province=source['province']
        data_source='内置示例数据' if external_spots is None else '高德 POI 数据'
    elif external_spots is not None and center is not None:
        spots=[dict(s) for s in external_spots]
        province='实时查询'
        data_source='高德 POI 数据'
    else:
        raise ValueError(f'“{city}”不在离线示例城市中，请配置高德 API Key 以查询国内其他城市')
    if routing not in ('greedy','dp'): raise ValueError('路线优化算法只支持 greedy / dp')
    if not isinstance(days,int) or isinstance(days,bool) or not 1<=days<=7:
        raise ValueError('天数必须是 1～7 的整数')
    if len(spots)>16: spots=spots[:16]
    day_groups, labels = choose_days(spots,days,clustering)
    itinerary=[]
    for i,group in enumerate(day_groups,1):
        ordered=(greedy_route(group,center) if routing=='greedy' else dp_route(group,center)) if group else []
        itinerary.append({'day':i,'theme':(ordered[0]['tags'][0]+' · 精选路线') if ordered else '自由活动','spots':ordered,'distance_km':round(route_distance(ordered,center),2),'duration_hours':round(sum(s.get('duration_hours',1.5) for s in ordered),1)})
    return {'city':city,'origin':origin or '未设置','province':province,'days':days,'clustering':clustering,'routing':routing,'data_source':data_source,'daily':itinerary,
            'center':center,'spot_count':sum(len(day['spots']) for day in itinerary),'cluster_count':len({x for x in labels if x!=-1}),'noise_count':sum(x==-1 for x in labels),
            'total_distance_km':round(sum(x['distance_km'] for x in itinerary),2),'distance_note':'直线距离之和用于算法比较；不是公路里程或实际通勤时长。','travel_route':None}


def benchmark(city,days,external_spots=None,center=None):
    rows=[]
    for cluster in ('kmeans','dbscan'):
        for routing in ('greedy','dp'):
            p=make_plan(city,'测试出发地',days,cluster,routing,external_spots,center)
            rows.append({'clustering':cluster,'routing':routing,'distance_km':p['total_distance_km'],'cluster_count':p['cluster_count'],'noise_count':p['noise_count'],'spot_count':p['spot_count']})
    return rows


