import naff
from naff import slash_str_option, slash_int_option, slash_bool_option
from naff import InteractionContext, AutocompleteContext, Permissions
from naff.client.utils import TTLCache

from utils.intractions import yes_no
from utils.exceptions import InvalidArgument
from utils.text import make_table, format_entry, pluralize
from utils.commands import manage_cmd, list_cmd, info_cmd, generic_rename, generic_move, generic_autocomplete

from extensions.character_models import Character, Scene, Chapter

chapter_cmd = manage_cmd.group("chapter")


class ChapterCmd(naff.Extension):
    def __init__(self, client):
        self.last_chapter = TTLCache(ttl=60*60, soft_limit=100, hard_limit=250)

    def set_last_chapter(self, ctx: naff.Context, chapter_obj: Chapter):
        self.last_chapter[ctx.author.id] = chapter_obj.id

    def clear_last_chapter(self, ctx: naff.Context):
        self.last_chapter.pop(ctx.author.id, None)

    def get_last_chapter(self, ctx: naff.Context):
        return self.last_chapter.get(ctx.author.id, None)

    @chapter_cmd.subcommand("create")
    async def chapter_create(
            self,
            ctx: InteractionContext,
            name: slash_str_option("chapter name", required=True),
    ):
        """Adds a new chapter"""
        await ctx.defer(ephemeral=True)
        chapter_obj = Chapter(name=name)
        await chapter_obj.insert()
        self.set_last_chapter(ctx, chapter_obj)

        embed = naff.Embed(color=naff.MaterialColors.GREEN)
        embed.description = f"Created chapter '**{chapter_obj.name}**' (**#{chapter_obj.number}**)"
        embed.fields.append(await self.chapters_field())
        await ctx.send(embed=embed)

    @chapter_cmd.subcommand("remove")
    async def chapter_remove(
            self,
            ctx: InteractionContext,
            chapter: slash_str_option("chapter to remove", required=True, autocomplete=True),
    ):
        """Removes a chapter"""
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)
        await chapter_obj.fetch_all_links()
        await chapter_obj.delete()
        async for scene in chapter_obj.scenes:
            await scene.delete()
        self.clear_last_chapter(ctx)

        embed = naff.Embed(color=naff.MaterialColors.DEEP_ORANGE)
        embed.description = f"Removed chapter '**{chapter_obj.name}**'"
        embed.fields.append(await self.chapters_field())
        await ctx.send(embed=embed)

    @chapter_remove.autocomplete("chapter")
    async def chapter_remove_autocomplete(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_autocomplete(ctx, chapter)

    @chapter_cmd.subcommand("rename")
    async def chapter_rename(
            self,
            ctx: InteractionContext,
            chapter: slash_str_option("chapter to rename", required=True, autocomplete=True),
            new_name: slash_str_option("new name for the chapter", required=True),
    ):
        """Renames a chapter"""
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)
        self.set_last_chapter(ctx, chapter_obj)

        embed = await generic_rename(chapter_obj, "chapter", new_name)
        embed.fields.append(await self.chapters_field(highlight=chapter_obj))
        await ctx.send(embed=embed)

    @chapter_rename.autocomplete("chapter")
    async def chapter_rename_autocomplete(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_autocomplete(ctx, chapter)

    @chapter_cmd.subcommand("move")
    async def chapter_move(
            self,
            ctx: InteractionContext,
            chapter: slash_str_option("chapter to move", required=True, autocomplete=True),
            new_position: slash_int_option("new number for the chapter", required=True, min_value=1),
    ):
        """Changes a position (number) of the chapter"""
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)
        self.set_last_chapter(ctx, chapter_obj)

        embed = await generic_move(chapter_obj, "chapter", new_position)
        embed.fields.append(await self.chapters_field(highlight=chapter_obj))
        await ctx.send(embed=embed)

    @chapter_move.autocomplete("chapter")
    async def chapter_move_autocomplete(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_autocomplete(ctx, chapter)

    @list_cmd.subcommand("chapters")
    async def chapter_list(self, ctx: InteractionContext,
                           list_scenes: slash_bool_option("whether to show all scenes in chapters", required=False) = True,
                           ):
        """List all chapters"""
        await ctx.defer()
        embed = naff.Embed(description="", color=naff.MaterialColors.LIGHT_BLUE)

        show_scenes_count = True
        chapters = await Chapter.all().sort("+number").to_list()

        if not list_scenes:
            async def make_row(chapter: Chapter):
                row = [chapter.fullname]
                if show_scenes_count:
                    scenes_count = await chapter.scenes.count()
                    row.append(pluralize(scenes_count, "scene"))
                return row

            wrap_column = [True]
            if show_scenes_count:
                wrap_column.append(True)

            chapters_rows = [await make_row(chapter) for chapter in chapters]
            chapters_text = "\n".join(make_table(chapters_rows, wrap_column))
            # embed.add_field(name=f"Chapters [{len(chapters)} total]", value=chapters_text)
            embed.title = f"Chapters list"
            embed.description = chapters_text
        else:
            embed.title = "Chapters and scenes list"
            for chapter in chapters:
                scenes = await chapter.scenes.to_list()
                scenes_text = "\n".join([f"{scene.number}. *{scene.name}*" for scene in scenes])
                embed.add_field(name=f"{chapter.fullname}", value=scenes_text or "No scenes!")

        await ctx.send(embed=embed)

    async def chapter_autocomplete(self, ctx: AutocompleteContext, query: str, only_with_scenes: bool = False):
        db_query = Chapter.all().sort("+number")
        if only_with_scenes:
            scenes = await Scene.all().to_list()
            chapter_ids = {scene.chapter.ref.id for scene in scenes}
            db_query = db_query.find({"_id": {"$in": list(chapter_ids)}})

        last_chapter_id = self.get_last_chapter(ctx)

        results = await generic_autocomplete(query, db_query, last_chapter_id, use_numbers=True)
        results = [{"name": f"{chapter.number}. {chapter.name}", "value": chapter.name} for chapter in results]
        await ctx.send(results)

    @classmethod
    async def chapters_field(cls, highlight=None):
        chapters = await Chapter.all().sort("+number").to_list()

        field = naff.EmbedField(
            name=f"Chapters [{len(chapters)} total]:",
            value="\n".join([format_entry(chapter, highlight) for chapter in chapters])
        )

        return field


def setup(bot):
    ChapterCmd(bot)
