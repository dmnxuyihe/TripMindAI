"""行程时间排程：把「景点个数装箱」改成「时间预算装箱」。

原来的多日分组只按景点个数平均分（容量 = ceil(总数/天数)），不看游览时长与交通，
于是会出现「一天 8 个景点、游览 12 小时」这种人类做不到的行程。

本模块用三层约束把它拉回现实：
1. 每个景点按类型给一个游览时长（园林 1.5h、博物馆 2h、商业街 0.8h…）；
2. 相邻景点之间按距离估算交通时间（≤2.5km 步行 4.5km/h，否则驾车 18km/h + 5 分钟）；
3. 每天有可用时间窗（默认 09:00–18:00）和节奏上限（休闲 3 个 / 6h），
   装不下的景点进入 unscheduled，而不是硬塞。
"""
from __future__ import annotations

import math

# 节奏预设：影响每日景点上限与时间预算
PACE_PRESETS = {
    'relaxed': {'label': '休闲', 'max_spots': 3, 'budget_hours': 6.0},
    'normal': {'label': '标准', 'max_spots': 4, 'budget_hours': 7.5},
    'packed': {'label': '紧凑', 'max_spots': 5, 'budget_hours': 8.5},
}
DEFAULT_PACE = 'relaxed'
DEFAULT_DAY_START = '09:00'
DEFAULT_DAY_END = '18:00'
LUNCH_MINUTES = 60
LUNCH_AFTER = 11 * 60            # 11:00 之后才考虑安排午饭
WALK_SPEED_KMH = 4.5             # 步行速度
DRIVE_SPEED_KMH = 18.0           # 市内驾车平均速度（含拥堵）
DRIVE_OVERHEAD_MIN = 5           # 上下车/找停车位
WALK_MAX_KM = 2.5                # 超过这个距离就不建议步行

# 景点类型 → 建议游览时长（小时）。命中越靠前的越优先。
VISIT_HOURS = (
    (('博物馆', '美术馆', '展览馆', '纪念馆'), 2.0),
    (('山', '风景区', '森林公园', '地质公园'), 3.5),
    (('湖', '湿地'), 2.0),
    (('园林', '公园', '植物园'), 1.5),
    (('古镇', '古街', '历史文化街区'), 1.5),
    (('寺', '庙', '教堂', '道观'), 1.0),
    (('商业街', '步行街', '购物'), 0.8),
)
DEFAULT_VISIT_HOURS = 1.5


def _haversine(a: dict, b: dict) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (float(a['lat']), float(a['lon']),
                                               float(b['lat']), float(b['lon'])))
    t = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(t)))


def visit_hours(spot: dict) -> float:
    """按景点分类估算游览时长；没有可比对的关键词时回落到景点自带时长。"""
    text = ' '.join(str(t) for t in (spot.get('tags') or [])) + ' ' + str(spot.get('name') or '')
    for keywords, hours in VISIT_HOURS:
        if any(word in text for word in keywords):
            return hours
    try:
        return float(spot.get('duration_hours') or DEFAULT_VISIT_HOURS)
    except (TypeError, ValueError):
        return DEFAULT_VISIT_HOURS


def travel_minutes(a: dict | None, b: dict) -> tuple[int, str]:
    """估算两点间交通时间，返回（分钟，方式）。"""
    if not a:
        return 0, '起点'
    distance = _haversine(a, b)
    if distance <= WALK_MAX_KM:
        minutes = distance / WALK_SPEED_KMH * 60
        mode = '步行'
    else:
        minutes = distance / DRIVE_SPEED_KMH * 60 + DRIVE_OVERHEAD_MIN
        mode = '驾车'
    return max(5, int(round(minutes / 5.0)) * 5), mode


def _parse_hm(value: str) -> int:
    try:
        hour, minute = str(value).split(':')[:2]
        return max(0, min(24 * 60, int(hour) * 60 + int(minute)))
    except (TypeError, ValueError):
        return 9 * 60


