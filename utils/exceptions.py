import logging
from contextlib import asynccontextmanager

import naff


class BotError(Exception):
    pass


class HandledError(BotError):
    pass


class InvalidArgument(BotError):
    pass


async def send_error(ctx: naff.Context, msg: str):
    if not ctx.responded:
        embed = naff.Embed(color=naff.MaterialColors.RED)
        embed.description = msg[:2000]
        await ctx.send(embed=embed, allowed_mentions=naff.AllowedMentions.none(), ephemeral=True)
    else:
        logging.warning(f"Already responded to message, error message: {msg}")


@asynccontextmanager
async def edit_origin_exception(ctx: naff.ComponentContext):
    try:
        yield
    except BotError as e:
        await ctx.edit_origin(
            str(e), embeds=[], components=[], files=[],
            allowed_mentions=naff.AllowedMentions.none(),
        )
        raise HandledError()
