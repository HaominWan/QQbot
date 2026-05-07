import json
import os

# Load configuration from config.json
config_path = os.path.join(os.path.dirname(__file__), 'config.json')

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

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or api_keys.get("deepseek", "")
DEEPSEEK_BASE_URL = model_settings.get("deepseek_base_url", "https://api.deepseek.com")
DEEPSEEK_MODEL = model_settings.get("deepseek_model", "deepseek-v4-flash")
DEEPSEEK_TEMPERATURE = float(model_settings.get("deepseek_temperature", 0.75))

SUPER_USERS = config_data["bot_settings"]["super_users"]
TEST_GROUPS = config_data["bot_settings"]["test_groups"]
HOST = config_data["bot_settings"]["host"]
PORT = config_data["bot_settings"]["port"]
PROXY_URL = config_data["bot_settings"]["proxy_url"]

_memory = config_data.get("memory_settings", {})
MEMORY_ENABLED = _memory.get("enabled", True)
MEMORY_DB_PATH = _memory.get("db_path", "./memory_db")
MEMORY_WINDOW_SIZE = int(_memory.get("window_size", 30))
MEMORY_SEARCH_RESULTS = int(_memory.get("search_results", 6))
