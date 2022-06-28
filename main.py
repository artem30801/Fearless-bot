import os
import logging
import inspect
import asyncio
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

import naff
import beanie
import jurigged
from naff import InteractionContext
from motor import motor_asyncio

from config import load_settings
from utils.exceptions import BotError, HandledError, send_error

logger = logging.getLogger()


class Bot(naff.Client):
    def __init__(self, current_dir, config):
        self.current_dir: Path = current_dir
        self.config = config

        super().__init__(
            intents=naff.Intents.DEFAULT,
            sync_interactions=True,
            delete_unused_application_cmds=True,
            asyncio_debug=self.config.debug,
            activity="with lightning",
            debug_scope=self.config.debug_scope or naff.MISSING,
            default_prefix=["!", naff.MENTION_PREFIX],
        )

        self.db: motor_asyncio.AsyncIOMotorClient | None = None
        self.models = list()

    def get_all_extensions(self):
        current = set(inspect.getmodule(ext).__name__ for ext in self.ext.values())
        search = (self.current_dir / "extensions").glob("*.py")
        files = set(path.relative_to(self.current_dir).with_suffix("").as_posix().replace("/", ".") for path in search)

        return current | files

    def add_model(self, model):
        self.models.append(model)

    async def startup(self):
        for extension in self.get_all_extensions():
            try:
                self.load_extension(extension)
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")

        if self.config.debug:
            self.load_extension("naff.ext.debug_extension")

        self.db = motor_asyncio.AsyncIOMotorClient(self.config.database_address)
        await beanie.init_beanie(database=self.db.fearless, document_models=self.models)
        await self.astart(self.config.discord_token)

    async def on_command_error(self, ctx: InteractionContext, error: Exception, *args, **kwargs):
        if isinstance(error, HandledError):
            pass
        elif isinstance(error, BotError):
            await send_error(ctx, str(error))
        else:
            await super().on_command_error(ctx, error, *args, **kwargs)


def main():
    config = load_settings()
    if config.debug:
        jurigged.watch()

    current_dir = Path(__file__).parent

    logs_dir = current_dir / "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    handlers = [
        TimedRotatingFileHandler(logs_dir / f"bot.log", when="W0", encoding="utf-8"),  # files rotate weekly at mondays
        logging.StreamHandler(),
    ]

    log_level = logging.DEBUG if config.debug else logging.INFO

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)-9.9s]-[%(name)-15.15s]: %(message)s")

    # logging.setLoggerClass(log_utils.BotLogger)
    naff_logger = logging.getLogger(naff.logger_name)
    naff_logger.setLevel(log_level)

    logger.setLevel(log_level)

    for handler in handlers:
        handler.setFormatter(formatter)
        handler.setLevel(log_level)

        logger.addHandler(handler)

    bot = Bot(current_dir, config)
    asyncio.run(bot.startup())


if __name__ == "__main__":
    main()
