# TripMind AI

**Python FastAPI + 原生 HTML/CSS/JS + PostgreSQL / SQLite + OpenAI 兼容大模型服务 + 高德地图 Web 服务 API。**

## 1. 配置（Windows）

准备：Python 3.10+、一个数据库（PostgreSQL 15+ 或直接用内置 SQLite）、以及**大模型 API Key**和**高德 Web 服务 API Key**。所有配置都写在项目根目录 `.env`。

1. 解压项目（或 `git clone`）
2. 数据库二选一：
   - **SQLite（最省事）**：新建 `.env.local`，写入 `DATABASE_URL=sqlite:///./tripmind.sqlite3`，无需安装 PostgreSQL；
   - **PostgreSQL**：用 pgAdmin 或 `psql` 新建数据库 `travel_agent`（编码 UTF-8），首次安装执行 `database/init.sql`。
3. 复制 `.env.example` 为 `.env`，填写数据库连接串、`DASHSCOPE_API_KEY`、`AMAP_WEB_KEY`（必须选 **Web 服务** 类型的 Key）；
4. 双击 `init_and_start.bat`（首次运行会创建虚拟环境并安装依赖），或手动执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

5. 浏览器打开 **http://127.0.0.1:8000** ，API 文档位于 **http://127.0.0.1:8000/api/docs**。
6. 日常启动用 `start.bat`（跳过建表）；`init_and_start.bat` 会建缺失的表并在景点表为空时导入 100 条教学景点，两者都是幂等的。

数据库连接字符串示例：

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:你的密码@127.0.0.1:5432/travel_agent
# 或
DATABASE_URL=sqlite:///./tripmind.sqlite3
```

> **SQL 安全说明**：PostgreSQL 密码含 `@`、`#`、`/`、`:` 时需要 URL 编码。数据库端口默认 5432。请先在 pgAdmin/psql 中确认数据库服务正在运行。

### 环境变量一览

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | PostgreSQL 连接串 | 也支持 `sqlite:///./xxx.sqlite3` |
| `DASHSCOPE_API_KEY` | 空 | 大模型服务的 API Key（变量名为历史命名，实际对应任意 OpenAI 兼容服务） |
| `DASHSCOPE_BASE_URL` | 阿里云端点 | **必须与 Key 所属服务、地域一致**，末尾带 `/v1` |
| `QWEN_MODELS` | `qwen-plus,qwen-max` | 允许选择的模型列表，逗号分隔 |
| `DEFAULT_MODEL` | 列表第一项 | 请求未指定模型时使用 |
| `MODEL_TIMEOUT_SECONDS` | 45 | 单次模型调用超时 |
| `AGENT_TOTAL_TIMEOUT_SECONDS` | 90 | **单次对话的总时间预算**，超过后中止并明确报错 |
| `AGENT_MAX_STEPS` | 4 | 一次对话内最多几轮工具调用 |
| `AMAP_WEB_KEY` | 空 | 高德 Web 服务 Key（不是 JS API Key） |
| `AMAP_TIMEOUT_SECONDS` | 12 | 单次高德请求超时 |
| `AMAP_INTERCITY_BUDGET_SECONDS` | 3 | 跨城距离查询的总预算，超时只降级不拖慢主流程 |
| `AMAP_LEGS_BUDGET_SECONDS` | 5 | 景点之间道路轨迹的取数预算（排程与地图共用同一份缓存） |
| `AMAP_JS_KEY` | 空 | 前端地图用的高德 JS API Key（与 Web 服务 Key 是两套凭据） |
| `AMAP_JS_SECURITY_CODE` | 空 | JS API 2.0 安全密钥；缺失时前端自动回退开源底图并提示 |
| `POI_CACHE_HOURS` | 72 | 高德 POI 缓存有效期（按城市+关键词隔离） |
| `TRIPMIND_INIT_DATABASE` | 1 | 1=建缺失表并按需导入教学景点；0=只用现有库 |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | 监听地址与端口；默认只监听本机 |

`/api/health` 能检测 DB 是否连接及配置状态，但 `qwen_configured/amap_configured=true` **只代表填了 Key，不代表真实调用成功**。

## 2. 交互示例

登录不需要账号。打开 AI 对话，选择模型列表中的任意模型。可以输入：

- “我从上海出发去苏州市玩三天，喜欢园林，不想太赶，给我规划路线。”
- “先说说西宁市有哪些特色景点。”
- “改成 2 天，保留第一天的两个景点。”
- “比较一下 K-means+贪心 和 DBSCAN+动态规划的路线长度。”
- “嗨，介绍一下你的能力。”

**行为流程：** 用户消息 → 大模型自然语言理解 → 模型选择工具及参数 → 后端调用高德获取 POI → PostgreSQL/SQLite 缓存 → 聚类/路径算法 → 模型根据工具结果组织答案 → 网页展示行程及工具轨迹。多轮对话以历史聊天文本作为上下文，历史记录保存在数据库中。

如果工具超时/未配置/查无结果，模型看到错误并说明情况；不会拿本地演示景点伪造高德查询成功。

