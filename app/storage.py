"""初始化数据库和查询景点的简单存储层。"""
from __future__ import annotations
import json
from pathlib import Path
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from .models import Attraction, Base

SEED_FILE = Path(__file__).parent / 'data' / 'cities.json'


def make_engine(url: str):
    if url.startswith('sqlite:///:memory:'):
        return create_engine(url, connect_args={'check_same_thread': False}, poolclass=StaticPool)
    if url.startswith('sqlite:'):
        return create_engine(url, connect_args={'check_same_thread': False})
    return create_engine(url, pool_pre_ping=True)


def setup_database(engine, initialize=True):
    """创建数据库会话工厂，并根据开关决定是否初始化表结构。

    初始化操作是幂等的：只创建缺失的数据表，并且仅在景点表为空时
    导入内置景点；不会删除数据表，也不会清空或覆盖已有记录。
    """
    if initialize:
        Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    if initialize:
        with Session.begin() as db:
            if db.scalar(select(func.count(Attraction.id))) == 0:
                data = json.loads(SEED_FILE.read_text(encoding='utf-8'))
                for city, entry in data.items():
                    for spot in entry['spots']:
                        db.add(Attraction(id=spot['id'], city=city, province=entry['province'],
                            name=spot['name'], lat=spot['lat'], lon=spot['lon'],
                            tags_json=json.dumps(spot['tags'], ensure_ascii=False),
                            description=spot['description'], duration_hours=spot.get('duration_hours', 1.5),
                            photo_url=spot.get('photo_url', ''), photo_credit=spot.get('photo_credit',''), photo_source=spot.get('photo_source','')))
    return Session


def list_cities(db):
    rows = db.execute(select(Attraction.city, func.count(Attraction.id)).group_by(Attraction.city).order_by(Attraction.city)).all()
    return [{'city': city, 'count': count} for city, count in rows]


def get_spots(db, city):
    items = db.scalars(select(Attraction).where(Attraction.city == city).order_by(Attraction.id)).all()
    return [dict(id=s.id, name=s.name, lat=s.lat, lon=s.lon, tags=json.loads(s.tags_json),
        description=s.description, duration_hours=s.duration_hours, photo_url=s.photo_url,
        photo_credit=s.photo_credit, photo_source=s.photo_source) for s in items]
