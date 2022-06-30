import naff
from naff import slash_str_option, slash_int_option
from naff import InteractionContext, AutocompleteContext, Permissions
from naff.client.utils import TTLCache

from utils.fuzz import fuzzy_autocomplete
from utils.intractions import yes_no
from utils.exceptions import InvalidArgument
from utils.text import make_table, format_entry, pluralize
from utils.commands import manage_cmd, generic_rename, generic_move, generic_autocomplete

from extensions.character_models import Character, Scene, Chapter
from extensions.chapter import ChapterCmd

scene_cmd = manage_cmd.group("scene")


class SceneCmd(naff.Extension):
    def __init__(self, client):
        self.last_scene = TTLCache(ttl=60 * 60, soft_limit=100, hard_limit=250)

    def set_last_scene(self, ctx: naff.Context, chapter_obj: Chapter, scene_obj: Scene):
        self.chapter_ext.set_last_chapter(ctx, chapter_obj)
        self.last_scene[ctx.author.id] = scene_obj.id

    def clear_last_scene(self, ctx: naff.Context):
        self.last_scene.pop(ctx.author.id, None)

    def get_last_scene(self, ctx: naff.Context):
        return self.last_scene.get(ctx.author.id, None)

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
        self.set_last_scene(ctx, chapter_obj, scene_obj)

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
        self.clear_last_scene(ctx)

        embed = naff.Embed(color=naff.MaterialColors.DEEP_ORANGE)
        embed.description = f"Removed scene '**{scene_obj.name}**' from the chapter '**{chapter_obj.name}**'"
        embed.fields.append(await self.scenes_field(chapter_obj))
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
        self.set_last_scene(ctx, chapter_obj, scene_obj)

        embed = await generic_rename(scene_obj, "scene", new_name)
        embed.fields.append(await self.scenes_field(chapter_obj, highlight=scene_obj))
        await ctx.send(embed=embed)

    @scene_rename.autocomplete("chapter")
    async def rename_scene_autocomplete_chapter(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter, only_wth_scenes=True)

    @scene_rename.autocomplete("scene")
    async def rename_scene_autocomplete_scene(self, ctx: AutocompleteContext, chapter: str, scene: str, **_):
        return await self.scene_autocomplete(ctx, chapter, scene)

    @scene_cmd.subcommand("move")
    async def scene_move(
            self,
            ctx: InteractionContext,
            chapter: slash_str_option("chapter to move scene in", required=True, autocomplete=True),
            scene: slash_str_option("scene to move", required=True, autocomplete=True),
            new_position: slash_int_option("new number for the scene inside the chapter", required=True, min_value=1),
    ):
        """Changes a position (number) of the scene in a chapter"""
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)
        scene_obj = await Scene.fuzzy_find(chapter_obj, scene)
        self.set_last_scene(ctx, chapter_obj, scene_obj)

        embed = await generic_move(scene_obj, "scene", new_position)
        embed.fields.append(await self.scenes_field(chapter_obj, highlight=scene_obj))
        await ctx.send(embed=embed)

    @scene_move.autocomplete("chapter")
    async def move_scene_autocomplete_chapter(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter, only_wth_scenes=True)

    @scene_move.autocomplete("scene")
    async def move_scene_autocomplete_scene(self, ctx: AutocompleteContext, chapter: str, scene: str, **_):
        return await self.scene_autocomplete(ctx, chapter, scene)

    @property
    def chapter_ext(self) -> "ChapterCmd":
        return self.bot.get_ext("ChapterCmd")  # type: ignore

    async def scene_autocomplete(self, ctx: AutocompleteContext, chapter: str, query: str, only_wth_characters: bool = False):
        chapter_obj = await Chapter.fuzzy_find(chapter)
        if chapter_obj.id != self.chapter_ext.get_last_chapter(ctx):
            self.clear_last_scene(ctx)

        db_query = Scene.in_chapter(chapter_obj.id).sort("+number")
        # if only_wth_characters:
        #     characters = await Character.all().to_list()
        #     chapter_ids = {character.chapter.ref.id for character in characters}
        #     db_query = db_query.find({"_id": {"$in": list(chapter_ids)}})

        last_scene_id = self.get_last_scene(ctx)

        results = await generic_autocomplete(query, db_query, last_scene_id, use_numbers=True)
        results = [{"name": f"{scene.number}. {scene.name}", "value": scene.name} for scene in results]
        await ctx.send(results)

    @classmethod
    async def scenes_field(cls, chapter, highlight=None):
        scenes = await Scene.in_chapter(chapter.id).sort("+number").to_list()

        field = naff.EmbedField(
            name=f"Scenes in '{chapter.name}' chapter [{len(scenes)} total]:",
            value="\n".join([format_entry(scene, highlight) for scene in scenes])
        )

        return field


def setup(bot):
    SceneCmd(bot)
