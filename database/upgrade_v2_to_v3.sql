-- 已有 V2 数据库只需执行这一份，无需重复导入演示数据。
CREATE TABLE IF NOT EXISTS amap_poi_cache (
 id varchar(80) PRIMARY KEY, city varchar(50) NOT NULL, keyword varchar(70) NOT NULL,
 name varchar(100) NOT NULL, lat double precision NOT NULL, lon double precision NOT NULL,
 data_json text NOT NULL, retrieved_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_amap_poi_cache_city ON amap_poi_cache(city);
CREATE INDEX IF NOT EXISTS ix_amap_poi_cache_keyword ON amap_poi_cache(keyword);