## 3. 两种界面、两套明确的数据口径

| 页面 | 作用 | 所用数据 |
|---|---|---|
| AI 对话 | 真实模型工具调用，自主判断是否规划 | 模型 + 高德景点（实时/缓存） |
| 行程规划 | 人工输入目的地，直接测试算法功能 | 高德景点（实时/缓存） |
| 算法实验室 | 4 种组合确定性比较 | 可选择“本地教学测试集”或“高德实时 POI” |
| 测试与缺陷 | 登记缺陷、状态追踪、质量统计 | 数据库 defects 表 |

**算法说明**：K-means/DBSCAN 负责位置聚类；最近邻贪心/Held-Karp 动态规划负责组内点序排序。聚类与排序使用**经纬度直线距离**作为目标函数，只用于教学对比，不追求全局最优。**但行程时间轴里的交通时长用的是高德真实路径**（≤2.5 km 步行、更远驾车），排程与地图共用 `app/legs.py` 的同一份缓存；只有高德取不到轨迹时才退回直线估计，并在图上画虚线、侧栏标注「直线」。算法可能无法同时满足门票、营业时间、人流、预算等现实约束；请勿声称已完全优化。

**单日景点上限**：由**旅行节奏**决定——休闲 3 个 / 标准 4 个 / 紧凑 5 个；候选会先按 `天数 × 每日上限` 截断，多余的进入「未排入」而不是报错。动态规划排序本身仍有 **12 个点/天**的硬上限（防指数复杂度），按上述节奏截断后不会触及。

**数据源说明**：100 条内置景点只在 `attractions` 表，作为教学回归基线；真实高德结果在 `amap_poi_cache` 表。缓存按城市及关键词分离，默认 72 小时有效（可设 `POI_CACHE_HOURS`）。`/api/plan` 与 `/api/benchmark` 共用同一份缓存，因此响应里的 `data_source` 会标注“高德地图 POI 实时接口”或“高德地图 POI 缓存”，两者都不是编造数据。高德照片来源及许可请遵循平台条款。

**时间口径**：所有接口返回的时间戳统一为带 UTC 时区的 ISO 8601（`...+00:00`）。SQLite 不保存时区，服务端读出后统一补 UTC，因此同一资源在“创建响应”和“列表响应”中的格式一致。

**上下文口径**：单次对话只把最近 **12 条**历史消息送入模型，且每条裁剪到 **2500 字符**。发生裁剪时响应会带 `context_note` 字段说明，前端会在回答下方提示，不会静默丢失。

## 4. 关键文件结构

```text
TripMindAI/
├─ app/
│  ├─ main.py              # FastAPI 路由（28 个）+ 参数校验 + 持久化 + NDJSON 流式输出
│  ├─ agent.py             # 模型 function calling；模型自主选择工具，含总时间预算
│  ├─ amap.py              # 真实高德 POI/地理编码/驾车适配器，可注入 HTTP 客户端
│  ├─ dynamic_planning.py  # 真实 POI → 缓存 → 聚类/排序；跨城查询带独立时间预算
│  ├─ itinerary.py         # 时间预算排程：游览时长/交通/营业时间/午餐/未排入清单
│  ├─ legs.py            # 路段耗时与道路折线的统一缓存（排程与地图共用）
│  ├─ geo.py             # GCJ-02 → WGS-84 坐标纠偏
│  ├─ travel_core.py       # K-means/DBSCAN/贪心/Held-Karp 纯算法
│  ├─ models.py            # SQLAlchemy 表定义（6 张表，含 itineraries）
│  ├─ storage.py           # 引擎与会话工厂、幂等建表与教学数据导入
│  ├─ planning.py          # 教学数据集的算法对比适配
│  ├─ config.py            # 环境变量 → 不可变 Settings
│  ├─ data/cities.json     # 12 城 100 条教学景点（不进入 AI 链路）
│  └─ static/{index.html,styles.css,app.js,logo.png}
├─ database/
│  ├─ init.sql              # PostgreSQL 初始化脚本
│  ├─ upgrade_v2_to_v3.sql  # 旧库升级
│  ├─ create_database.sql   # 建库语句
│  └─ check.sql             # 数据自检
├─ tests/                  # pytest 用例（168 条，无外网依赖）
├─ .env.example / .env.local
├─ requirements.txt / requirements-dev.txt
├─ pytest.ini              # 已配置 testpaths=tests 与 pythonpath=.
├─ run.py                  # 启动入口
├─ init_and_start.bat      # 初始化 + 启动（建表、装依赖）
└─ start.bat / start.sh    # 日常启动（跳过初始化）
```

## 5. 行程真实性

