import enum
import traceback
import logging
from typing import TYPE_CHECKING
from datetime import datetime, timedelta, timezone
from functools import partial

import naff
from naff import client
import pytz
import beanie
from naff import subcommand, slash_str_option, slash_channel_option, slash_bool_option
from naff import InteractionContext, AutocompleteContext
from collections import defaultdict

from utils.fuzz import fuzzy_find_obj, fuzzy_autocomplete
from utils.exceptions import InvalidArgument
from utils.commands import manage_cmd
from utils.db import Document

if TYPE_CHECKING:
    from extensions.timezone import TimezoneCmd

logger = logging.getLogger(__name__)

info_bar_cmd = manage_cmd.group("info_bar")


class ClockBarChannel(Document):
    guild_id: int
    channel_id: int
    timezone: str
    prefix: str = ""
    postfix: str = ""
    show_timezone: bool = True
    h24: bool = True

    @beanie.before_event(beanie.ValidateOnSave)
    async def validate_db(self):
        # validate name
        cls = self.__class__
        if await cls.find(cls.channel_id == self.channel_id, cls.id != self.id).exists():
            raise InvalidArgument(f"Clock bar for channel `{self.channel_id}` already exists!")

    async def channel(self, bot: naff.Client) -> naff.GuildChannel:
        return await bot.fetch_channel(self.channel_id)


class MinuteIntervalTrigger(naff.BaseTrigger):
    """
    Trigger the task every set interval.
    """

    _t = int | float

    def __init__(self, minutes: _t = 0) -> None:
        self.delta_minutes = minutes
        self.delta = timedelta(minutes=self.delta_minutes)

        # lazy check for negatives
        if (datetime.now() + self.delta) < datetime.now():
            raise ValueError("Interval values must result in a time in the future!")

    def next_fire(self) -> datetime:
        t = self.last_call_time + self.delta
        t = datetime(t.year, t.month, t.day, t.hour, t.minute - t.minute % self.delta_minutes, 5)
        return t


class InfoBarCmd(naff.Extension):
    def __init__(self, client):
        self.clock_bars = list()
        self.clock_bar_task = None
        self.clock_bar_minutes = 10

    @naff.listen()
    async def on_startup(self, *args, **kwargs):
        print("STARTUP", args, kwargs)
        self.clock_bar_task = naff.Task(
            self._update_clock_bar_task,
            MinuteIntervalTrigger(minutes=self.clock_bar_minutes),
        )
        await self._refresh_clock_bars_cache()
        await self._update_clock_bar_task()
        self.clock_bar_task.start()

    async def _update_clock_bar_task(self):
        for clock_bar in self.clock_bars.copy():
            try:
                await self._update_clock_bar(clock_bar)
            except InvalidArgument as e:
                embed = naff.Embed(color=naff.MaterialColors.RED)
                embed.description = str(e)
                guild = await self.bot.fetch_guild(clock_bar.guild_id)
                await guild.system_channel.send(embed=embed)

    async def _update_clock_bar(self, clock_bar: ClockBarChannel):
        channel = await clock_bar.channel(self.bot)
        try:
            await channel.edit(name=self._get_clock_bar_name(clock_bar))
        except Exception as e:
            logger.warning(
                f"Could not edit channel {channel} name for clock bar {clock_bar} in {channel.guild}, removing it: {e}")
            traceback.print_exc()
            try:
                self.clock_bars.remove(clock_bar)
            except ValueError:
                pass
            await clock_bar.delete()
            await self._refresh_clock_bars_cache()

            channel = channel.mention if channel is not None else f"`{clock_bar.channel_id}`"
            raise InvalidArgument(
                f"Could not edit channel {channel} name.\n"
                f"Maybe it was deleted or I don't have channel editing permissions.\n"
                f"Anyway, I won't be updating it."
            )

    async def _refresh_clock_bars_cache(self):
        self.clock_bars = await ClockBarChannel.all().to_list()

    @staticmethod
    def _get_clock_bar_name(clock_bar: ClockBarChannel):
        timezone = pytz.timezone(clock_bar.timezone)
        now = datetime.now(timezone)
        abbreviation = now.strftime("%Z") if clock_bar.show_timezone else ""
        time_str = now.strftime("%H:%M") if clock_bar.h24 else now.strftime("%I:%M %p")
        return f"{clock_bar.prefix} {time_str} {abbreviation} {clock_bar.postfix}"

    @info_bar_cmd.subcommand("create_clock")
    async def clock_create(
            self,
            ctx: InteractionContext,
            channel: slash_channel_option("channel to convert into clock info bar", required=True, channel_types=[naff.ChannelTypes.GUILD_VOICE]),
            timezone: slash_str_option("timezone to use for the clock", required=True, autocomplete=True),
            prefix: slash_str_option("clock prefix", required=False) = "",
            postfix: slash_str_option("clock postfix", required=False) = "",
            show_timezone: slash_bool_option("whether to show timezone in the clock", required=False) = True,
            h24: slash_bool_option("whether to show time in 24 hour format", required=False) = True,
    ):
        await ctx.defer(ephemeral=True)
        clock_bar = ClockBarChannel(
            guild_id=ctx.guild.id,
            channel_id=channel.id,
            timezone=timezone,
            prefix=prefix,
            postfix=postfix,
            show_timezone=show_timezone,
            h24=h24,
        )
        """Makes a name of the voice channel act like a clock bar, periodically updated with current time"""
        await clock_bar.save()
        await self._update_clock_bar(clock_bar)
        await self._refresh_clock_bars_cache()

        channel = await clock_bar.channel(self.bot)
        embed = naff.Embed(color=naff.MaterialColors.GREEN)
        embed.description = f"Successfully created auto-updated clock bar for channel {channel.mention}"
        await ctx.send(embed=embed)

    @clock_create.autocomplete("timezone")
    async def clock_create_autocomplete(self, ctx: AutocompleteContext, timezone: str, **_):
        return await self.timezone_ext.timezone_autocomplete(ctx, timezone)

    @info_bar_cmd.subcommand("remove_clock")
    async def clock_remove(
            self,
            ctx: InteractionContext,
            channel: slash_channel_option("channel to convert into clock info bar", required=True, channel_types=[naff.ChannelTypes.GUILD_VOICE]),
    ):
        """Removes clock bar (not channel itself) and stops all the updates"""
        await ctx.defer(ephemeral=True)
        clock_bar = ClockBarChannel.find({"channel_id": channel.id}).first_or_none()
        if clock_bar is None:
            raise InvalidArgument(f"Channel {channel.mention} is not associated with any clock bar!")

        await clock_bar.delete()
        await self._refresh_clock_bars_cache()

        embed = naff.Embed(color=naff.MaterialColors.DEEP_ORANGE)
        embed.description = f"Removed clock bar from channel {channel.mention}"
        await ctx.send(embed=embed)

    @property
    def timezone_ext(self) -> "TimezoneCmd":
        return self.bot.get_ext("TimezoneCmd")  # type: ignore


def setup(bot):
    bot.add_model(ClockBarChannel)
    InfoBarCmd(bot)
