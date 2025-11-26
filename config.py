import json
import os

# Load configuration from config.json
config_path = os.path.join(os.path.dirname(__file__), 'config.json')

if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
else:
    # Fallback or error if config.json is missing
    # You might want to copy config.example.json to config.json here if needed
    raise FileNotFoundError("config.json not found. Please create it from config.example.json")

OPENAI_API_KEY = config_data["api_keys"]["openai"]
GEMINI_API_KEY = config_data["api_keys"]["gemini"]
GROQ_API_KEY = config_data["api_keys"]["groq"]
PRODIA_API_KEY = config_data["api_keys"]["prodia"]

SUPER_USERS = config_data["bot_settings"]["super_users"]
TEST_GROUPS = config_data["bot_settings"]["test_groups"]
HOST = config_data["bot_settings"]["host"]
PORT = config_data["bot_settings"]["port"]
PROXY_URL = config_data["bot_settings"]["proxy_url"]