def _fmt(minutes: int) -> str:
    minutes = max(0, int(minutes))
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _plan_day(spots, start, end, budget_minutes, max_spots, center=None):
    """按时间窗把一天的景点装进去，返回（已排景点、时间轴、负荷、剩余景点）。"""
    cursor = start
    placed, timeline, leftover = [], [], []
    visit_total = travel_total = 0
    lunch_done = False
    previous = center if center else None

    for index, spot in enumerate(spots):
        if len(placed) >= max_spots:
            leftover = spots[index:]
            break
        leg, mode = travel_minutes(previous, spot)
        arrive = cursor + leg
        hours = visit_hours(spot)
        duration = int(round(hours * 60))

        # 午饭：如果这趟游览会跨过中午，就在它之前安排 1 小时午餐
        if not lunch_done and arrive >= LUNCH_AFTER and arrive + duration > 12 * 60 + 30:
            lunch_at = max(arrive, 12 * 60)
            if lunch_at + LUNCH_MINUTES + duration > end:
                leftover = spots[index:]
                break
            timeline.append({'kind': 'meal', 'start': _fmt(lunch_at),
                             'end': _fmt(lunch_at + LUNCH_MINUTES), 'label': '午餐 + 休息'})
            cursor = lunch_at + LUNCH_MINUTES
            lunch_done = True
            arrive = cursor + leg

        if arrive + duration > end or (arrive + duration - start) > budget_minutes:
            leftover = spots[index:]
            break

        if leg:
            timeline.append({'kind': 'travel', 'start': _fmt(cursor), 'end': _fmt(arrive),
                             'label': f'{mode}前往 {spot["name"]}', 'minutes': leg, 'mode': mode})
            travel_total += leg
        timeline.append({'kind': 'visit', 'start': _fmt(arrive), 'end': _fmt(arrive + duration),
                         'label': spot['name'], 'minutes': duration, 'hours': round(duration / 60, 1)})
        visit_total += duration
        cursor = arrive + duration
        if cursor >= LUNCH_AFTER:
            lunch_done = True  # 已经过了午饭时段，不再插入
        placed.append(spot)
        previous = spot

    load = {
        'visit_hours': round(visit_total / 60, 1),
        'travel_hours': round(travel_total / 60, 1),
        'budget_hours': round(budget_minutes / 60, 1),
        'used_hours': round((visit_total + travel_total) / 60, 1),
        'spare_hours': round(max(0, budget_minutes - visit_total - travel_total) / 60, 1),
        'spot_count': len(placed),
    }
    return placed, timeline, load, leftover


