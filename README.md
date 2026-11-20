# TripMind AI

**Python FastAPI + 原生 HTML/CSS/JS + PostgreSQL + 阿里云百炼 Qwen + 高德地图 Web 服务 API。**

## 配置（Windows）

准备：Python 3.10+、PostgreSQL 15+，以及**阿里百炼 API Key**和**高德 Web 服务 API Key**。两类 API Key 均填在项目根目录 `.env`

1. 解压项目
2. 用 pgAdmin 或 `psql` 新建数据库 `travel_agent`（数据库编码 UTF-8）；
3. 首次安装在 pgAdmin 的 `travel_agent` Query Tool 执行 `database/init.sql`
4. 复制 `.env.example` 为 `.env`，修改数据库密码、`DASHSCOPE_API_KEY`、`AMAP_WEB_KEY`（web服务）；
5. 双击 `init_and_start.bat`，首次运行将创建虚拟环境、安装依赖；
6. 浏览器打开 **http://127.0.0.1:8000** ，API 文档位于 **http://127.0.0.1:8000/api/docs**。

数据库连接字符串示例：

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:你的密码@127.0.0.1:5432/travel_agent
DASHSCOPE_API_KEY=sk-你自己的百炼密钥
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODELS=qwen-plus,qwen-max
DEFAULT_MODEL=qwen-plus
AMAP_WEB_KEY=你自己的高德Web服务Key
```

`DASHSCOPE_BASE_URL` **必须对应 Key 所属地域及业务空间**。百炼新地域/工作空间可能要求 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` 形式，请以你自己控制台为准。HTTP Tool Calling 需要选择支持工具调用的文本模型。

阿里官方文档：https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions/

高德 POI 2.0 文档：https://developer.amap.com/api/webservice/guide/api/newpoisearch

> **SQL 安全说明**：PostgreSQL 密码含 `@`、`#`、`/`、`:` 时需要 URL 编码。数据库端口默认 5432。请先在 pgAdmin/psql 中确认数据库服务正在运行。

### 用 PowerShell 手动启动

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

`/api/health` 能检测 DB 是否连接及配置状态，但 `qwen_configured/amap_configured=true` **只代表填了 Key，不代表真实调用成功**。

## 2. 交互示例

登录不需要账号。打开 AI 对话，选择 `qwen-plus` 或 `qwen-max`。可以输入：

- “我从上海出发去苏州市玩三天，喜欢园林，不想太赶，给我规划路线。”
- “先说说西宁市有哪些特色景点。”
- “改成 2 天，保留第一天的两个景点。”
- “比较一下 K-means+贪心 和 DBSCAN+动态规划的路线长度。”
- “嗨，介绍一下你的能力。”

**行为流程：** 用户消息 → 阿里模型自然语言理解 → 模型选择工具及参数 → 后端调用高德获取 POI → PostgreSQL 缓存 → 聚类/路径算法 → 模型根据工具结果组织答案 → 网页展示行程及工具轨迹。多轮对话以历史聊天文本作为上下文，历史记录保存在 PostgreSQL。

如果工具超时/未配置/查无结果，模型看到错误并说明情况；不会拿本地演示景点伪造高德查询成功。

## 3. 两种界面、两套明确的数据口径

| 页面 | 作用 | 所用数据 |
|---|---|---|
| AI 对话 | 真实 Qwen 工具调用，自主判断是否规划 | Qwen + 高德景点（实时/缓存） |
| 行程规划 | 人工输入目的地，直接测试算法功能 | 高德景点（实时/缓存） |
| 算法实验室 | 4 种组合确定性比较 | 可选择“本地教学测试集”或“高德实时 POI” |
| 测试与缺陷 | 登记缺陷、状态追踪、质量统计 | PostgreSQL defects 表 |

**算法说明**：K-means/DBSCAN 负责位置聚类；最近邻贪心/Held-Karp 动态规划负责组内点序排序。算法使用**经纬度直线距离**作为目标函数，只用于教学对比，不是驾车/步行真实最优路线。跨城路线若高德驾车接口返回数据，会显示有来源的驾车公里数与估算耗时；城市内景点之间仍是直线估计。算法可能无法同时满足门票、营业时间、人流、预算等现实约束；请勿声称已完全优化。

**数据源说明**：100 条内置景点只在 `attractions` 表，作为教学回归基线；真实高德结果在 `amap_poi_cache` 表。缓存按城市及关键词分离，默认 72 小时有效（可设 `POI_CACHE_HOURS`）。高德照片来源及许可请遵循平台条款。

## 4. 关键文件结构

```text
TripMind_AI_v3/
├─ app/
│  ├─ main.py              # FastAPI endpoints + persistence
│  ├─ agent.py             # Qwen function calling; model decides tool selection
│  ├─ amap.py              # Real AMap POI/geocode/driving HTTP adapter
│  ├─ dynamic_planning.py  # Real POI -> cache -> clustering/routing
│  ├─ travel_core.py       # K-means/DBSCAN/greedy/Held-Karp pure algorithms
│  ├─ models.py            # SQLAlchemy tables
│  ├─ storage.py           # DB session & teaching fixtures
│  ├─ planning.py          # Teaching fixture algorithm lab
│  ├─ config.py            # env settings
│  ├─ data/cities.json     # 100 teaching POIs, NOT live agent
│  └─ static/{index.html,styles.css,app.js,logo.png}
├─ database/
│  ├─ init.sql             # PostgreSQL full initialization
│  └─ upgrade_v2_to_v3.sql# Upgrade existing V2 DB
├─ tests/                  # pytest; fake external HTTP responses
├─ scripts/verify_100_rounds.py
├─ docs/TEST_REPORT.md
├─ .env.example
├─ requirements.txt
├─ requirements-dev.txt
├─ run.py
└─ 启动项目.bat
```

## 5. API 概览

- `GET /api/health`, `GET /api/models`
- `POST /api/chat`：真实 Qwen function calling，回复中 `tool_trace` 会标明模型选了什么工具
- `GET/POST/DELETE /api/conversations...`：聊天持久化
- `POST /api/plan`：直接通过高德 + 算法进行结构化规划
- `GET /api/benchmark`：真实高德 POI 上的算法对比
- `GET /api/benchmark-fixture`：100 条本地教学景点上的确定性算法对比
- `GET/POST/PATCH /api/defects...`，`GET /api/quality-summary`

## 6. 已知限制

- **没有 API Key 不能执行真正 AI 聊天**；没有高德 Key 就不能获取未缓存城市真实 POI。这是明确报错，不会伪造回答。
- 只能规划 1～7 天。使用小规模 POI 进行计算，不保证覆盖城市内全部景点；景点有无、POI 搜索排序依赖高德。
- 景点开门时间、公交时刻、门票价格并无可靠的实时核验；多轮修改完全依赖真实模型的工具选择与理解，需要真实联调和人工验收。
- 未包含用户注册、授权和生产级安全防护，推荐仅在本地学习环境运行。`HOST=127.0.0.1`，不要直接暴露到公共互联网。
- 真实 API 未提供密钥，本交付没有声称验证真实百炼或高德请求。浏览器自动化在本执行环境受本地访问策略限制，仍需在本机人工验收。

**课程适配**：可设计功能度测试、易用性测试、用户文档检查、静态代码审查、动态接口/算法测试、缺陷回归；测试证据和团队会议纪要必须来自实际执行。
