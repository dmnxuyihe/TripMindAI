# TripMind AI

**Python FastAPI + 原生 HTML/CSS/JS + PostgreSQL / SQLite + OpenAI 兼容大模型服务 + 高德地图 Web 服务 API。**

## 配置（Windows）

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
| `AMAP_INTERCITY_BUDGET_SECONDS` | 8 | 跨城距离查询的总预算，超时只降级不拖慢主流程 |
| `POI_CACHE_HOURS` | 72 | 高德 POI 缓存有效期（按城市+关键词隔离） |
| `TRIPMIND_INIT_DATABASE` | 1 | 1=建缺失表并按需导入教学景点；0=只用现有库 |

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

**算法说明**：K-means/DBSCAN 负责位置聚类；最近邻贪心/Held-Karp 动态规划负责组内点序排序。算法使用**经纬度直线距离**作为目标函数，只用于教学对比，不是驾车/步行真实最优路线。跨城路线若高德驾车接口返回数据，会显示有来源的驾车公里数与估算耗时；城市内景点之间仍是直线估计。算法可能无法同时满足门票、营业时间、人流、预算等现实约束；请勿声称已完全优化。

**单日景点上限**：动态规划排序最多支持 **12 个景点/天**（防止指数复杂度失控），超过时该日会明确报错而不是静默降级；实际运行时单日景点数由 `min(16, max(8, 天数×3))` 决定，通常不会触发。

**数据源说明**：100 条内置景点只在 `attractions` 表，作为教学回归基线；真实高德结果在 `amap_poi_cache` 表。缓存按城市及关键词分离，默认 72 小时有效（可设 `POI_CACHE_HOURS`）。`/api/plan` 与 `/api/benchmark` 共用同一份缓存，因此响应里的 `data_source` 会标注“高德地图 POI 实时接口”或“高德地图 POI 缓存”，两者都不是编造数据。高德照片来源及许可请遵循平台条款。

**时间口径**：所有接口返回的时间戳统一为带 UTC 时区的 ISO 8601（`...+00:00`）。SQLite 不保存时区，服务端读出后统一补 UTC，因此同一资源在“创建响应”和“列表响应”中的格式一致。

**上下文口径**：单次对话只把最近 **12 条**历史消息送入模型，且每条裁剪到 **2500 字符**。发生裁剪时响应会带 `context_note` 字段说明，前端会在回答下方提示，不会静默丢失。

## 4. 关键文件结构

```text
TripMindAI/
├─ app/
│  ├─ main.py              # FastAPI 路由（18 个）+ 参数校验 + 持久化 + NDJSON 流式输出
│  ├─ agent.py             # 模型 function calling；模型自主选择工具，含总时间预算
│  ├─ amap.py              # 真实高德 POI/地理编码/驾车适配器，可注入 HTTP 客户端
│  ├─ dynamic_planning.py  # 真实 POI → 缓存 → 聚类/排序；跨城查询带独立时间预算
│  ├─ travel_core.py       # K-means/DBSCAN/贪心/Held-Karp 纯算法
│  ├─ models.py            # SQLAlchemy 表定义（5 张表）
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
├─ .env.example / .env.local
├─ requirements.txt / requirements-dev.txt
├─ pytest.ini              # 已配置 testpaths=tests 与 pythonpath=.
├─ run.py                  # 启动入口
├─ init_and_start.bat      # 初始化 + 启动（建表、装依赖）
└─ start.bat / start.sh    # 日常启动（跳过初始化）
```

> **自动化测试现状**：`pytest.ini` 与 `requirements-dev.txt`（pytest、ruff）已就绪，但仓库目前**尚未包含 `tests/` 目录**，因此 `pytest` 暂时收集不到用例。测试用例将在课程测试阶段补充。

## 5. API 概览

- `GET /api/health`、`GET /api/models`、`GET /api/docs`
- `GET /api/cities`、`GET /api/attractions?city=...`：返回 `found` 标记，未收录城市返回空列表与 `note` 说明
- `POST /api/plan`：高德 + 算法直接结构化规划；跨城数据超预算时省略并给出 `intercity_note`
- `GET /api/benchmark?city=...&days=...`：真实高德 POI 上的算法对比
- `GET /api/benchmark-fixture?city=...&days=...`：100 条本地教学景点上的确定性对比（未收录城市返回空 `rows` 与 `note`）
- `POST /api/chat`：真实模型 function calling，回复中 `tool_trace` 标明模型选了什么工具，`context_note` 标明上下文是否被裁剪
- `POST /api/chat/stream`：同上，以 NDJSON 流式返回（`status`/`delta`/`done` 事件）
- `GET/POST /api/conversations`、`GET/DELETE /api/conversations/{id}`：对话持久化，删除会话会级联删除消息
- `GET/POST /api/defects`、`PATCH /api/defects/{id}`、`GET /api/quality-summary`：缺陷登记与质量统计

接口入参一律拒绝未声明的字段（返回 422），避免“传了但被静默忽略”。

## 6. 已知限制

- **没有 API Key 不能执行真正 AI 聊天**；没有高德 Key 就不能获取未缓存城市真实 POI。这是明确报错，不会伪造回答。
- 只能规划 1～7 天。使用小规模 POI 进行计算，不保证覆盖城市内全部景点；景点有无、POI 搜索排序依赖高德。
- 景点开门时间、公交时刻、门票价格并无可靠的实时核验；多轮修改完全依赖真实模型的工具选择与理解，需要真实联调和人工验收。
- 未包含用户注册、授权和生产级安全防护，推荐仅在本地学习环境运行。`HOST=127.0.0.1`，不要直接暴露到公共互联网。
- 高德地理编码接口在本机实测抖动较大（0.4～24 秒），已对城市坐标做进程内缓存并把跨城查询限制在独立时间预算内；极端情况下跨城数据会被省略。
- 同一对话触发多轮工具调用时整体耗时可能达到分钟级，已由 `AGENT_TOTAL_TIMEOUT_SECONDS` 兜底中止并报错。

**课程适配**：可设计功能度测试、易用性测试、用户文档检查、静态代码审查、动态接口/算法测试、缺陷回归；测试证据和团队会议纪要必须来自实际执行。
