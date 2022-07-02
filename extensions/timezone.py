import re
import naff
import beanie
import pytz
from naff import subcommand, slash_str_option
from naff import InteractionContext, AutocompleteContext
from collections import defaultdict
from datetime import datetime

from utils.fuzz import fuzzy_find_obj, fuzzy_autocomplete
from utils.exceptions import InvalidArgument


class TimezoneCmd(naff.Extension):
    def __init__(self, client):
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
                results.append(v1+v2+v3)
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

    @staticmethod
    def expand_results(fuzzy_results: list, data_dict: dict[str, list[str]], additional_score: int = 0) -> list[tuple[str, int]]:
        results = []
        for key, score, _ in fuzzy_results:
            entries = [(name, score + additional_score) for name in data_dict[key]]
            results.extend(entries)
        return results

    @subcommand(base="timezone", name="set")
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
        await ctx.send(timezone)

    @timezone_set.autocomplete("timezone")
    async def timezone_set_autocomplete(self, ctx: AutocompleteContext, timezone: str, **_):
        return await self.timezone_autocomplete(ctx, timezone)

    def get_timezone(self, query: str):
        query = query.strip()
        if query in pytz.common_timezones:
            return query
        results = self.get_timezone_results(query)
        if results:
            return results[0]

        raise InvalidArgument(f"Timezone {query} not found!")

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

    async def timezone_autocomplete(self, ctx: naff.Context, query: str):
        # Leave 25 best results
        results = self.get_timezone_results(query)
        results = results[:25]
        # Format output
        results = [{"name": self.format_timezone(name), "value": name} for name, score in results]
        await ctx.send(results)


abbreviations: defaultdict[str, list] = defaultdict(list)

for name in pytz.common_timezones:
    timezone = pytz.timezone(name)
    now = datetime.now(timezone)

    abbreviation = now.strftime("%Z")
    abbreviations[abbreviation].append(name)

print(abbreviations)
print(len(abbreviations))

# abbreviations: defaultdict[str, list] = defaultdict(list)
# offsets: defaultdict[str, list] = defaultdict(list)
#
# for name in pytz.common_timezones:
#     timezone = pytz.timezone(name)
#     now = datetime.now(timezone)
#     offset = Timezones.format_offset(now)
#     abbreviation = now.strftime("%Z")
#
#     offsets[offset].append(name)
#     abbreviations[abbreviation].append(name)

# print(offsets)
# print(abbreviations)
#
# results = Timezones.expand_results("+3", offsets)
# results = [Timezones.format_timezone(name) + f" | {score}" for name, score in results]
# print(results)
# print(pytz.common_timezones)

def setup(bot):
    TimezoneCmd(bot)

