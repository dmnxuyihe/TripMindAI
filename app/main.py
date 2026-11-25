"""FastAPI app factory: 前端、对话、行程、算法、缺陷跟踪。"""
from __future__ import annotations
import json
import logging
import os
import re
import queue
import threading
import time
from datetime import timedelta, timezone
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import case, func, select, text
from .config import Settings
from .agent import AgentError, run_agent
from .amap import MapError, geocode, reverse_geocode
from .itinerary import DEFAULT_DAY_END, DEFAULT_DAY_START, _unscheduled_entry, apply_schedule
from .legs import prefetch as prefetch_legs
from .geo import add_wgs84_fields


def plan_distance_km(a, b) -> float:
    """粗略球面距离，用于校验景点是否离行程城市太远。"""
    import math
    lat1, lon1, lat2, lon2 = map(math.radians, (float(a['lat']), float(a['lon']),
                                               float(b['lat']), float(b['lon'])))
    t = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(t)))
from .dynamic_planning import build_live_plan, benchmark_live
from .planning import comparison_from_db
from .models import Attraction, ChatMessage, Conversation, Defect, Itinerary, utcnow
from .storage import list_cities, make_engine, setup_database

STATIC = Path(__file__).parent / 'static'


class ChatInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=36)
    model: str | None = Field(default=None, max_length=80)
    clustering: str = 'kmeans'
    routing: str = 'greedy'


class CreateConversation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default='新对话', min_length=1, max_length=120)
    model: str | None = Field(default=None, max_length=80)


class PlanInput(BaseModel):
    @field_validator('days', mode='before')
    @classmethod
    def _reject_bool_days(cls, value):
        if isinstance(value, bool):
            raise ValueError('旅行天数不能是布尔值')
        return value

    model_config = ConfigDict(extra='forbid')
    city: str = Field(min_length=1, max_length=50)
    pace: str = Field(default='relaxed', max_length=16)
    spot_ids: list[str] = Field(default_factory=list, max_length=16)
    day_start: str = Field(default='09:00', max_length=5)
    lodging: str = Field(default='', max_length=80)
    lodging_lat: float | None = Field(default=None, ge=-90, le=90)
    lodging_lon: float | None = Field(default=None, ge=-180, le=180)
    spot_names: list[str] = Field(default_factory=list, max_length=16)
    origin: str = Field(default='上海', max_length=50)
    days: int = Field(ge=1, le=7)
    clustering: str = 'kmeans'
    routing: str = 'greedy'


class DefectInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=2, max_length=200)
    steps: str = Field(min_length=2, max_length=4000)
    expected: str = Field(min_length=1, max_length=2000)
    actual: str = Field(min_length=1, max_length=2000)
    severity: str = 'minor'


class DefectUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str


class RouteSegment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: tuple[float, float]
    end: tuple[float, float]


class RouteGeometryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    segments: list[RouteSegment] = Field(default_factory=list, max_length=16)

leg_geometry_cache: dict[tuple, tuple] = {}


class ItineraryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default='我的行程', max_length=120)
    plan: dict


class PlanRescheduleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plan: dict


class PlanEditInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plan: dict
    op: str = Field(max_length=16)
    day: int = Field(ge=1, le=7)
    spot_id: str | None = Field(default=None, max_length=80)
    spot: dict | None = None


def plan_shape_error(plan) -> str | None:
    """校验前端回传的行程结构，避免脏数据把重排/微调打崩。"""
    if not isinstance(plan, dict):
        return '行程数据必须是对象'
    daily = plan.get('daily')
    if not isinstance(daily, list) or not daily:
        return '缺少行程数据'
    for day in daily:
        if not isinstance(day, dict):
            return '行程结构不合法（daily 的元素必须是对象）'
        if not isinstance(day.get('spots'), list):
            return '行程结构不合法（每天必须有 spots 列表）'
        for spot in day['spots']:
            if not isinstance(spot, dict):
                return '行程结构不合法（spots 的元素必须是对象）'
    unscheduled = plan.get('unscheduled')
    if unscheduled is not None and not isinstance(unscheduled, list):
        return '行程结构不合法（unscheduled 必须是列表）'
    return None


