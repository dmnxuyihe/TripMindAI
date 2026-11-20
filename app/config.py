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
    amap_api_key: str = field(default_factory=lambda: os.getenv('AMAP_WEB_KEY', ''))
    amap_timeout_seconds: float = field(default_factory=lambda: float(os.getenv('AMAP_TIMEOUT_SECONDS', '12')))
    poi_cache_hours: int = field(default_factory=lambda: int(os.getenv('POI_CACHE_HOURS', '72')))
    agent_max_steps: int = field(default_factory=lambda: int(os.getenv('AGENT_MAX_STEPS', '4')))

    @property
    def allowed_models(self):
        return self.qwen_models
