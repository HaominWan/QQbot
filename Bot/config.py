import json
import os

# Load configuration from config.json
config_dir = os.path.dirname(__file__)
config_path = os.path.join(config_dir, 'config.json')


def _resolve_config_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(config_dir, path))

if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8-sig') as f:
        config_data = json.load(f)
else:
    # Fallback or error if config.json is missing
    # You might want to copy config.example.json to config.json here if needed
    raise FileNotFoundError("config.json not found. Please create it from config.example.json")

api_keys = config_data.get("api_keys", {})
model_settings = config_data.get("model_settings", {})

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or api_keys.get("openai", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or api_keys.get("gemini", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or api_keys.get("groq", "")
PRODIA_API_KEY = os.environ.get("PRODIA_API_KEY") or api_keys.get("prodia", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or api_keys.get("openrouter", "")
HF_TOKEN = os.environ.get("HF_TOKEN") or api_keys.get("hf_token", "")
PIXIV_REFRESH_TOKEN = (
    os.environ.get("PIXIV_REFRESH_TOKEN")
    or api_keys.get("pixiv_refresh_token", "")
)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or api_keys.get("deepseek", "")
DEEPSEEK_BASE_URL = model_settings.get("deepseek_base_url", "https://api.deepseek.com")
DEEPSEEK_MODEL = model_settings.get("deepseek_model", "deepseek-v4-flash")
DEEPSEEK_TEMPERATURE = float(model_settings.get("deepseek_temperature", 0.75))

def _int_list(values, field_name: str) -> list[int]:
    normalized = []
    for value in values:
        try:
            normalized.append(int(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} contains a non-integer id: {value!r}") from exc
    return normalized


SUPER_USERS = _int_list(config_data["bot_settings"]["super_users"], "super_users")
TEST_GROUPS = _int_list(config_data["bot_settings"]["test_groups"], "test_groups")
HOST = config_data["bot_settings"]["host"]
PORT = config_data["bot_settings"]["port"]
PROXY_URL = config_data["bot_settings"]["proxy_url"]

_memory = config_data.get("memory_settings", {})
MEMORY_ENABLED = _memory.get("enabled", True)
MEMORY_DB_PATH = _resolve_config_path(_memory.get("db_path", "./memory_db"))
MEMORY_WINDOW_SIZE = int(_memory.get("window_size", 30))
MEMORY_SEARCH_RESULTS = int(_memory.get("search_results", 3))
MEMORY_MAX_RECORDS_PER_GROUP = int(_memory.get("max_records_per_group", 5000))
MEMORY_CONTEXT_MAX_CHARS = int(_memory.get("context_max_chars", 1500))
MEMORY_CONTEXT_PLACEMENT = _memory.get("context_placement", "user_message")

_pixiv = config_data.get("pixiv_settings", {})
PIXIV_MIN_BOOKMARKS = int(_pixiv.get("min_bookmarks", 100))
PIXIV_SAMPLE_POOL = int(_pixiv.get("sample_pool", 80))
PIXIV_DEFAULT_COUNT = int(_pixiv.get("default_count", 1))
PIXIV_MAX_COUNT = int(_pixiv.get("max_count", 3))
PIXIV_ALLOW_R18 = bool(_pixiv.get("allow_r18", False))
PIXIV_ALLOW_AI = bool(_pixiv.get("allow_ai", False))
