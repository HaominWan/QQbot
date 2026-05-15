from groq import Groq, AsyncGroq
from openai import AsyncOpenAI
from config import *
import aiohttp
import asyncio
import httpx
import os
import tempfile

_MAX_RETRIES = 5
_RETRY_DELAY = 2.0


def _usage_value(usage, name):
    if isinstance(usage, dict):
        return usage.get(name)
    return getattr(usage, name, None)


def _log_deepseek_usage(usage):
    prompt_tokens = _usage_value(usage, "prompt_tokens")
    completion_tokens = _usage_value(usage, "completion_tokens")
    total_tokens = _usage_value(usage, "total_tokens")
    cache_hit = _usage_value(usage, "prompt_cache_hit_tokens")
    cache_miss = _usage_value(usage, "prompt_cache_miss_tokens")

    if prompt_tokens is None and cache_hit is not None and cache_miss is not None:
        prompt_tokens = cache_hit + cache_miss

    hit_rate = None
    if prompt_tokens and cache_hit is not None:
        hit_rate = cache_hit / prompt_tokens

    hit_rate_text = f"{hit_rate:.1%}" if hit_rate is not None else "n/a"
    print(
        "[DeepSeek usage] "
        f"prompt={prompt_tokens}, "
        f"cache_hit={cache_hit}, "
        f"cache_miss={cache_miss}, "
        f"hit_rate={hit_rate_text}, "
        f"completion={completion_tokens}, "
        f"total={total_tokens}"
    )


async def call_llm_api(chat_history):
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DeepSeek API key is not configured")

    request_payload = dict(
        model=DEEPSEEK_MODEL,
        messages=chat_history,
        temperature=DEEPSEEK_TEMPERATURE,
        top_p=1,
        stream=True,
        stream_options={"include_usage": True},
    )
    if DEEPSEEK_MODEL.startswith("deepseek-v4"):
        request_payload["extra_body"] = {"thinking": {"type": "disabled"}}

    async def _consume_response(client):
        response = await client.chat.completions.create(**request_payload)
        full_response = ""
        async for chunk in response:
            if getattr(chunk, "usage", None):
                _log_deepseek_usage(chunk.usage)
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
        return full_response

    for attempt in range(_MAX_RETRIES):
        try:
            http_client = httpx.AsyncClient(proxy=PROXY_URL) if PROXY_URL else None
            client = AsyncOpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
                http_client=http_client,
            )
            try:
                return await _consume_response(client)
            finally:
                await client.close()
                if http_client is not None and not http_client.is_closed:
                    await http_client.aclose()

        except Exception as e:
            print(f"Error calling DeepSeek API (attempt {attempt + 1}/{_MAX_RETRIES}): {e}")
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_RETRY_DELAY * (attempt + 1))
            else:
                return "抱歉，我暂时无法处理你的请求。"


# Backward-compatible name while model/session code is migrated gradually.
call_groq_api = call_llm_api

async def transcribe_audio(audio_url):
    """
    使用 Groq Whisper 模型将音频转换为文本
    """
    try:
        print(f"[Groq] Transcribing audio from: {audio_url}")
        
        # 下载音频文件
        async with aiohttp.ClientSession() as session:
            async with session.get(audio_url) as response:
                if response.status != 200:
                    return "[语音下载失败]"
                audio_data = await response.read()

        # 保存为临时文件
        # 注意：这里假设音频格式是 Groq 支持的（如 mp3, wav, m4a 等）。
        # 如果是 QQ 的 silk 格式，可能需要 ffmpeg 转码。
        # 为了简单起见，这里先直接尝试，或者保存为 .wav (如果 Lagrange 提供了转换后的 url)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_audio.write(audio_data)
            temp_audio_path = temp_audio.name

        try:
            client = AsyncGroq(api_key=GROQ_API_KEY)
            
            with open(temp_audio_path, "rb") as file:
                transcription = await client.audio.transcriptions.create(
                    file=(temp_audio_path, file.read()),
                    model="distil-whisper-large-v3-en", # 或者 whisper-large-v3
                    response_format="json",
                    language="zh", # 强制识别为中文，或者 auto
                    temperature=0.0
                )
            
            print(f"[Groq] Transcription: {transcription.text}")
            return f" [语音内容: {transcription.text}] "
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)

    except Exception as e:
        print(f"[Groq] Audio transcription error: {e}")
        return " [语音识别失败] "

    
#             OpenAI(api_key = OPENAI_API_KEY)
#             print(OPENAI_API_KEY)
#             try:
#                 client = OpenAI(
#                      organization="org-jwlTKLr5o8qaeGU1OL0xgt5a",
#                      project="proj_LKwx8mUG90NATGpm7Ub5TB9H"
#                 )

#                 response = client.chat.completions.create(
#                      model="gpt-3.5-turbo", 
#                      messages=chat_history,
#                     temperature=0.7,
#                 )
#                 print(response)
#                 return response["choices"][0]["message"]["content"]
            
#             except Exception as e:
#                 error_message = f"Error calling ChatGPT API: {str(e)}"
#                 print(error_message)  # 打印日志
#                 return "抱歉，我暂时无法处理你的请求。"  # 返回给用户的默认错误消息