def iso(dt):
    """统一输出带 UTC 时区的 ISO 8601 时间。

    SQLite 不保存时区，数据库读回的 datetime 是 naive 的；若直接 isoformat()，
    同一资源在“刚创建时”和“重新读取时”会得到带/不带 +00:00 两种格式。
    这里统一按 UTC 补全时区再输出，保证接口的时间表示一致。
    """
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def dump_message(msg):
    return {'id': msg.id, 'role': msg.role, 'content': msg.content,
            'created_at': iso(msg.created_at), 'meta': json.loads(msg.meta_json or '{}')}


def dump_conversation(obj):
    return {'id': obj.id, 'title': obj.title, 'model': obj.model, 'created_at': iso(obj.created_at), 'updated_at': iso(obj.updated_at)}


def chat_message_order():
    """稳定保持用户问题在前、助手回答在后，并兼容已有同时间消息。"""
    role_order = case((ChatMessage.role == 'user', 0), (ChatMessage.role == 'assistant', 1), else_=2)
    return ChatMessage.created_at, role_order, ChatMessage.id


def normalize_choice(value, allowed, label):
    if value not in allowed:
        raise HTTPException(status_code=422, detail=f'{label}只支持：{", ".join(allowed)}')


def create_app(settings: Settings | None = None, engine=None):
    settings = settings or Settings()
    engine = engine or make_engine(settings.database_url)
    Session = setup_database(engine, initialize=settings.initialize_database)
    app = FastAPI(title='智行旅途 Agent', version='3.4.7', docs_url='/api/docs', redoc_url=None)
    app.state.settings = settings
    app.state.session_factory = Session
    app.state.engine = engine

    @app.middleware('http')
    async def log_requests(request, call_next):
        started = time.monotonic()
        response = await call_next(request)
        cost_ms = (time.monotonic() - started) * 1000
        if request.url.path.startswith('/api/'):
            logging.getLogger('tripmind.access').info(
                '%s %s -> %s %.0fms', request.method, request.url.path, response.status_code, cost_ms)
        response.headers['X-Response-Time-ms'] = f'{cost_ms:.0f}'
        return response
    app.mount('/static', StaticFiles(directory=STATIC), name='static')

    @app.get('/')
    def home():
        return FileResponse(STATIC / 'index.html')

    @app.get('/api/health')
    def health():
        with Session() as db:
            db.execute(text('SELECT 1'))
            count = db.scalar(select(func.count(Attraction.id)))
        return {'status': 'ok', 'version': '3.4.7', 'database': 'ok', 'attractions': count,
                'qwen_configured': bool(settings.dashscope_api_key), 'amap_configured': bool(settings.amap_api_key),
                'amap_js_configured': bool(settings.amap_js_key), 'route_mode': 'amap_poi_with_straight_line_algorithm'}

    @app.get('/api/models')
    def models():
        return {'models': [{'id': name, 'name': name, 'configured': bool(settings.dashscope_api_key)}
                           for name in settings.qwen_models],
                'default': settings.default_model if settings.default_model in settings.allowed_models else settings.qwen_models[0]}

    @app.get('/api/geocode/reverse')
    def geocode_reverse(lon: float = Query(ge=-180, le=180), lat: float = Query(ge=-90, le=90)):
        """地图选点后回填地址名；没有 Key 或查不到时返回 name=None，前端退回显示坐标。"""
        if not settings.amap_api_key:
            return {'name': None, 'lon': lon, 'lat': lat, 'note': '未配置 AMAP_WEB_KEY'}
        try:
            info = reverse_geocode(lon, lat, key=settings.amap_api_key,
                                   timeout=max(1.0, min(3.0, settings.amap_timeout_seconds)))
        except MapError as exc:
            return {'name': None, 'lon': lon, 'lat': lat, 'note': str(exc)}
        if not info:
            return {'name': None, 'lon': lon, 'lat': lat, 'note': '该位置没有可用地址'}
        return {**info, 'lon': lon, 'lat': lat}

    @app.get('/api/map-config')
    def map_config():
        """前端地图配置。

        只下发 JS API 的 key（这类 key 本身因域名白名单而可公开），
        绝不返回 Web 服务 key；未配置时前端回退到开源底图方案。
        """
        if settings.amap_js_key:
            return {'provider': 'amap-js', 'key': settings.amap_js_key,
                    'security_code': settings.amap_js_security_code,
                    'note': '高德地图 JS API 2.0'}
        return {'provider': 'none', 'key': '', 'security_code': '',
                'note': '未配置 AMAP_JS_KEY，前端使用开源底图回退方案'}

    @app.get('/api/cities')
    def cities():
        with Session() as db:
            return {'cities': list_cities(db)}

    @app.get('/api/pois')
    def pois(city: str = Query(min_length=1, max_length=50),
             keyword: str = Query(default='旅游景点', max_length=65),
             limit: int = Query(default=16, ge=1, le=20)):
        """返回某城市的候选景点，供用户勾选后再规划。"""
        from .dynamic_planning import discover
        with Session() as db:
            try:
                spots, source = discover(db, settings, city.strip(), keyword.strip() or '旅游景点', limit)
            except (ValueError, MapError) as exc:
                raise HTTPException(422, str(exc)) from exc
        items = []
        for spot in spots[:limit]:
            item = {'id': spot['id'], 'name': spot['name'], 'lat': spot['lat'], 'lon': spot['lon'],
                    'tags': spot.get('tags') or [], 'duration_hours': spot.get('duration_hours', 1.5)}
            add_wgs84_fields(item)
            items.append(item)
        return {'city': city.strip(), 'keyword': keyword.strip() or '旅游景点',
                'source': source, 'spots': items}

    @app.get('/api/attractions')
    def attractions(city: str = Query(min_length=1, max_length=50)):
        from .storage import get_spots
        with Session() as db:
            spots = get_spots(db, city)
        if not spots:
            return {'city': city, 'spots': [], 'found': False,
                    'note': f'本地景点库未收录“{city}”；规划与算法对比请通过高德实时接口查询其他城市。'}
        return {'city': city, 'spots': spots, 'found': True}

    @app.post('/api/plan')
    def plan(payload: PlanInput):
        normalize_choice(payload.clustering, ('kmeans', 'dbscan'), '聚类算法')
        normalize_choice(payload.routing, ('greedy', 'dp'), '路径算法')
        normalize_choice(payload.pace, ('relaxed', 'normal', 'packed'), '节奏')
        if not re.fullmatch(r'([01]?\d|2[0-3]):[0-5]\d', payload.day_start.strip()):
            raise HTTPException(422, '每天出发时间格式应为 HH:MM（例如 09:00）')
        start_hour, start_minute = (int(part) for part in payload.day_start.strip().split(':'))
        if start_hour * 60 + start_minute >= 17 * 60:
            raise HTTPException(422, '每天出发时间太晚（需早于 17:00），否则当天没有可安排的时间窗')
        with Session() as db:
            try:
                return build_live_plan(db, settings, payload.city.strip(), payload.origin.strip(), payload.days,
                    clustering=payload.clustering, routing=payload.routing, pace=payload.pace,
                    spot_ids=payload.spot_ids, spot_names=payload.spot_names,
                    day_start=payload.day_start.strip(), lodging=payload.lodging.strip() or None,
                    lodging_point=({'lat': payload.lodging_lat, 'lon': payload.lodging_lon}
                                   if payload.lodging_lat is not None and payload.lodging_lon is not None
                                   else None))
            except (ValueError, MapError) as exc:
                raise HTTPException(422, str(exc)) from exc

    @app.get('/api/benchmark')
    def benchmark(city: str = Query(min_length=1, max_length=50), days: int = Query(ge=1, le=7)):
        with Session() as db:
            try:
                return benchmark_live(db, settings, city, days)
            except (ValueError, MapError) as exc:
                raise HTTPException(422, str(exc)) from exc

    @app.get('/api/benchmark-fixture')
    def benchmark_fixture(city: str = Query(min_length=1,max_length=50), days: int = Query(ge=1,le=7)):
        from .storage import get_spots
        with Session() as db:
            # 口径与 /api/attractions 保持一致：未收录的城市返回空结果 + 说明，而不是错误码。
            if not get_spots(db, city):
                return {'city': city, 'days': days, 'source': '本地教学测试集（非实时）',
                        'rows': [], 'found': False,
                        'note': f'本地教学测试集未收录“{city}”；该数据集仅含 12 个城市，用于算法确定性回归。'}
            try:
                return {'city':city, 'days':days, 'source':'本地教学测试集（非实时）', 'found': True,
                    'rows':comparison_from_db(db,city,days),
                    'note':'教学固定数据，仅用于测试确定性的算法，不提供给真实 AI Agent 作为实时 POI。'}
            except ValueError as exc:
                raise HTTPException(422,str(exc)) from exc

    def resolve_model(value):
        """请求未指定模型时回落到配置的默认模型，避免写死某个厂商的模型名。"""
        name = (value or '').strip() or settings.default_model
        normalize_choice(name, settings.allowed_models, '模型')
        return name

    @app.get('/api/conversations')
    def conversations():
        with Session() as db:
            objects = db.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(50)).all()
            return {'conversations': [dump_conversation(x) for x in objects]}

    @app.post('/api/conversations', status_code=201)
    def create_conversation(payload: CreateConversation):
        model = resolve_model(payload.model)
        obj = Conversation(id=str(uuid4()), title=payload.title.strip() or '新对话', model=model)
        with Session.begin() as db:
            db.add(obj)
        return dump_conversation(obj)

    @app.get('/api/conversations/{conversation_id}')
    def get_conversation(conversation_id: str):
        with Session() as db:
            obj = db.get(Conversation, conversation_id)
            if obj is None:
                raise HTTPException(404, '对话不存在')
            messages = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(*chat_message_order())).all()
            return {**dump_conversation(obj), 'messages': [dump_message(m) for m in messages]}

    @app.delete('/api/conversations/{conversation_id}')
    def delete_conversation(conversation_id: str):
        with Session.begin() as db:
            obj = db.get(Conversation, conversation_id)
            if obj is None:
                raise HTTPException(404, '对话不存在')
            db.delete(obj)
        return {'deleted': True}

    @app.post('/api/chat')
    def chat(payload: ChatInput):
        model = resolve_model(payload.model)
        message = payload.message.strip()
        if not message:
            raise HTTPException(422, '消息不能为空')
        with Session() as db:
            old_messages = []
            existing = None
            if payload.conversation_id:
                existing = db.get(Conversation, payload.conversation_id)
                if existing is None:
                    raise HTTPException(404, '对话不存在')
                old_messages = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == existing.id)
                    .order_by(*chat_message_order())).all()
            try:
                result = run_agent(db, settings, model,
                    [{'role':m.role, 'content':m.content} for m in old_messages], message)
            except AgentError as exc:
                raise HTTPException(503, str(exc)) from exc
            # Model or tool error must not create a fake answer/history pair.
            convo = existing or Conversation(id=str(uuid4()), title=message[:36], model=model)
            if existing is None:
                db.add(convo)
            else:
                convo.model = model
                convo.updated_at = utcnow()
            user_time = utcnow()
            db.add(ChatMessage(id=str(uuid4()), conversation_id=convo.id, role='user', content=message,
                meta_json='{}', created_at=user_time))
            db.add(ChatMessage(id=str(uuid4()), conversation_id=convo.id, role='assistant', content=result['assistant'],
                meta_json=json.dumps({'plan':result['plan'], 'tool_trace':result['tool_trace'],
                    'provider':'openai-compatible', 'context_note':result.get('context_note')}, ensure_ascii=False), created_at=user_time + timedelta(microseconds=1)))
            db.commit()
            return {'conversation_id': convo.id, 'model':model, 'provider':'openai-compatible', **result}

    @app.post('/api/chat/stream')
    def chat_stream(payload: ChatInput):
        """Stream visible processing stages and answer chunks as NDJSON.

        Stage messages describe observable work only; private model reasoning is
        never requested or exposed.
        """
        model = resolve_model(payload.model)
        message = payload.message.strip()
        if not message:
            raise HTTPException(422, '消息不能为空')

        def encode(event, **data):
            return json.dumps({'event': event, **data}, ensure_ascii=False, default=str) + '\n'

        def generate():
            events = queue.Queue()

            def worker():
                try:
                    with Session() as db:
                        streamed_chars = [0]
                        def push_delta(text):
                            streamed_chars[0] += len(text)
                            events.put({'event':'delta', 'text':text})
                        old_messages = []
                        existing = None
                        if payload.conversation_id:
                            existing = db.get(Conversation, payload.conversation_id)
                            if existing is None:
                                raise ValueError('对话不存在')
                            old_messages = db.scalars(select(ChatMessage).where(
                                ChatMessage.conversation_id == existing.id
                            ).order_by(*chat_message_order())).all()
                        result = run_agent(db, settings, model,
                            [{'role':m.role, 'content':m.content} for m in old_messages], message,
                            progress=lambda text: events.put({'event':'status', 'text':text}),
                            answer_delta=push_delta)
                        convo = existing or Conversation(id=str(uuid4()), title=message[:36], model=model)
                        if existing is None:
                            db.add(convo)
                        else:
                            convo.model = model
                            convo.updated_at = utcnow()
                        user_time = utcnow()
                        db.add(ChatMessage(id=str(uuid4()), conversation_id=convo.id,
                            role='user', content=message, meta_json='{}', created_at=user_time))
                        db.add(ChatMessage(id=str(uuid4()), conversation_id=convo.id,
                            role='assistant', content=result['assistant'], meta_json=json.dumps({
                                'plan':result['plan'], 'tool_trace':result['tool_trace'],
                                'provider':'openai-compatible', 'context_note':result.get('context_note')}, ensure_ascii=False),
                            created_at=user_time + timedelta(microseconds=1)))
                        db.commit()
                        events.put({'event':'result', 'conversation_id':convo.id,
                                    'streamed':streamed_chars[0] > 0, **result})
                except (AgentError, ValueError) as exc:
                    events.put({'event':'error', 'message':str(exc)})
                except Exception:
                    events.put({'event':'error', 'message':'服务处理失败，请稍后重试。'})
                finally:
                    events.put(None)

            threading.Thread(target=worker, daemon=True).start()
            yield encode('status', text='正在分析你的问题…')
            while True:
                item = events.get()
                if item is None:
                    break
                if item['event'] == 'result':
                    item.pop('event', None)
                    answer = item.pop('assistant')
                    # Preserve Markdown while yielding frequently enough for a
                    # natural typing effect after the model finishes its tool loop.
                    if not item.pop('streamed', False):
                        for start in range(0, len(answer), 12):
                            yield encode('delta', text=answer[start:start + 12])
                            time.sleep(0.015)
                    yield encode('done', **item)
                else:
                    yield json.dumps(item, ensure_ascii=False) + '\n'

        return StreamingResponse(generate(), media_type='application/x-ndjson', headers={
            'Cache-Control':'no-cache, no-transform', 'X-Accel-Buffering':'no'})

    @app.post('/api/route-geometry')
    def route_geometry(payload: RouteGeometryInput):
        """返回相邻景点之间的道路折线与通行时间。

        与排程共用 app/legs.py 的缓存：地图上看到的耗时与时间轴一致。
        取不到折线的段返回 path=None，前端按直线处理。
        """
        if not payload.segments:
            return {'legs': [], 'note': '没有需要取轨迹的相邻景点。'}
        if not settings.amap_api_key:
            raise HTTPException(status_code=422, detail='缺少 AMAP_WEB_KEY，无法获取道路轨迹。')
        for seg in payload.segments:
            for lon, lat in (seg.start, seg.end):
                if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                    raise HTTPException(422, '坐标超出范围，无法获取道路轨迹')
        pairs = [({'lon': seg.start[0], 'lat': seg.start[1]},
                  {'lon': seg.end[0], 'lat': seg.end[1]}) for seg in payload.segments]
        fetched = prefetch_legs(pairs, settings=settings,
                                budget_seconds=settings.amap_legs_budget_seconds)
        legs = []
        for index, (start_point, end_point) in enumerate(pairs):
            key = (round(start_point['lon'], 4), round(start_point['lat'], 4),
                   round(end_point['lon'], 4), round(end_point['lat'], 4))
            hit = fetched.get(key)
            if hit and hit[3]:
                legs.append({'index': index, 'path': hit[3], 'minutes': hit[0],
                             'mode': hit[1], 'source': hit[2]})
            else:
                legs.append({'index': index, 'path': None, 'source': 'straight'})
        routed = sum(1 for leg in legs if leg['source'] != 'straight')
        note = f'共 {len(legs)} 段景点间路线，{routed} 段取得高德道路轨迹（耗时与时间轴一致）；其余为直线估计。'
        return {'legs': legs, 'note': note}

    @app.post('/api/itineraries')
    def save_itinerary(payload: ItineraryInput, response: Response):
        plan = payload.plan or {}
        error = plan_shape_error(plan)
        if error:
            raise HTTPException(422, error)
        daily = plan['daily']
        raw_days = plan.get('days')
        try:
            days_value = int(raw_days) if raw_days is not None else len(daily)
        except (TypeError, ValueError):
            raise HTTPException(422, '行程的天数不合法') from None
        if not 1 <= days_value <= 7:
            raise HTTPException(422, '行程的天数应在 1–7 之间')
        body = json.dumps(plan, ensure_ascii=False, default=str)
        # 同一份行程重复保存时复用已有记录，避免点几次生成几条分享链接
        with Session() as db:
            existing = db.scalars(select(Itinerary).where(Itinerary.payload == body)
                                  .order_by(Itinerary.created_at.desc()).limit(1)).first()
            if existing is not None:
                response.status_code = 200
                return {'id': existing.id, 'url': f'/?trip={existing.id}',
                        'title': existing.title, 'reused': True}
        obj = Itinerary(id=str(uuid4()), title=payload.title.strip() or '我的行程',
                        city=str(plan.get('city') or '')[:50], days=days_value,
                        payload=body)
        with Session.begin() as db:
            db.add(obj)
        response.status_code = 201
        return {'id': obj.id, 'url': f'/?trip={obj.id}', 'title': obj.title, 'reused': False}

    @app.get('/api/itineraries')
    def list_itineraries(limit: int = Query(default=30, ge=1, le=100)):
        with Session() as db:
            rows = db.scalars(select(Itinerary).order_by(Itinerary.created_at.desc()).limit(limit)).all()
        return {'itineraries': [{'id': r.id, 'title': r.title, 'city': r.city, 'days': r.days,
                                 'created_at': iso(r.created_at)} for r in rows]}

    @app.get('/api/itineraries/{itinerary_id}')
    def get_itinerary(itinerary_id: str):
        with Session() as db:
            obj = db.get(Itinerary, itinerary_id)
            if obj is None:
                raise HTTPException(404, '行程不存在或已被删除')
            return {'id': obj.id, 'title': obj.title, 'city': obj.city,
                    'created_at': iso(obj.created_at), 'plan': json.loads(obj.payload)}

    @app.delete('/api/itineraries/{itinerary_id}')
    def delete_itinerary(itinerary_id: str):
        with Session.begin() as db:
            obj = db.get(Itinerary, itinerary_id)
            if obj is None:
                raise HTTPException(404, '行程不存在或已被删除')
            db.delete(obj)
        return {'deleted': True}

    @app.post('/api/plan/edit')
    def edit_plan(payload: PlanEditInput):
        """微调：把某个景点从某天移除，或把未排入的景点加进某天，然后重新排程。"""
        plan = payload.plan if isinstance(payload.plan, dict) else {}
        error = plan_shape_error(plan)
        if error:
            raise HTTPException(422, error)
        plan = dict(plan)
        daily = plan['daily']
        index = payload.day - 1
        if index < 0 or index >= len(daily):
            raise HTTPException(422, '天数超出范围')
        day = dict(daily[index])
        spots = list(day.get('spots') or [])
        if payload.op == 'remove':
            target = [s for s in spots if str(s.get('id')) == str(payload.spot_id)]
            if not target:
                raise HTTPException(404, '这一天的行程里没有该景点')
            spots = [s for s in spots if str(s.get('id')) != str(payload.spot_id)]
            entry = _unscheduled_entry(target[0], '手动移除')
            if not isinstance(plan.get('unscheduled'), list):
                plan['unscheduled'] = []
            plan['unscheduled'].insert(0, entry)
        elif payload.op == 'add':
            spot = dict(payload.spot or {})
            if (spot.get('lat') is None or spot.get('lon') is None) and spot.get('name') and settings.amap_api_key:
                # 旧版本的未排入条目可能只有名称，补一次地理编码
                try:
                    point = geocode(str(spot['name']), key=settings.amap_api_key,
                                    timeout=max(1.0, min(3.0, settings.amap_timeout_seconds)))
                except MapError:
                    point = None
                if point:
                    spot.update(point)
            try:
                lat_value = float(spot.get('lat'))
                lon_value = float(spot.get('lon'))
            except (TypeError, ValueError):
                raise HTTPException(422, '景点坐标不合法，无法加入行程') from None
            spot['lat'], spot['lon'] = lat_value, lon_value
            if not (-90 <= lat_value <= 90 and -180 <= lon_value <= 180):
                raise HTTPException(422, '景点坐标超出范围，无法加入行程')
            center = plan.get('center') or {}
            if center.get('lat') is not None and center.get('lon') is not None:
                if plan_distance_km(center, spot) > 150:
                    raise HTTPException(422, '该景点离行程城市太远，无法加入')
            spots.append(spot)
            plan['unscheduled'] = [u for u in (plan.get('unscheduled') or [])
                                   if u.get('name') != spot.get('name')]
        else:
            raise HTTPException(422, '不支持的操作')
        day['spots'] = spots
        daily[index] = day
        plan['daily'] = daily
        plan = apply_schedule(plan, plan.get('pace') or 'relaxed',
                              plan.get('day_start') or DEFAULT_DAY_START,
                              DEFAULT_DAY_END)
        return plan

    @app.post('/api/plan/reschedule')
    def reschedule_plan(payload: PlanRescheduleInput):
        """微调后一次性重排：按前端提交的每日景点分配重新算时间轴，只调用一次。"""
        plan = dict(payload.plan or {})
        error = plan_shape_error(plan)
        if error:
            raise HTTPException(422, error)
        daily = [dict(day) for day in plan['daily']]
        # 同一景点只保留第一次出现，跨天/同天重复都合并到 unscheduled
        seen = set()
        duplicates = []
        for day in daily:
            kept = []
            for spot in day['spots']:
                key = str(spot.get('id') or spot.get('name') or '')
                if key and key in seen:
                    duplicates.append(spot)
                    continue
                if key:
                    seen.add(key)
                kept.append(spot)
            day['spots'] = kept
        plan['daily'] = daily
        if duplicates:
            plan['unscheduled'] = list(plan.get('unscheduled') or [])
            for spot in duplicates:
                entry = _unscheduled_entry(spot, '重复景点已合并')
                if not any(u.get('name') == entry['name'] for u in plan['unscheduled']):
                    plan['unscheduled'].append(entry)
        plan['days'] = len(daily)
        plan = apply_schedule(plan, plan.get('pace') or 'relaxed',
                              plan.get('day_start') or DEFAULT_DAY_START,
                              DEFAULT_DAY_END)
        return plan

    @app.get('/api/defects')
    def defects():
        with Session() as db:
            rows = db.scalars(select(Defect).order_by(Defect.id.desc()).limit(100)).all()
            return {'defects': [dump_defect(x) for x in rows]}

    @app.post('/api/defects', status_code=201)
    def add_defect(payload: DefectInput):
        normalize_choice(payload.severity, ('critical', 'major', 'minor', 'suggestion'), '严重程度')
        with Session.begin() as db:
            obj = Defect(title=payload.title.strip(), steps=payload.steps, expected=payload.expected,
                         actual=payload.actual, severity=payload.severity)
            db.add(obj)
            db.flush()
            output = dump_defect(obj)
        return output

    @app.patch('/api/defects/{defect_id}')
    def update_defect(defect_id: int, payload: DefectUpdate):
        normalize_choice(payload.status, ('open', 'fixed', 'verified', 'wontfix'), '状态')
        with Session.begin() as db:
            obj = db.get(Defect, defect_id)
            if obj is None:
                raise HTTPException(404, '缺陷不存在')
            obj.status = payload.status
            output = dump_defect(obj)
        return output

    @app.get('/api/quality-summary')
    def quality_summary():
        with Session() as db:
            items = db.scalars(select(Defect)).all()
            return {'total_defects': len(items), 'by_status': {s: sum(x.status == s for x in items)
                    for s in ('open', 'fixed', 'verified', 'wontfix')},
                    'by_severity': {s: sum(x.severity == s for x in items)
                    for s in ('critical', 'major', 'minor', 'suggestion')},
                    'warning': '仅根据人工录入的缺陷统计，不代表已完成所有测试或软件质量合格。'}

    return app


def dump_defect(obj):
    return {'id': obj.id, 'title': obj.title, 'steps': obj.steps, 'expected': obj.expected,
            'actual': obj.actual, 'severity': obj.severity, 'status': obj.status,
            'created_at': iso(obj.created_at)}


if os.getenv('TRIPMIND_SKIP_DEFAULT_APP', '0') != '1':
    # 单元/接口测试通过 TRIPMIND_SKIP_DEFAULT_APP=1 关闭模块级实例化，
    # 改用 create_app(settings, engine) 注入临时数据库，避免测试碰到开发库。
    app = create_app()  # 使用 .env 中的 DATABASE_URL 连接本地数据库
