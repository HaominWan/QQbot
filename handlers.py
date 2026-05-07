from api import transcribe_audio
from agent_orchestrator import AgentOrchestrator
from command_handlers import CommandHandler
from config import TEST_GROUPS, MEMORY_ENABLED, MEMORY_DB_PATH, MEMORY_SEARCH_RESULTS, MEMORY_WINDOW_SIZE
from framework import BotContext, EventRouter, MessageEvent
from persona_engine import PersonaEngine
from plugins import analyze_video
from plugins.vision import describe_image, fetch_image
from session_manager import SessionManager


bot_interfaces = None
command_handler = None
persona_engine = None
session_manager = None
event_router = None
agent_orchestrator = None
user_sessions = {}

test_group = TEST_GROUPS


async def handle_image_message(image_urls, message_content):
    descriptions = []
    for url in image_urls:
        try:
            print(f"[Vision] Processing image: {url}")
            image_data = await fetch_image(url)
            if not image_data:
                descriptions.append("图片加载失败")
                continue
            desc = await describe_image(image_data, url)
            descriptions.append(desc)
        except Exception as exc:
            print(f"[Vision] Error processing image: {exc}")
            descriptions.append(f"图片处理错误")

    if descriptions:
        joined = " / ".join(descriptions)
        message_content += f"\n[图片内容: {joined}]"
    return message_content


async def process_multimodal_content(message_segments, message_content):
    image_urls = []
    video_urls = []
    audio_urls = []

    for part in message_segments:
        part_type = part.get("type")
        data = part.get("data", {})

        if part_type == "image":
            image_url = data.get("url") or data.get("file")
            if image_url:
                image_urls.append(image_url)

        if part_type == "video":
            video_url = data.get("url") or data.get("file")
            if video_url and str(video_url).startswith("http"):
                video_urls.append(video_url)

        if part_type == "record":
            audio_url = data.get("url") or data.get("file")
            if audio_url and str(audio_url).startswith("http"):
                audio_urls.append(audio_url)

    if image_urls:
        message_content = await handle_image_message(image_urls, message_content)

    for url in video_urls:
        message_content += await analyze_video(url)

    for url in audio_urls:
        message_content += await transcribe_audio(url)

    return message_content


async def handler_init(interfaces):
    global bot_interfaces, command_handler, user_sessions
    global persona_engine, session_manager, event_router, agent_orchestrator

    bot_interfaces = interfaces
    persona_engine = PersonaEngine(
        bot_interfaces["bot_qq"],
        bot_interfaces["test_if_super_user"],
    )

    memory = None
    if MEMORY_ENABLED:
        try:
            from memory import VectorMemory
            memory = VectorMemory(persist_dir=MEMORY_DB_PATH, search_results=MEMORY_SEARCH_RESULTS)
            print(f"[Memory] Vector memory initialized at {MEMORY_DB_PATH}")
        except Exception as exc:
            print(f"[Memory] Failed to initialize vector memory: {exc}")

    session_manager = SessionManager(
        bot_interfaces["bot_qq"],
        bot_interfaces["test_if_super_user"],
        memory=memory,
        window_size=MEMORY_WINDOW_SIZE,
    )
    user_sessions = session_manager.private_sessions
    command_handler = CommandHandler(
        interfaces,
        user_sessions,
        session_manager=session_manager,
    )
    agent_orchestrator = AgentOrchestrator(
        bot_interfaces,
        command_handler,
        persona_engine,
        session_manager,
        process_multimodal_content,
    )
    event_router = create_event_router()


async def handler_release():
    pass


def create_event_router():
    router = EventRouter()

    @router.message(lambda ctx: ctx.event.is_private, name="private_message", priority=10)
    async def private_message(ctx: BotContext):
        await handle_private_message(ctx.ws, ctx.event.raw)

    @router.message(
        lambda ctx: ctx.event.is_group and ctx.event.group_id in test_group,
        name="allowed_group_message",
        priority=10,
    )
    async def allowed_group_message(ctx: BotContext):
        await handle_group_message(ctx.ws, ctx.event.raw)

    return router


async def execute_function(ws, message):
    event = MessageEvent.from_onebot(message)
    if event is None:
        return

    print(message)
    ctx = BotContext(ws, bot_interfaces, event)
    await event_router.dispatch(ctx)


async def handle_group_message(ws, message):
    return await agent_orchestrator.handle_group_message(ws, message)


async def handle_private_message(ws, message):
    return await agent_orchestrator.handle_private_message(ws, message)
