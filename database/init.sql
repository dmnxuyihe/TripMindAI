-- 智行旅途 PostgreSQL 15+ 初始化脚本，连接至 travel_agent 数据库后执行。
-- 幂等执行：表存在不重建，景点重复则跳过；不会删除聊天和缺陷记录。
BEGIN;
CREATE TABLE IF NOT EXISTS conversations (
  id varchar(36) PRIMARY KEY, title varchar(120) NOT NULL,
  model varchar(80) NOT NULL DEFAULT 'qwen-plus',
  created_at timestamptz NOT NULL DEFAULT NOW(), updated_at timestamptz NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS chat_messages (
  id varchar(36) PRIMARY KEY,
  conversation_id varchar(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role varchar(16) NOT NULL, content text NOT NULL,
  meta_json text NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_chat_messages_conversation_id ON chat_messages(conversation_id);
CREATE INDEX IF NOT EXISTS ix_conversations_updated ON conversations(updated_at);
CREATE TABLE IF NOT EXISTS attractions (
  id varchar(80) PRIMARY KEY, city varchar(50) NOT NULL,
  province varchar(50) NOT NULL, name varchar(100) NOT NULL,
  lat double precision NOT NULL, lon double precision NOT NULL,
  tags_json text NOT NULL DEFAULT '[]', description text NOT NULL DEFAULT '',
  duration_hours double precision NOT NULL DEFAULT 1.5,
  photo_url text NOT NULL DEFAULT '', photo_credit text NOT NULL DEFAULT '', photo_source text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_attractions_city ON attractions(city);
CREATE TABLE IF NOT EXISTS defects (
  id serial PRIMARY KEY, title varchar(200) NOT NULL,
  steps text NOT NULL, expected text NOT NULL, actual text NOT NULL,
  severity varchar(20) NOT NULL DEFAULT 'minor',
  status varchar(20) NOT NULL DEFAULT 'open',
  created_at timestamptz NOT NULL DEFAULT NOW()
);
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('杭州-01','杭州','浙江省','西湖',30.25,120.1495,'["湖景", "经典"]','杭州代表性湖景，适合沿湖慢行和欣赏城市山水。',1.5,'https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a9/West_Lake_-_Hangzhou%2C_China.jpg/960px-West_Lake_-_Hangzhou%2C_China.jpg','Louisa Salazar / CC BY-SA 3.0 / Wikimedia Commons','https://commons.wikimedia.org/wiki/File:West_Lake_-_Hangzhou,_China.jpg') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('杭州-02','杭州','浙江省','断桥残雪',30.26,120.1495,'["湖景", "历史"]','位于西湖北部，适合结合白堤徒步。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('杭州-03','杭州','浙江省','雷峰塔',30.2311,120.1483,'["历史", "观景"]','西湖南岸地标，登高可俯瞰湖区。',2.0,'https://thumb.wikimedia.org/wikipedia/commons/thumb/6/62/West_Lake_Leifeng_Pagoda.jpg/960px-West_Lake_Leifeng_Pagoda.jpg','饮冰室客人 / CC BY-SA 4.0 / Wikimedia Commons','https://commons.wikimedia.org/wiki/File:West_Lake_Leifeng_Pagoda.jpg') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('杭州-04','杭州','浙江省','灵隐寺',30.244,120.1037,'["寺庙", "文化"]','位于西湖西侧山林间的历史佛教寺院。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('杭州-05','杭州','浙江省','飞来峰',30.2435,120.101,'["山水", "文化"]','以岩壁石刻和山林步道为特色。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('杭州-06','杭州','浙江省','龙井村',30.2081,120.1156,'["茶文化", "自然"]','以茶园和山间村落风景著称。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('杭州-07','杭州','浙江省','西溪湿地',30.2692,120.0698,'["湿地", "自然"]','以河网、湿地生态和慢节奏游览为特色。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('杭州-08','杭州','浙江省','河坊街',30.2438,120.1744,'["美食", "文化"]','老城步行街区，可以体验传统商铺与地方小吃。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('杭州-09','杭州','浙江省','九溪烟树',30.1956,120.1177,'["山水", "徒步"]','山谷溪流与林荫步道，适合轻徒步。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('杭州-10','杭州','浙江省','宋城',30.1827,120.1065,'["演艺", "文化"]','以宋文化为主题的旅游演艺区域。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('北京-01','北京','北京市','故宫博物院',39.9163,116.3972,'["历史", "博物馆"]','明清宫殿建筑群及丰富的文物展览。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('北京-02','北京','北京市','天安门广场',39.9054,116.3976,'["地标", "历史"]','北京中心区域的大型城市广场。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('北京-03','北京','北京市','景山公园',39.925,116.3967,'["公园", "观景"]','登高可眺望北京中轴线及故宫。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('北京-04','北京','北京市','天坛公园',39.8822,116.4066,'["历史", "公园"]','以古代祭天建筑群和园林环境闻名。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('北京-05','北京','北京市','颐和园',39.999,116.2755,'["园林", "历史"]','以昆明湖和万寿山为核心的皇家园林。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('北京-06','北京','北京市','圆明园',40.0081,116.3033,'["历史", "园林"]','历史遗址与园林水景相结合的游览区。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('北京-07','北京','北京市','南锣鼓巷',39.9374,116.4036,'["胡同", "美食"]','传统胡同商业街区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('北京-08','北京','北京市','什刹海',39.9376,116.3873,'["湖景", "胡同"]','可步行体验湖畔和老北京胡同氛围。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('北京-09','北京','北京市','八达岭长城',40.3597,116.0201,'["历史", "徒步"]','长城代表性游览区，距离北京市中心较远。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('上海-01','上海','上海市','外滩',31.2397,121.4903,'["地标", "夜景"]','黄浦江畔历史建筑群和城市天际线景观。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('上海-02','上海','上海市','豫园',31.2271,121.4921,'["园林", "文化"]','江南古典园林和周边老城商圈。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('上海-03','上海','上海市','东方明珠',31.2396,121.4998,'["观景", "地标"]','陆家嘴标志性电视塔与观景地点。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('上海-04','上海','上海市','南京路步行街',31.2361,121.475,'["购物", "城市"]','商业步行街，适合夜景漫步。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('上海-05','上海','上海市','田子坊',31.2107,121.4688,'["街区", "文化"]','由里弄建筑改造的创意街区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('上海-06','上海','上海市','上海博物馆',31.2309,121.473,'["博物馆", "文化"]','收藏展示中国古代艺术品的博物馆。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('上海-07','上海','上海市','武康路',31.2081,121.4358,'["街区", "建筑"]','具有历史风貌的街道。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('上海-08','上海','上海市','朱家角古镇',31.11,121.0553,'["古镇", "历史"]','水乡古镇，离市中心较远。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('成都-01','成都','四川省','成都大熊猫繁育研究基地',30.7381,104.1446,'["动物", "亲子"]','观赏大熊猫科普展示的热门场所。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('成都-02','成都','四川省','宽窄巷子',30.6731,104.053,'["文化", "街区"]','由历史街巷构成的文化商业区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('成都-03','成都','四川省','锦里古街',30.6442,104.049,'["美食", "古街"]','成都传统风格街区及地方小吃集中地。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('成都-04','成都','四川省','武侯祠',30.6455,104.0483,'["三国", "历史"]','以三国历史文化为主题的博物馆园区。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('成都-05','成都','四川省','杜甫草堂',30.6601,104.0286,'["文学", "园林"]','纪念诗人杜甫的历史文化景区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('成都-06','成都','四川省','人民公园',30.6634,104.0627,'["公园", "茶馆"]','适合体验成都公园和茶馆文化。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('成都-07','成都','四川省','春熙路',30.657,104.08,'["购物", "城市"]','成都核心商业街区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('成都-08','成都','四川省','青城山',30.9011,103.5657,'["山水", "道教"]','位于都江堰附近的山岳与道教文化景区。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('成都-09','成都','四川省','都江堰',31.0008,103.6143,'["水利", "历史"]','历史悠久的水利工程与景区。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('西安-01','西安','陕西省','西安城墙',34.269,108.946,'["历史", "地标"]','保存较完整的古城墙，可沿城墙游览。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('西安-02','西安','陕西省','钟楼',34.2611,108.9471,'["历史", "地标"]','西安市中心标志性古建筑。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('西安-03','西安','陕西省','鼓楼',34.262,108.9393,'["历史", "地标"]','毗邻回民街的城市历史建筑。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('西安-04','西安','陕西省','回民街',34.2666,108.9408,'["美食", "街区"]','以特色小吃和城市街巷体验为主。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('西安-05','西安','陕西省','大雁塔',34.2186,108.9643,'["历史", "文化"]','唐代佛教建筑与周边文化景观。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('西安-06','西安','陕西省','大唐不夜城',34.2134,108.966,'["夜景", "文化"]','唐文化主题步行街区，夜间氛围活跃。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('西安-07','西安','陕西省','陕西历史博物馆',34.2257,108.9563,'["博物馆", "历史"]','集中展示陕西地区历史文物。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('西安-08','西安','陕西省','秦始皇帝陵博物院',34.3839,109.2785,'["历史", "博物馆"]','兵马俑展馆所在区域，距市中心较远。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('广州-01','广州','广东省','广州塔',23.1086,113.3193,'["地标", "观景"]','珠江畔城市观景地标。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('广州-02','广州','广东省','沙面岛',23.1112,113.239,'["建筑", "街区"]','保留多种历史风格建筑的江边街区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('广州-03','广州','广东省','陈家祠',23.1263,113.2475,'["文化", "建筑"]','岭南传统建筑与工艺展示场所。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('广州-04','广州','广东省','北京路步行街',23.1252,113.2678,'["美食", "购物"]','广州历史商业街区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('广州-05','广州','广东省','越秀公园',23.1415,113.2666,'["公园", "历史"]','大型城市公园和五羊雕塑所在区域。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('广州-06','广州','广东省','中山纪念堂',23.1373,113.2636,'["历史", "建筑"]','具有纪念意义的城市公共建筑。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('广州-07','广州','广东省','白云山',23.1888,113.2995,'["山水", "徒步"]','城市近郊登山和休闲景区。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('广州-08','广州','广东省','珠江新城',23.1194,113.3215,'["城市", "夜景"]','现代城市建筑与夜景集中区域。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('重庆-01','重庆','重庆市','洪崖洞',29.5667,106.5784,'["夜景", "街区"]','依山而建的山城夜景地标。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('重庆-02','重庆','重庆市','解放碑',29.5606,106.577,'["地标", "购物"]','重庆核心商圈的标志性建筑。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('重庆-03','重庆','重庆市','长江索道',29.557,106.5872,'["观景", "交通"]','跨江索道及两岸山城景观体验。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('重庆-04','重庆','重庆市','磁器口古镇',29.5828,106.452,'["古镇", "文化"]','嘉陵江畔历史街巷景区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('重庆-05','重庆','重庆市','李子坝观景平台',29.5568,106.5338,'["城市", "交通"]','观赏轨道交通穿楼景观。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('重庆-06','重庆','重庆市','鹅岭公园',29.5526,106.531,'["公园", "观景"]','登高欣赏江景和山城地形。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('重庆-07','重庆','重庆市','南山一棵树',29.5431,106.5987,'["夜景", "观景"]','南岸山坡上的城市观景点。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('重庆-08','重庆','重庆市','三峡博物馆',29.5642,106.5472,'["博物馆", "文化"]','介绍三峡地区自然、人文和历史。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('南京-01','南京','江苏省','中山陵',32.0654,118.8486,'["历史", "文化"]','位于钟山风景区的纪念性建筑群。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('南京-02','南京','江苏省','明孝陵',32.0592,118.8364,'["历史", "园林"]','明代陵寝遗址与林间步道。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('南京-03','南京','江苏省','夫子庙',32.0193,118.787,'["古街", "文化"]','秦淮河畔历史文化街区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('南京-04','南京','江苏省','秦淮河',32.0196,118.79,'["河景", "夜景"]','城市历史水岸景观。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('南京-05','南京','江苏省','玄武湖',32.0735,118.797,'["湖景", "公园"]','市中心附近大型湖泊公园。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('南京-06','南京','江苏省','南京博物院',32.0439,118.8235,'["博物馆", "历史"]','南京重要的综合性历史艺术博物馆。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('南京-07','南京','江苏省','总统府',32.0443,118.8063,'["历史", "建筑"]','包含近代史相关展陈的历史建筑群。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('南京-08','南京','江苏省','老门东',32.0036,118.7878,'["古街", "美食"]','城市历史街区和传统建筑风貌区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('武汉-01','武汉','湖北省','黄鹤楼',30.544,114.3025,'["历史", "观景"]','长江南岸古典建筑与城市眺望点。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('武汉-02','武汉','湖北省','东湖',30.5658,114.3893,'["湖景", "自然"]','大型城中湖与绿道区域。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('武汉-03','武汉','湖北省','湖北省博物馆',30.5649,114.365,'["博物馆", "历史"]','以楚文化文物展陈闻名。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('武汉-04','武汉','湖北省','武汉大学',30.5401,114.3614,'["校园", "建筑"]','具有历史建筑和自然环境的校园。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('武汉-05','武汉','湖北省','户部巷',30.5459,114.295,'["美食", "街区"]','传统美食街区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('武汉-06','武汉','湖北省','江汉路',30.5824,114.2889,'["街区", "购物"]','历史建筑和现代商业结合的步行街。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('武汉-07','武汉','湖北省','古琴台',30.5523,114.263,'["历史", "文化"]','与知音故事相关的文化景点。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('武汉-08','武汉','湖北省','汉口江滩',30.5926,114.3029,'["江景", "公园"]','沿江步道及开放公共空间。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('厦门-01','厦门','福建省','鼓浪屿',24.4473,118.0674,'["海岛", "建筑"]','以近代建筑风貌和海岛步行为特色。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('厦门-02','厦门','福建省','厦门大学',24.4365,118.1025,'["校园", "建筑"]','毗邻海岸的高校校园，入校政策需核实。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('厦门-03','厦门','福建省','南普陀寺',24.4428,118.0998,'["寺庙", "文化"]','五老峰山麓历史寺庙。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('厦门-04','厦门','福建省','曾厝垵',24.428,118.1152,'["美食", "街区"]','近海休闲街巷与小吃聚集区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('厦门-05','厦门','福建省','环岛路',24.4288,118.1432,'["海滨", "骑行"]','环海休闲道路和观海步道。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('厦门-06','厦门','福建省','胡里山炮台',24.4329,118.1106,'["历史", "海滨"]','海边历史军事遗址。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('厦门-07','厦门','福建省','中山路步行街',24.4573,118.0793,'["街区", "购物"]','骑楼建筑与商铺集中地。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('厦门-08','厦门','福建省','园林植物园',24.4471,118.105,'["植物", "自然"]','热带亚热带植物景观丰富。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('三亚-01','三亚','海南省','亚龙湾',18.2229,109.644,'["海滨", "度假"]','沙滩与度假酒店集中的海湾。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('三亚-02','三亚','海南省','天涯海角',18.2967,109.3511,'["海滨", "地标"]','海滨礁石及海岸风光景区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('三亚-03','三亚','海南省','蜈支洲岛',18.3158,109.7576,'["海岛", "海滨"]','离岸海岛游览，需提前查船班。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('三亚-04','三亚','海南省','鹿回头',18.2256,109.4913,'["公园", "观景"]','可以观赏三亚市区及海湾景观。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('三亚-05','三亚','海南省','南山文化旅游区',18.2945,109.2108,'["文化", "海滨"]','以文化建筑与海景闻名的景区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('三亚-06','三亚','海南省','大东海',18.224,109.5292,'["海滨", "度假"]','靠近市区的热门海滨区域。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('三亚-07','三亚','海南省','三亚湾',18.2773,109.4752,'["海滨", "夜景"]','适合傍晚漫步观海的海湾。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('三亚-08','三亚','海南省','大小洞天',18.3034,109.1798,'["自然", "海滨"]','海岸礁石和自然山海景观。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('桂林-01','桂林','广西壮族自治区','象鼻山',25.2643,110.2948,'["山水", "地标"]','桂林市区著名的山水地标。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('桂林-02','桂林','广西壮族自治区','两江四湖',25.2725,110.287,'["水景", "夜景"]','城市内环湖水系和夜景游览区。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('桂林-03','桂林','广西壮族自治区','七星公园',25.272,110.3156,'["山水", "公园"]','山峰、溶洞与公园相结合。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('桂林-04','桂林','广西壮族自治区','芦笛岩',25.3042,110.2701,'["溶洞", "自然"]','以喀斯特溶洞景观闻名。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('桂林-05','桂林','广西壮族自治区','叠彩山',25.2861,110.306,'["山水", "观景"]','登高俯瞰桂林城区与山峰。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('桂林-06','桂林','广西壮族自治区','独秀峰',25.2783,110.2998,'["历史", "山水"]','市区历史山峰及王城景区。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('桂林-07','桂林','广西壮族自治区','阳朔西街',24.777,110.4964,'["古街", "美食"]','阳朔县热闹的步行商业街。',1.5,'','','') ON CONFLICT (id) DO NOTHING;
INSERT INTO attractions (id,city,province,name,lat,lon,tags_json,description,duration_hours,photo_url,photo_credit,photo_source) VALUES ('桂林-08','桂林','广西壮族自治区','遇龙河',24.7546,110.4323,'["山水", "漂流"]','阳朔附近以田园山水著称的河流。',2.0,'','','') ON CONFLICT (id) DO NOTHING;
COMMIT;

-- V3 增量：高德真实 POI 缓存，与原始演示景点表隔离；可在旧 V2 库上执行。
CREATE TABLE IF NOT EXISTS amap_poi_cache (
 id varchar(80) PRIMARY KEY,
 city varchar(50) NOT NULL,
 keyword varchar(70) NOT NULL,
 name varchar(100) NOT NULL,
 lat double precision NOT NULL,
 lon double precision NOT NULL,
 data_json text NOT NULL,
 retrieved_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_amap_poi_cache_city ON amap_poi_cache(city);
CREATE INDEX IF NOT EXISTS ix_amap_poi_cache_keyword ON amap_poi_cache(keyword);
