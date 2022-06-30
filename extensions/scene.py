import naff
from naff import slash_str_option, slash_int_option
from naff import InteractionContext, AutocompleteContext, Permissions

from utils.fuzz import fuzzy_autocomplete
from utils.intractions import yes_no
from utils.exceptions import InvalidArgument
from utils.text import make_table, format_entry, pluralize
from utils.commands import manage_cmd, generic_rename

from extensions.character_models import Character, Scene, Chapter
from extensions.chapter import ChapterCmd

scene_cmd = manage_cmd.group("scene")


class SceneCmd(naff.Extension):
    @scene_cmd.subcommand("add")
    async def add_scene(
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
        embed.description = f"Added scene '**{scene_obj.name}**' to the chapter '**{chapter_obj.name}**'"
        embed.fields.append(await self.scenes_field(chapter_obj, highlight=scene_obj))
        await ctx.send(embed=embed)

    @add_scene.autocomplete("chapter")
    async def add_scene_autocomplete(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter)

    @scene_cmd.subcommand("remove")
    async def remove_scene(
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
        embed.description = f"Removed scene '**{scene_obj.name}**' from the chapter '**{chapter_obj.name}**'"
        embed.fields.append(await self.scenes_field(chapter_obj, highlight=scene_obj))
        await ctx.send(embed=embed)

    @remove_scene.autocomplete("chapter")
    async def remove_scene_autocomplete_chapter(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter, only_wth_scenes=True)

    @remove_scene.autocomplete("scene")
    async def remove_scene_autocomplete_scene(self, ctx: AutocompleteContext, chapter: str, scene: str, **_):
        return await self.scene_autocomplete(ctx, chapter, scene)

    @scene_cmd.subcommand("rename")
    async def scene_rename(
            self,
            ctx: InteractionContext,
            chapter: slash_str_option("chapter to rename scene in", required=True, autocomplete=True),
            scene: slash_str_option("scene to rename", required=True, autocomplete=True),
            new_name: slash_str_option("new name for the scene", required=True),
    ):
        """Renames a scene"""
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)
        scene_obj = await Scene.fuzzy_find(chapter_obj, scene)

        embed = await generic_rename(scene_obj, "scene", new_name)
        await ctx.send(embed=embed)

    @scene_rename.autocomplete("chapter")
    async def rename_scene_autocomplete_chapter(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter)

    @scene_rename.autocomplete("scene")
    async def rename_scene_autocomplete_scene(self, ctx: AutocompleteContext, chapter: str, scene: str, **_):
        return await self.scene_autocomplete(ctx, chapter, scene)

    @property
    def chapter_ext(self) -> "ChapterCmd":
        return self.bot.get_ext("ChapterCmd")  # type: ignore

    @classmethod
    async def scene_autocomplete(cls, ctx: AutocompleteContext, chapter: str, query: str):
        chapter_obj = await Chapter.fuzzy_find(chapter)
        scene_list = await Scene.in_chapter(chapter_obj.id).sort("+number").to_list()
        scenes = [scene.name for scene in scene_list]
        results = fuzzy_autocomplete(query, scenes)
        await ctx.send(results)

    @classmethod
    async def scenes_field(cls, chapter, highlight=None):
        scenes = await Scene.in_chapter(chapter.id).sort("+number").to_list()

        field = naff.EmbedField(
            name=f"Scenes in '{chapter.name}' [{len(scenes)} total]",
            value="\n".join([format_entry(scene, highlight) for scene in scenes])
        )

        return field


def setup(bot):
    SceneCmd(bot)