- **游览时长按类型估算**（博物馆 2h、寺庙 1h、园林 1.5h、商业街 0.8h、大景区 3.5h），不再一律 1.5 小时；
- **交通时间用高德路径**（步行 ≤2.5km、更远驾车），排程与地图共用缓存，两个地方看到的时间一致；
- **营业时间**：高德有 `business.opentime` 就用真实时段，没有则按类型给保守默认值并在提示里标注“按类型估算”；计划安排在关门之后会给出 ⚠ 提示，但不会静默丢弃景点；
- **节奏与时间窗**：休闲 3 个/6h（默认）、标准 4 个/7.5h、紧凑 5 个/8.5h；出发时间可设置为任意 HH:MM，时间窗随之后移；
- **住宿地**：填了 `lodging` 时每天从该处出发（会先地理编码），跨城段仍单独处理；
- **排不下的景点**进入 `unscheduled`，并给出“建议至少安排 N 天”与容量账本。

> **自动化测试现状**：`tests/` 共 **168 条**用例，覆盖排程逻辑、营业时间解析、POI 去重、路段缓存、接口契约与行程微调，使用临时 SQLite 与假客户端，**不依赖外网**。运行方式：
>
> ```powershell
> .\.venv\Scripts\python.exe -m pytest -q      # 约 4–5 秒，期望 168 passed
> .\.venv\Scripts\python.exe -m ruff check app --select F,E9
> ```

## 6. API 概览

- `GET /api/health`、`GET /api/models`、`GET /api/docs`、`GET /api/map-config`（下发给前端的地图配置）
- `GET /api/cities`、`GET /api/attractions?city=...`：返回 `found` 标记，未收录城市返回空列表与 `note` 说明
- `GET /api/pois?city=...`：候选景点（含营业时间、纠偏坐标），供用户勾选后再规划
- `POST /api/plan`：结构化规划。支持 `pace`（休闲/标准/紧凑）、`day_start`、`lodging`（住宿地）、`spot_ids`/`spot_names`（自选景点）；跨城数据超预算时省略并给出 `intercity_note`
- `POST /api/plan/edit`：单点微调（`op=remove` 把景点移出某天，`op=add` 把未排入的景点加回）
- `POST /api/plan/reschedule`：微调后批量重排（前端把整份调整提交一次，只重算一次时间轴）
- `POST /api/route-geometry`：相邻景点的道路折线与通行时间；与排程共用同一份缓存，保证时间轴和地图口径一致
- `GET /api/geocode/reverse?lon=&lat=`：逆地理编码，供住宿地地图选点回填地址名
- `POST /api/itineraries`、`GET /api/itineraries`、`GET/DELETE /api/itineraries/{id}`：保存行程并生成分享链接（`/?trip=<id>` 直接打开）
- `GET /api/benchmark?city=...&days=...`：真实高德 POI 上的算法对比
- `GET /api/benchmark-fixture?city=...&days=...`：100 条本地教学景点上的确定性对比（未收录城市返回空 `rows` 与 `note`）
- `POST /api/chat`：真实模型 function calling，回复中 `tool_trace` 标明模型选了什么工具，`context_note` 标明上下文是否被裁剪
- `POST /api/chat/stream`：同上，以 NDJSON 流式返回（`status`/`delta`/`done` 事件）
- `GET/POST /api/conversations`、`GET/DELETE /api/conversations/{id}`：对话持久化，删除会话会级联删除消息
- `GET/POST /api/defects`、`PATCH /api/defects/{id}`、`GET /api/quality-summary`：缺陷登记与质量统计

接口入参一律拒绝未声明的字段（返回 422），避免“传了但被静默忽略”。

## 7. 更新日志

每个版本的变更与修复见 [CHANGELOG.md](CHANGELOG.md)，其中「版本一览 / 修复一览」可快速浏览；本文档的「已知限制」小节与其中的「已知问题」保持一致。

## 8. 已知限制

- **没有 API Key 不能执行真正 AI 聊天**；没有高德 Key 就不能获取未缓存城市真实 POI。这是明确报错，不会伪造回答。
- 只能规划 1～7 天。使用小规模 POI 进行计算，不保证覆盖城市内全部景点；景点有无、POI 搜索排序依赖高德。
- **营业时间**：高德只有部分 POI 返回 `business.opentime`，缺失时按类型给保守默认值并在时间轴标注“按类型估算”；计划落在关门之后只给 ⚠ 提示，不会强行调整或丢弃景点。
- **门票、预约、限流、天气、节假日**均未接入，只有提示语，出行前需自行核实。
- 未包含用户注册、授权和生产级安全防护，推荐仅在本地学习环境运行。`HOST=127.0.0.1`，不要直接暴露到公共互联网。
- **分享链接无鉴权**：知道 `?trip=<uuid>` 即可访问该行程，公网部署前需要加访问控制或有效期。
- 高德地理编码接口在本机实测抖动较大（0.4～24 秒），已对城市坐标做进程内缓存并把跨城查询限制在独立时间预算内；极端情况下跨城数据会被省略。
- 同一对话触发多轮工具调用时整体耗时可能达到分钟级，已由 `AGENT_TOTAL_TIMEOUT_SECONDS` 兜底中止并报错。

**课程适配**：可设计功能度测试、易用性测试、用户文档检查、静态代码审查、动态接口/算法测试、缺陷回归；测试证据和团队会议纪要必须来自实际执行。
