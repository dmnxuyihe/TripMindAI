"""FastAPI app factory: 前端、对话、行程、算法、缺陷跟踪。"""
from __future__ import annotations
import json
import os
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
from datetime import timedelta, timezone
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, select, text
from .config import Settings
from .agent import AgentError, run_agent
from .amap import MapError, walking_route
from .dynamic_planning import build_live_plan, benchmark_live
from .planning import comparison_from_db
from .models import Attraction, ChatMessage, Conversation, Defect, utcnow
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
    model_config = ConfigDict(extra='forbid')
    city: str = Field(min_length=1, max_length=50)
    pace: str = Field(default='relaxed', max_length=16)
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
    app = FastAPI(title='智行旅途 Agent', version='3.2.1', docs_url='/api/docs', redoc_url=None)
    app.state.settings = settings
    app.state.session_factory = Session
    app.state.engine = engine
    app.mount('/static', StaticFiles(directory=STATIC), name='static')

    @app.get('/')
    def home():
        return FileResponse(STATIC / 'index.html')

    @app.get('/api/health')
    def health():
        with Session() as db:
            db.execute(text('SELECT 1'))
            count = db.scalar(select(func.count(Attraction.id)))
        return {'status': 'ok', 'version': '3.2.1', 'database': 'ok', 'attractions': count,
                'qwen_configured': bool(settings.dashscope_api_key), 'amap_configured': bool(settings.amap_api_key),
                'amap_js_configured': bool(settings.amap_js_key), 'route_mode': 'amap_poi_with_straight_line_algorithm'}

    @app.get('/api/models')
    def models():
        return {'models': [{'id': name, 'name': name, 'configured': bool(settings.dashscope_api_key)}
                           for name in settings.qwen_models],
                'default': settings.default_model if settings.default_model in settings.allowed_models else settings.qwen_models[0]}

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
        with Session() as db:
            try:
                return build_live_plan(db, settings, payload.city.strip(), payload.origin.strip(), payload.days,
                    clustering=payload.clustering, routing=payload.routing, pace=payload.pace)
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
        """并发获取相邻景点之间的步行道路折线。

        地图先按直线渲染，本接口返回后再把线替换成真实道路轨迹；
        单段失败或超时就保持直线，不影响行程本身。高德该接口会间歇性卡顿，
        因此每条请求单独限时，并对成功结果做进程内缓存。
        """
        if not settings.amap_api_key:
            raise HTTPException(status_code=422, detail='缺少 AMAP_WEB_KEY，无法获取道路轨迹。')
        segments = payload.segments
        if not segments:
            return {'legs': [], 'note': '没有需要取轨迹的相邻景点。'}

        budget = max(2.0, settings.amap_legs_budget_seconds)
        # 单段限时压到 4 秒：高德偶发 10~20 秒的卡顿直接放弃，用直线兜底
        per_call = max(1.2, min(2.5, settings.amap_timeout_seconds))
        results = [None] * len(segments)

        def cache_key(seg):
            return (round(seg.start[0], 4), round(seg.start[1], 4),
                    round(seg.end[0], 4), round(seg.end[1], 4))

        def fetch(index):
            seg = segments[index]
            key = cache_key(seg)
            cached = leg_geometry_cache.get(key)
            if cached and time.time() - cached[0] < 6 * 3600:
                return cached[1]
            try:
                route = walking_route({'lon': seg.start[0], 'lat': seg.start[1]},
                                      {'lon': seg.end[0], 'lat': seg.end[1]},
                                      key=settings.amap_api_key, timeout=per_call)
            except MapError:
                return None
            if route and route.get('path'):
                leg_geometry_cache[key] = (time.time(), route)
                return route
            return None

        cached_count = sum(1 for seg in segments
                           if leg_geometry_cache.get(cache_key(seg))
                           and time.time() - leg_geometry_cache[cache_key(seg)][0] < 6 * 3600)
        pending = [i for i in range(len(segments))
                   if not (leg_geometry_cache.get(cache_key(segments[i]))
                           and time.time() - leg_geometry_cache[cache_key(segments[i])][0] < 6 * 3600)]
        for i in range(len(segments)):
            if i not in pending:
                results[i] = leg_geometry_cache[cache_key(segments[i])][1]

        if pending:
            pool = ThreadPoolExecutor(max_workers=min(6, len(pending)))
            futures = {pool.submit(fetch, i): i for i in pending}
            try:
                for future in as_completed(futures, timeout=budget):
                    index = futures[future]
                    try:
                        results[index] = future.result()
                    except Exception:
                        results[index] = None
            except TimeoutError:
                pass
            finally:
                # 不等卡住的请求：超时的那几段直接按直线处理
                pool.shutdown(wait=False, cancel_futures=True)

        legs = []
        for index, route in enumerate(results):
            if route and route.get('path'):
                legs.append({'index': index, 'path': route['path'],
                             'distance_m': route.get('distance_m', 0),
                             'duration_s': route.get('duration_s', 0), 'source': 'walking'})
            else:
                legs.append({'index': index, 'path': None, 'source': 'straight'})
        routed = sum(1 for leg in legs if leg['source'] == 'walking')
        if routed == len(legs):
            note = f'共 {len(legs)} 段景点间路线均取得高德步行道路轨迹。'
        else:
            note = f'共 {len(legs)} 段景点间路线，{routed} 段取得高德步行道路轨迹；其余为直线估计。'
        if cached_count:
            note += f'（其中 {cached_count} 段来自缓存）'
        return {'legs': legs, 'note': note}

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
