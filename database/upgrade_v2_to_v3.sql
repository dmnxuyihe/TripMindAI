-- 已有 V2 数据库只需执行这一份，无需重复导入演示数据。
CREATE TABLE IF NOT EXISTS amap_poi_cache (
 id varchar(80) PRIMARY KEY, city varchar(50) NOT NULL, keyword varchar(70) NOT NULL,
 name varchar(100) NOT NULL, lat double precision NOT NULL, lon double precision NOT NULL,
 data_json text NOT NULL, retrieved_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_amap_poi_cache_city ON amap_poi_cache(city);
CREATE INDEX IF NOT EXISTS ix_amap_poi_cache_keyword ON amap_poi_cache(keyword);

-- v3.4 新增：保存/分享的行程
CREATE TABLE IF NOT EXISTS itineraries (
  id varchar(36) PRIMARY KEY,
  title varchar(120) NOT NULL DEFAULT '未命名行程',
  city varchar(50) NOT NULL DEFAULT '',
  days integer NOT NULL DEFAULT 1,
  payload text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_itineraries_created_at ON itineraries(created_at);
