import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from telegram.ext import Application, ApplicationBuilder

from bot.handlers.clipboard import register_clipboard_handlers
from bot.handlers.core import register_core_handlers
from bot.handlers.files import register_files_handlers
from bot.handlers.guardian import register_guardian_handlers
from bot.handlers.media import register_media_handlers
from bot.handlers.misc import register_misc_handlers
from bot.handlers.network import register_network_handlers
from bot.handlers.notepad import register_notepad_handlers
from bot.handlers.remote import register_remote_handlers
from bot.handlers.scheduler import register_scheduler_handlers
from bot.handlers.search import register_search_handlers
from bot.handlers.system import register_system_handlers
from bot.handlers.windows_mgr import register_windows_handlers

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ALLOWED_USER_ID = int(os.getenv('ALLOWED_USER_ID', '0'))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def _post_init(app: Application) -> None:
    from utils.proactive import ProactiveMonitor
    loop = asyncio.get_running_loop()
    monitor = ProactiveMonitor(app.bot, ALLOWED_USER_ID, loop)
    monitor.start()


def main() -> None:
    app: Application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )

    # Guardian first so /panic has priority
    register_guardian_handlers(app)
    register_system_handlers(app)
    register_files_handlers(app)
    register_clipboard_handlers(app)
    register_media_handlers(app)
    register_misc_handlers(app)
    register_network_handlers(app)
    register_notepad_handlers(app)
    register_remote_handlers(app)
    register_scheduler_handlers(app)
    register_search_handlers(app)
    register_windows_handlers(app)
    # Core last — MessageHandler catch-all must come after all CommandHandlers
    register_core_handlers(app)

    app.run_polling()


if __name__ == '__main__':
    main()