def apply_schedule(plan: dict, pace: str = DEFAULT_PACE,
                   day_start: str = DEFAULT_DAY_START,
                   day_end: str = DEFAULT_DAY_END,
                   extra_unscheduled=()) -> dict:
    """给已生成的分日行程套上时间表，装不下的景点进入 unscheduled。"""
    preset = PACE_PRESETS.get(pace) or PACE_PRESETS[DEFAULT_PACE]
    start, end = _parse_hm(day_start), _parse_hm(day_end)
    budget = min(int(preset['budget_hours'] * 60), max(60, end - start))
    max_spots = int(preset['max_spots'])
    center = plan.get('center') or None

    pool = []
    for day in plan.get('daily') or []:
        pool.extend(day.get('spots') or [])

    scheduled_days = []
    leftovers = list(extra_unscheduled)
    for day in plan.get('daily') or []:
        candidates = [s for s in (day.get('spots') or []) if s in pool]
        for spot in candidates:
            if spot in pool:
                pool.remove(spot)
        placed, timeline, load, overflow = _plan_day(candidates, start, end, budget, max_spots, center)
        leftovers.extend(overflow)
        scheduled_days.append({'placed': placed, 'timeline': timeline, 'load': load})

    def rebuild(placed):
        return _plan_day(placed, start, end, budget, max_spots, center)

    # 第二遍：落选景点直接塞进还有余量的天
    for spot in list(leftovers):
        for index, day in enumerate(scheduled_days):
            if day['load']['spot_count'] >= max_spots:
                continue
            placed, timeline, load, _ = rebuild((day['placed'] or []) + [spot])
            if len(placed) == len(day['placed']) + 1:
                scheduled_days[index] = {'placed': placed, 'timeline': timeline, 'load': load}
                leftovers.remove(spot)
                break

    # 第三遍：换出补位——先换进一个落选景点，再把被换出的放进别的天。
    # 只有「总排入数增加」才接受，因此不会让结果变差；顺序固定，结果可复现。
    for _round in range(3):
        progressed = False
        for spot in list(leftovers):
            if progressed:
                break
            for index, day in enumerate(scheduled_days):
                if progressed:
                    break
                if day['load']['spot_count'] < 1:
                    continue
                for victim in list(day['placed']):
                    rest = [s for s in day['placed'] if s is not victim]
                    placed, timeline, load, _ = rebuild(rest + [spot])
                    if len(placed) != len(rest) + 1:
                        continue
                    for other_index, other in enumerate(scheduled_days):
                        if other_index == index or other['load']['spot_count'] >= max_spots:
                            continue
                        moved, moved_timeline, moved_load, _ = rebuild((other['placed'] or []) + [victim])
                        if len(moved) != len(other['placed']) + 1:
                            continue
                        scheduled_days[index] = {'placed': placed, 'timeline': timeline, 'load': load}
                        scheduled_days[other_index] = {'placed': moved,
                                                       'timeline': moved_timeline,
                                                       'load': moved_load}
                        leftovers.remove(spot)
                        progressed = True
                        break
                    if progressed:
                        break

    total_scheduled = 0
    for day, scheduled in zip(plan.get('daily') or [], scheduled_days):
        day['spots'] = scheduled['placed']
        day['timeline'] = scheduled['timeline']
        day['day_load'] = scheduled['load']
        day['distance_km'] = round(_route_distance(scheduled['placed'], center), 2)
        day['duration_hours'] = scheduled['load']['visit_hours']
        if scheduled['placed']:
            day['theme'] = day.get('theme') or '精选路线'
        total_scheduled += len(scheduled['placed'])

    # 容量账本：把「总共需要多少小时 / 现在有多少小时」算给用户看，
    # 让"排不下"成为可解释的结论，而不是系统悄悄少给几个景点。
    day_count = len(plan.get('daily') or [])
    per_day_budget = preset['budget_hours']
    scheduled_hours = sum(d['load'].get('used_hours', 0) for d in scheduled_days)
    pending_visit = sum(visit_hours(s) for s in leftovers)
    pending_travel = 0.2 * len(leftovers)          # 每段预留约 12 分钟
    required_hours = scheduled_hours + pending_visit + pending_travel
    available_hours = day_count * per_day_budget
    recommended_days = max(1, math.ceil(required_hours / per_day_budget)) if per_day_budget else day_count

    plan['pace'] = pace
    plan['pace_label'] = preset['label']
    plan['day_window'] = f'{day_start}–{day_end}'
    plan['daily_max_spots'] = max_spots
    plan['spot_count'] = total_scheduled
    plan['total_distance_km'] = round(sum(d.get('distance_km') or 0 for d in plan.get('daily') or []), 2)
    plan['unscheduled'] = [{'name': s.get('name'), 'reason': '超出每日时间预算'} for s in leftovers]
    plan['capacity'] = {
        'required_hours': round(required_hours, 1),
        'available_hours': round(available_hours, 1),
        'scheduled_hours': round(scheduled_hours, 1),
        'recommended_days': recommended_days,
        'total_spots': total_scheduled + len(leftovers),
        'scheduled_spots': total_scheduled,
        'unscheduled_spots': len(leftovers),
    }
    if leftovers:
        plan['capacity_note'] = (
            f'{preset["label"]}节奏下每天最多 {max_spots} 个景点、约 {per_day_budget:g} 小时'
            f'（时间窗 {day_start}–{day_end}）。本次共 {total_scheduled + len(leftovers)} 个景点，'
            f'连游览带交通约需 {required_hours:.1f} 小时，当前 {day_count} 天可用 {available_hours:.1f} 小时；'
            f'已排入 {total_scheduled} 个，另有 {len(leftovers)} 个排不下')
        if required_hours <= available_hours:
            plan['capacity_note'] += (f'（可用时长够，但受每日 {max_spots} 个景点上限与时间窗限制，'
                                      '零散余量拼不出完整的一天）')
        plan['capacity_note'] += f'；按这个节奏建议至少安排 {recommended_days} 天。'
    else:
        plan['capacity_note'] = (
            f'{preset["label"]}节奏下每天最多 {max_spots} 个景点、约 {per_day_budget:g} 小时'
            f'（时间窗 {day_start}–{day_end}），本次全部景点均已排入，'
            f'共用 {scheduled_hours:.1f} 小时（可用 {available_hours:.1f} 小时）。')
    return plan


def _route_distance(spots, center) -> float:
    if not spots:
        return 0.0
    total = _haversine(center, spots[0]) if center else 0.0
    total += sum(_haversine(spots[i], spots[i + 1]) for i in range(len(spots) - 1))
    return total
