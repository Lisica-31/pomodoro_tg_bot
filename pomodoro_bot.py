import asyncio
from os import getenv
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from data_base import init_db

from handlers.starthelp import router as starthelp_router
from handlers.session_setup import router as session_setup_router
from handlers.session_commands import router as session_commands_router
from handlers.archive_commands import router as archive_commands_router
from handlers.templates_commands import router as templates_commands_router


load_dotenv()
bot_token = getenv ('bot_token')
bot = Bot(token=bot_token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


dp.include_router(starthelp_router)
dp.include_router(session_setup_router)
dp.include_router(session_commands_router)
dp.include_router(archive_commands_router)
dp.include_router(templates_commands_router)

init_db()
