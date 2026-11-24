"""Only environment variables, never browser-side API credentials."""
from dataclasses import dataclass, field
import os
from dotenv import load_dotenv

load_dotenv()
# Optional machine-local overrides.  This keeps credentials in the existing
# .env while allowing a developer to switch services (for example, use the
# built-in SQLite support when PostgreSQL is unavailable).
load_dotenv('.env.local', override=True)

@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv('DATABASE_URL', 'postgresql+psycopg://postgres:postgres@127.0.0.1:5432/travel_agent'))
    # 数据库初始化开关：1=创建缺失表并按需导入初始景点；0=只使用现有数据库。
    initialize_database: bool = field(default_factory=lambda: os.getenv('TRIPMIND_INIT_DATABASE', '1').strip() == '1')
    dashscope_api_key: str = field(default_factory=lambda: os.getenv('DASHSCOPE_API_KEY', ''))
    dashscope_base_url: str = field(default_factory=lambda: os.getenv('DASHSCOPE_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'))
    qwen_models: tuple[str, ...] = field(default_factory=lambda: tuple(x.strip() for x in os.getenv('QWEN_MODELS', 'qwen-plus,qwen-max').split(',') if x.strip()))
    default_model: str = field(default_factory=lambda: os.getenv('DEFAULT_MODEL', 'qwen-plus'))
    model_timeout_seconds: float = field(default_factory=lambda: float(os.getenv('MODEL_TIMEOUT_SECONDS', '45')))
    agent_max_steps: int = field(default_factory=lambda: int(os.getenv('AGENT_MAX_STEPS', '4')))
    # 单次对话的总时间预算，防止多轮工具调用叠加成分钟级响应。
    agent_total_timeout_seconds: float = field(default_factory=lambda: float(os.getenv('AGENT_TOTAL_TIMEOUT_SECONDS', '90')))
    amap_api_key: str = field(default_factory=lambda: os.getenv('AMAP_WEB_KEY', ''))
    # 高德 JS API（前端地图）用的 key 与安全密钥，与 Web 服务 key 是两套凭据。
    amap_js_key: str = field(default_factory=lambda: os.getenv('AMAP_JS_KEY', ''))
    amap_js_security_code: str = field(default_factory=lambda: os.getenv('AMAP_JS_SECURITY_CODE', ''))
    amap_timeout_seconds: float = field(default_factory=lambda: float(os.getenv('AMAP_TIMEOUT_SECONDS', '12')))
    # 跨城距离只是展示性信息，给它单独的时间预算：超时就降级，不拖慢主流程。
    # 市内相邻景点步行路径的总预算；超时降级为直线，不拖慢规划
    amap_legs_budget_seconds: float = field(default_factory=lambda: float(os.getenv('AMAP_LEGS_BUDGET_SECONDS', '3.5')))
    amap_intercity_budget_seconds: float = field(default_factory=lambda: float(os.getenv('AMAP_INTERCITY_BUDGET_SECONDS', '3')))
    poi_cache_hours: int = field(default_factory=lambda: int(os.getenv('POI_CACHE_HOURS', '72')))

    @property
    def allowed_models(self):
        return self.qwen_models
