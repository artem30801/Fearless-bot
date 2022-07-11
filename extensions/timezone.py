import re

import time

import dateparser
import pytz
from dateparser.date import DateDataParser
from dateparser.search import search_dates

from datetime import datetime

import naff
import beanie
from dateutil.relativedelta import relativedelta

from naff import SlashCommand, SlashCommandChoice, slash_str_option, slash_user_option, context_menu
from naff import InteractionContext, AutocompleteContext
from collections import defaultdict

from utils.fuzz import fuzzy_autocomplete
from utils.exceptions import InvalidArgument
from utils.db import Document
from utils.text import make_table, format_delta, clock_emojis
from utils.commands import manage_cmd

timezone_cmd = SlashCommand(name="timezone")
time_cmd = SlashCommand(name="time")

manage_timezone_cmd = manage_cmd.group("timezone")
timezone_styles = [SlashCommandChoice(item.name, item.name) for item in naff.TimestampStyles]


class UserTimezone(Document):
    user_id: int
    timezone: str

    @property
    def now(self):
        return datetime.now(pytz.timezone(self.timezone))

    @property
    def tz_info(self):
        return pytz.timezone(self.timezone)

    @property
    def abbreviation(self):
        return self.now.strftime("%Z")

    @property
    def offset(self):
        return TimezoneCmd.format_offset(self.now)

    @property
    def time_now(self):
        return self.now.strftime("%H:%M")

    @property
    def date_now(self):
        return self.now.strftime("%d.%m.%y")

    @property
    def weekday(self):
        return self.now.strftime("%A")

    @property
    def full(self):
        return TimezoneCmd.format_timezone(self.timezone)

    @classmethod
    async def from_member(cls, member: naff.Member, you=False) -> "UserTimezone":
        user_timezone = await cls.find({"user_id": member.id}).first_or_none()
        if not user_timezone:
            if you:
                raise InvalidArgument("You don't have a timezone set up!\n"
                                      "Use `/timezone set` command to set your timezone info")
            else:
                raise InvalidArgument(f"{member.mention} doesn't have a time zone set up!")
        return user_timezone


