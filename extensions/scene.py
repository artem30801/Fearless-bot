import naff
from naff import slash_str_option, slash_int_option
from naff import InteractionContext, AutocompleteContext, Permissions

from utils.fuzz import fuzzy_autocomplete
from utils.intractions import yes_no
from utils.exceptions import InvalidArgument
from utils.commands import manage, generic_rename

from extensions.character_models import Character, Scene, Chapter

chapter_cmd = manage.group("chapter")


class SceneCmd(naff.Extension):
    @chapter_cmd.subcommand("create")
    async def chapter_create(
            self,
            ctx: InteractionContext,
            name: slash_str_option("chapter name", required=True),
    ):
        """Adds a new chapter"""
        await ctx.defer(ephemeral=True)
        chapter = Chapter(name=name)
        await chapter.insert()

        embed = naff.Embed(color=naff.MaterialColors.GREEN)
        embed.description = f"Created chapter '**{chapter.name}**' (**#{chapter.number}**)"
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
        embed = await generic_rename(ctx, chapter_obj, "chapter", new_name)
        await ctx.send(embed=embed)

    @chapter_rename.autocomplete("chapter")
    async def chapter_rename_autocomplete(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_autocomplete(ctx, chapter)

    @chapter_cmd.subcommand("move")
    async def chapter_move(
            self,
            ctx: InteractionContext,
            chapter: slash_str_option("chapter to rename", required=True, autocomplete=True),
            new_position: slash_int_option("new number for the chapter", required=True, min_value=1),
    ):
        """Changes a position (number) of the chapter"""
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)
        old_number = chapter_obj.number
        chapter_obj.number = new_position
        await chapter_obj.save()
        embed = naff.Embed()
        if old_number == chapter_obj.number:
            embed.color = naff.MaterialColors.PURPLE
            embed.description = f"Position of the chapter '**{chapter_obj.name}**' did not change (**#{chapter_obj.number}**)"
        else:
            embed.color = naff.MaterialColors.INDIGO
            embed.description = f"Moved chapter '**{chapter_obj.name}**' from position **#{old_number}** to **#{chapter_obj.number}**"
        embed.fields.append(await self.chapters_field(highlight=chapter_obj))
        await ctx.send(embed=embed)

    @chapter_move.autocomplete("chapter")
    async def chapter_move_autocomplete(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_autocomplete(ctx, chapter)

    # Scene commands

    @chapter_cmd.subcommand("add_scene")
    async def chapter_add_scene(
            self,
            ctx: InteractionContext,
            chapter: slash_str_option("chapter to add scene to", required=True, autocomplete=True),
            name: slash_str_option("scene name", required=True),
    ):
        """Adds a scene to the chapter"""
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)
        scene_obj = Scene(name=name, chapter=chapter_obj)
        await scene_obj.save()

        embed = naff.Embed(color=naff.MaterialColors.GREEN)
        embed.description = f"Added scene '**{scene_obj.name}**' to chapter '**{chapter_obj.name}**'"
        await ctx.send(embed=embed)

    @chapter_add_scene.autocomplete("chapter")
    async def chapter_add_scene_autocomplete(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_autocomplete(ctx, chapter)

    @chapter_cmd.subcommand("remove_scene")
    async def chapter_remove_scene(
            self,
            ctx: InteractionContext,
            chapter: slash_str_option("chapter to remove scene from", required=True, autocomplete=True),
            scene: slash_str_option("scene to remove", required=True, autocomplete=True),
    ):
        """Removes a scene from the chapter"""
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)
        scene_obj = await Scene.fuzzy_find(chapter_obj, scene)

        await scene_obj.delete()
        embed = naff.Embed(color=naff.MaterialColors.DEEP_ORANGE)
        embed.description = f"Removed scene '**{scene_obj.name}**' from chapter '**{chapter_obj.name}**'"
        await ctx.send(embed=embed)

    @chapter_remove_scene.autocomplete("chapter")
    async def chapter_remove_scene_autocomplete1(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_autocomplete(ctx, chapter)

    @chapter_remove_scene.autocomplete("scene")
    async def chapter_remove_scene_autocomplete2(self, ctx: AutocompleteContext, chapter: str, scene: str, **_):
        return await self.scene_autocomplete(ctx, chapter, scene)

    @classmethod
    async def chapter_autocomplete(cls, ctx: AutocompleteContext, query: str):
        chapter_list = await Chapter.all().sort("+number").to_list()
        chapters = [chapter.name for chapter in chapter_list]
        results = fuzzy_autocomplete(query, chapters)
        # todo by number
        # todo remember last
        await ctx.send(results)

    @classmethod
    async def scene_autocomplete(cls, ctx: AutocompleteContext, chapter: str, query: str):
        chapter_obj = await Chapter.fuzzy_find(chapter)
        scene_list = await Scene.find({"chapter.$id": chapter_obj.id}).sort("+number").to_list()
        scenes = [scene.name for scene in scene_list]
        results = fuzzy_autocomplete(query, scenes)
        await ctx.send(results)

    @staticmethod
    async def chapters_field(highlight=None):
        chapters = await Chapter.all().sort("+number").to_list()

        def format_entry(chapter):
            to_highlight = chapter == highlight
            style = "***" if to_highlight else "*"
            return f"{chapter.number}. {style}{chapter.name}{style}"

        field = naff.EmbedField(
            name=f"Chapters [{len(chapters)} total]",
            value="\n".join([format_entry(chapter) for chapter in chapters])
        )

        return field


def setup(bot):
    SceneCmd(bot)