class TimezoneCmd(naff.Extension):
    def __init__(self, client):
        # timezones
        self.timezones = pytz.all_timezones

        self.abbreviations: defaultdict[str, list] = defaultdict(list)
        self.offsets: defaultdict[str, list] = defaultdict(list)

        for name in self.timezones:
            timezone = pytz.timezone(name)
            now = datetime.now(timezone)

            abbreviation = now.strftime("%Z")
            self.abbreviations[abbreviation].append(name)

            offset_variations = self._offset_variations(now)
            for offset in offset_variations:
                self.offsets[offset].append(name)

    @staticmethod
    def _offset_variations(now):
        offset = now.strftime("%z")
        sign, hours, minutes = offset[0], int(offset[1:3]), int(offset[3:])
        sign_variants = ["", "+"] if sign == "+" else ["-"]
        minutes_variants = ["", f"{minutes}"]
        v2 = f"{hours}"
        results = []
        for v1 in sign_variants:
            for v3 in minutes_variants:
                results.append(v1 + v2 + v3)
        return results

    @classmethod
    def format_timezone(cls, name):
        timezone = pytz.timezone(name)
        now = datetime.now(timezone)
        offset = cls.format_offset(now)
        abbreviation = now.strftime("%Z")
        return f"{offset} | {abbreviation} | {name} | {now.strftime('%H:%M')}"

    @staticmethod
    def format_offset(now):
        offset = now.strftime("%z")
        return f"UTC{offset[:3]}:{offset[3:]}"

    async def generic_timezone_set(self, member, timezone, you=False):
        embed = naff.Embed()

        user_timezone, created = await self.set_user_timezone(member.id, timezone)
        if created is not None:
            embed.description = f"Set {'your' if you else member.mention} timezone as `{user_timezone.abbreviation}`"
            if created:
                embed.color = naff.MaterialColors.GREEN
            else:
                embed.color = naff.MaterialColors.INDIGO
        else:
            embed.description = f"{'Your' if you else member.mention} timezone is already set as `{user_timezone.abbreviation}`"
            embed.color = naff.MaterialColors.PURPLE

        embed.fields.append(self.get_user_field(user_timezone))
        return embed

    @timezone_cmd.subcommand("set")
    async def timezone_set(
            self,
            ctx: InteractionContext,
            timezone: slash_str_option(
                "specify as: offset (+3, -3) or nearest country or principal city (Brussels, US) or abbreviation",
                required=True,
                autocomplete=True,
            ),
    ):
        """Set your timezone for all further commands"""
        await ctx.defer(ephemeral=True)
        embed = await self.generic_timezone_set(ctx.author, timezone, you=True)
        await ctx.send(embed=embed)

    @timezone_set.autocomplete("timezone")
    async def timezone_set_autocomplete(self, ctx: AutocompleteContext, timezone: str, **_):
        return await self.timezone_autocomplete(ctx, timezone)

    @manage_timezone_cmd.subcommand("set")
    async def manage_timezone_set(
            self,
            ctx: InteractionContext,
            member: slash_user_option("member to set timezone to", required=True),
            timezone: slash_str_option(
                "specify as: offset (+3, -3) or nearest country or principal city (Brussels, US) or abbreviation",
                required=True,
                autocomplete=True,
            ),
    ):
        """Set timezone of the member"""
        await ctx.defer(ephemeral=True)
        embed = await self.generic_timezone_set(member, timezone, you=False)
        await ctx.send(embed=embed)

    @manage_timezone_set.autocomplete("timezone")
    async def manage_timezone_set_autocomplete(self, ctx: AutocompleteContext, timezone: str, **_):
        return await self.timezone_autocomplete(ctx, timezone)

    @staticmethod
    async def generic_timezone_clear(member, you=False):
        user_timezone = await UserTimezone.from_member(member, you=you)
        await user_timezone.delete()
        embed = naff.Embed(color=naff.MaterialColors.DEEP_ORANGE)
        embed.description = f"Cleared {'your' if you else member.mention} timezone info!"
        if you:
            embed.description += f"\n Who are you exactly, again?"
        return embed

    @timezone_cmd.subcommand("clear")
    async def timezone_clear(self, ctx: InteractionContext):
        """Clear your timezone info"""
        await ctx.defer(ephemeral=True)
        embed = await self.generic_timezone_clear(ctx.author, you=True)
        await ctx.send(embed=embed)

    @manage_timezone_cmd.subcommand("clear")
    async def manage_timezone_clear(
            self,
            ctx: InteractionContext,
            member: slash_user_option("member to clear timezone from", required=True),
    ):
        """Clear timezone info of the member"""
        await ctx.defer(ephemeral=True)
        embed = await self.generic_timezone_clear(member, you=False)
        await ctx.send(embed=embed)

    async def generic_time_info(self, ctx: InteractionContext, member: naff.Member, user_timezone: UserTimezone):
        embed = naff.Embed(color=naff.MaterialColors.BLUE)
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.description = f"For: {member.mention}"
        embed.fields.append(self.get_user_field(user_timezone))
        await ctx.send(embed=embed)

    @time_cmd.subcommand("me")
    async def time_me(self, ctx: InteractionContext):
        """Send information about your time"""
        member: naff.Member = ctx.author
        user_timezone = await UserTimezone.from_member(member, you=True)
        await self.generic_time_info(ctx, member, user_timezone)

    @time_cmd.subcommand("member")
    async def time_member(
            self,
            ctx: InteractionContext,
            member: slash_user_option("member to show time info about", required=True),
    ):
        """Send information about member's time"""
        member: naff.Member
        user_timezone = await UserTimezone.from_member(member, you=False)
        await self.generic_time_info(ctx, member, user_timezone)

    @time_cmd.subcommand("compare_member")
    async def time_compare_member(
            self,
            ctx: InteractionContext,
            member: slash_user_option("member to compare time info with", required=True),
    ):
        """Compare time information with member's time"""
        if ctx.author == member:
            raise InvalidArgument("Hahaha, stop. You're trying to compare youself to *yourself*?\n"
                                  "Of course you're the best *you* out there, even in timezones!\n"
                                  )

        your_timezone = await UserTimezone.from_member(ctx.author, you=False)
        user_timezone = await UserTimezone.from_member(member, you=False)

        embed = naff.Embed(color=naff.MaterialColors.BLUE)
        embed.fields.append(self.get_user_field(your_timezone, member=ctx.author))
        embed.fields.append(self.get_user_field(user_timezone, member=member))

        delta = relativedelta(user_timezone.now.replace(tzinfo=None), your_timezone.now.replace(tzinfo=None))
        if not delta:
            delta_text = f"No time difference between {ctx.author.mention} and {member.mention}!"
        else:
            delta_format = format_delta(delta, positive=True)
            direction = "ahead" if abs(delta) != delta else "behind"
            delta_text = f"{ctx.author.mention} time is *{delta_format}* **{direction}** {member.mention} time"

        embed.add_field(name="Time difference", value=delta_text)

        await ctx.send(embed=embed)

    @time_cmd.subcommand("timestamps")
    async def time_timestamps(self, ctx: InteractionContext,
                              time: slash_str_option("time to convert into discord timestamp", required=True,
                                                     autocomplete=True),
                              style: slash_str_option("style of discord timestamp to use", required=False,
                                                      choices=timezone_styles) = None,
                              ):
        """Converts specified time into discord built-in timestamp formats for you to copy-paste"""
        d, t = await self.parse_time(ctx.author, time)
        timestamp = naff.Timestamp.fromdatetime(d)
        embed = naff.Embed(color=naff.MaterialColors.BLUE)
        if style is None:
            embed.description = f"Target time: {d.strftime('%c')}"
            rows = [[style.name, timestamp.format(style), timestamp.format(style)] for style in naff.TimestampStyles]
            embed.add_field(name="Timestamp variants:",
                            value="\n".join(make_table(rows, [True, True, False]))
                            )
            embed.set_footer("Copy-paste text from the second column into your message textbox to send timestamp")
        else:
            # for mobile, mostly
            style_obj = naff.TimestampStyles[style]
            embed.description = f"`{timestamp.format(style_obj)}`"
            embed.add_field(name=f"{style_obj.name} timestamp",
                            value=f"{timestamp.format(style_obj)}\n"
                            )
            embed.set_footer(
                "Copy-paste text from the embed (long tap on mobile) \ninto your message textbox to send timestamp")

        await ctx.send(embed=embed, ephemeral=True)

    @time_timestamps.autocomplete("time")
    async def time_timestamps_autocomplete(self, ctx: AutocompleteContext, time: str, **_):
        return await self.time_autocomplete(ctx, time)

    @context_menu(name="Detect datetimes", context_type=naff.CommandTypes.MESSAGE)
    async def time_message_context(self, ctx: InteractionContext):
        message: naff.Message = ctx.target
        user_timezone = await UserTimezone.from_member(message.author)
        embed = self.generic_datetime_detect(message, user_timezone)

        await ctx.send(embed=embed)

    @context_menu(name="Get time info", context_type=naff.CommandTypes.USER)
    async def time_user_context(self, ctx: InteractionContext):
        member: naff.Member = ctx.target
        user_timezone = await UserTimezone.from_member(member, you=False)
        await self.generic_time_info(ctx, member, user_timezone)

    @naff.listen()
    async def on_message_reaction_add(self, event: naff.events.MessageReactionAdd):
        if event.emoji.name not in clock_emojis:
            return
        message = event.message
        count = sum(reaction.count for reaction in message.reactions if reaction.emoji.name in clock_emojis)
        if count != 1:
            return

        try:
            user_timezone = await UserTimezone.from_member(message.author)
            embed = self.generic_datetime_detect(message, user_timezone, add_quote=False)
        except InvalidArgument as e:
            embed = naff.Embed(color=naff.MaterialColors.RED)
            embed.description = str(e)[:2000]
            await message.reply(embed=embed, allowed_mentions=naff.AllowedMentions.none())
        else:
            await message.reply(embed=embed, allowed_mentions=naff.AllowedMentions.none())

    @staticmethod
    def generic_datetime_detect(message: naff.Message, user_timezone: UserTimezone, add_quote=True):
        to_detect = message.content.replace("*", "")
        to_detect = to_detect.strip()

        base = datetime.fromtimestamp(time.mktime(message.timestamp.timetuple()))
        base = pytz.UTC.localize(base).astimezone(None)
        settings = {"PREFER_DATES_FROM": "future", "RELATIVE_BASE": base}
        languages = ["en"]

        try:
            detected = search_dates(to_detect, settings=settings, languages=languages)
        except ValueError:
            raise InvalidArgument("Cannot detect language of the message or it is unsupported!")

        if detected is None:
            # sanity check because somtimes search_dates does not get datetime if it is not surrounded by anything
            parsed = dateparser.parse(to_detect, settings=settings, languages=languages)
            if parsed is None:
                raise InvalidArgument("No dates nor times were detected in the message!")
            detected = [(to_detect, parsed)]
        else:
            def process(chunk: str, t: datetime):
                # sanity check because somtimes search_dates gets AM as months etc
                parsed = dateparser.parse(chunk, settings=settings, languages=languages)
                if parsed is not None and parsed != t:
                    return chunk, parsed
                return chunk, t

            detected = [process(chunk, t) for chunk, t in detected]

        def localize(t: datetime):
            # sometimes user can explicitly specify time in the message
            if t.tzinfo is None:
                return t.astimezone(user_timezone.tz_info)
            return t

        detected = [(chunk, naff.Timestamp.fromdatetime(localize(t))) for chunk, t in detected]

        embed = naff.Embed(color=naff.MaterialColors.BLUE)
        embed.timestamp = message.timestamp
        embed.set_footer("Original message sent")

        if add_quote:
            embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.display_avatar.url,
                url=message.jump_url,
            )

            content = to_detect
            for chunk, _ in detected:
                pos = content.find(chunk)
                content = content[:pos + len(chunk)] + "**" + content[pos + len(chunk):]
                content = content[:pos] + "**" + content[pos:]
            embed.description = f">>> {content}"

        if len(detected) > 1:
            rows = [[chunk,
                     f"{t.format(naff.TimestampStyles.ShortDateTime)} ({t.format(naff.TimestampStyles.RelativeTime)})"]
                    for chunk, t in detected]
            detected_text = "\n".join(make_table(rows, [True, False]))
        else:
            t = detected[0][1]
            detected_text = f"{t.format(naff.TimestampStyles.ShortDateTime)} ({t.format(naff.TimestampStyles.RelativeTime)})"
            # detected_text += f"\n{t.strftime('%c %Z')}"

        detected_text = f"Original timezone: *{user_timezone.abbreviation} ({user_timezone.offset})*\n{detected_text}"
        embed.add_field(name="Detected dates and times:", value=detected_text)
        return embed

    @staticmethod
    def get_user_field(user_timezone: UserTimezone, member: naff.Member | None = None):
        lines = [
            ["Timezone", user_timezone.abbreviation],
            ["Time offset", user_timezone.offset],
            ["Time now", user_timezone.time_now],
            ["Weekday now", user_timezone.weekday],
        ]

        value = '\n'.join(make_table(lines, [True, True]))
        name = f"{member.display_name}'s time info" if member else "Time info"
        field = naff.EmbedField(
            name=name,
            value=value,
            inline=True,
        )

        return field

    async def set_user_timezone(self, user_id: int, timezone_name: str):
        timezone = self.get_timezone(timezone_name)
        user_timezone = await UserTimezone.find({"user_id": user_id}).first_or_none()
        if not user_timezone:
            user_timezone = UserTimezone(user_id=user_id, timezone=timezone)
            created = True
        elif user_timezone.timezone == timezone:
            created = None
        else:
            user_timezone.timezone = timezone
            created = False

        await user_timezone.save()
        return user_timezone, created

    def get_timezone(self, query: str):
        query = query.strip()
        if query in self.timezones:
            return query
        results = self.get_timezone_results(query)
        if results:
            return results[0][0]

        raise InvalidArgument(f"Timezone {query} not found!")

    @staticmethod
    def expand_results(
            fuzzy_results: list,
            data_dict: dict[str, list[str]],
            additional_score: int = 0,
    ) -> list[tuple[str, int]]:
        results = []
        for key, score, _ in fuzzy_results:
            entries = [(name, score + additional_score) for name in data_dict[key]]
            results.extend(entries)
        return results

    def get_timezone_results(self, query: str):
        # Search by offsets and append all timezones with matching offsets to the results
        query = query.strip()
        results = []

        if not re.search('[a-zA-Z]', query):
            offset_str = re.sub(r"[^1-9+-]", "", query)
            offsets = self.offsets.get(offset_str)
            if offsets:
                results = [(name, 100) for name in offsets]

        if not results:
            # Search by abbreviations and append all timezones with matching abbreviations to the results
            fuzzy_results = fuzzy_autocomplete(query, list(self.abbreviations.keys()))
            results.extend(self.expand_results(fuzzy_results, self.abbreviations, additional_score=-10))

            # Search by full timezone names
            results.extend(fuzzy_autocomplete(query, self.timezones))

            # TODO most popular timezones if empty

            # Sort by score and name, the highest score LAST
            # print("PRE SORT", results)
            results.sort(key=lambda item: item[1])
            # Convert to dict and then back to list to make sure that there are no duplicates in names
            # This way, results with the highest score override results with the lowest score
            results = {name: score for name, score, *_ in results}
            results = [(name, score) for name, score in results.items()]
            # Sort by score and name, the highest score FIRST (bc dict conversion scrambles order)
            results.sort(key=lambda item: item[0], reverse=False)
            results.sort(key=lambda item: item[1], reverse=True)

        return results

    async def timezone_autocomplete(self, ctx: AutocompleteContext, query: str):
        # Leave 25 best results
        results = self.get_timezone_results(query)
        results = results[:25]
        # Format output
        results = [{"name": self.format_timezone(name), "value": name} for name, score in results]
        await ctx.send(results)

    @staticmethod
    async def parse_time(member: naff.Member, query: str):
        query = query.strip()
        if not query:
            raise InvalidArgument("Input time in any format including natural language (in five minutes, etc)")

        settings = {"PREFER_DATES_FROM": "future"}
        parser = DateDataParser(settings=settings)

        data = parser.get_date_data(query)
        d = data.date_obj

        if d is not None:
            if d.tzname() is None:
                try:
                    user_timezone = await UserTimezone.from_member(member, you=True)
                except InvalidArgument:
                    raise InvalidArgument("You don't have a timezone set up!\n"
                                          "Use `/timezone set` command to set your timezone info "
                                          "or insert timezone name into your query")
                d = d.astimezone(tz=user_timezone.tz_info)

            t = time.mktime(d.astimezone(None).timetuple())
            return d, t
        else:
            raise InvalidArgument(f"Cannot interpret `{query}` as a valid time")

    async def time_autocomplete(self, ctx: AutocompleteContext, query: str):
        try:
            d, t = await self.parse_time(ctx.author, query)
        except InvalidArgument as e:
            suggestion = {"name": str(e), "value": "0"}
        else:
            suggestion = {"name": f"Interpreted as: {d.strftime('%c %Z')}", "value": str(t)}
        await ctx.send([suggestion])


def setup(bot):
    bot.add_model(UserTimezone)
    TimezoneCmd(bot)
