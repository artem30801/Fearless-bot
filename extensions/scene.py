from typing import TYPE_CHECKING
import naff
from naff import slash_str_option, slash_int_option
from naff import InteractionContext, AutocompleteContext, Permissions
from naff.client.utils import TTLCache
from bson import ObjectId

from utils.fuzz import fuzzy_autocomplete
from utils.intractions import yes_no
from utils.exceptions import InvalidArgument
from utils.text import make_table, format_entry, pluralize
from utils.commands import manage_cmd, list_cmd, info_cmd, generic_rename, generic_move, generic_autocomplete

from extensions.character_models import Character, Scene, Chapter

if TYPE_CHECKING:
    from extensions.character import CharacterCmd
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

    def get_last_scene(self, ctx: naff.Context) -> ObjectId | None:
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
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter, only_with_scenes=True)

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
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter, only_with_scenes=True)

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
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter, only_with_scenes=True)

    @scene_move.autocomplete("scene")
    async def move_scene_autocomplete_scene(self, ctx: AutocompleteContext, chapter: str, scene: str, **_):
        return await self.scene_autocomplete(ctx, chapter, scene)

    @scene_cmd.subcommand("add_character")
    async def scene_add_character(
            self,
            ctx: InteractionContext,
            chapter: slash_str_option("chapter of the scene to add character to", required=True, autocomplete=True),
            scene: slash_str_option("scene to add character to", required=True, autocomplete=True),
            character: slash_str_option("character to add to the scene", required=True, autocomplete=True),
    ):
        """Adds a character to the scene"""
        # noinspection DuplicatedCode
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)
        scene_obj = await Scene.fuzzy_find(chapter_obj, scene)
        character_obj = await Character.fuzzy_find(character)
        self.set_last_scene(ctx, chapter_obj, scene_obj)

        embed = naff.Embed()
        id_exists = [True for instance in scene_obj.characters if character_obj.id == instance.ref.id]
        if id_exists:
            embed.color = naff.MaterialColors.PURPLE
            embed.description = f"Character '**{character_obj.name}**' is already in the scene '**{scene_obj.name}**' " \
                                f"of chapter '**{chapter_obj.name}**'"
        else:
            embed.color = naff.MaterialColors.INDIGO
            scene_obj.characters.append(Character.link_from_id(character_obj.id))
            await scene_obj.save()
            embed.description = f"Added character '**{character_obj.name}**' to the scene '**{scene_obj.name}**' " \
                                f"of chapter '**{chapter_obj.name}**'"
        embed.fields.append(await self.scene_characters_field(ctx, chapter_obj, scene_obj))
        await ctx.send(embed=embed)

    @scene_add_character.autocomplete("chapter")
    async def add_character_autocomplete_chapter(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter, only_with_scenes=True)

    @scene_add_character.autocomplete("scene")
    async def add_character_autocomplete_scene(self, ctx: AutocompleteContext, chapter: str, scene: str, **_):
        return await self.scene_autocomplete(ctx, chapter, scene)

    @scene_add_character.autocomplete("character")
    async def add_character_autocomplete_character(self, ctx: AutocompleteContext,
                                                   chapter: str, scene: str, character: str, **_):
        chapter_obj = await Chapter.fuzzy_find(chapter)
        scene_obj = await Scene.fuzzy_find(chapter_obj, scene)
        return await self.character_ext.character_autocomplete(ctx, character, exclude_scene=scene_obj)

    @scene_cmd.subcommand("remove_character")
    async def scene_remove_character(
            self,
            ctx: InteractionContext,
            chapter: slash_str_option("chapter of the scene to remove character from", required=True,
                                      autocomplete=True),
            scene: slash_str_option("scene to remove character from", required=True, autocomplete=True),
            character: slash_str_option("character to remove from the scene", required=True, autocomplete=True),
    ):
        """Removes a character from the scene"""
        # noinspection DuplicatedCode
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)
        scene_obj = await Scene.fuzzy_find(chapter_obj, scene)
        character_obj = await Character.fuzzy_find(character)
        self.set_last_scene(ctx, chapter_obj, scene_obj)

        embed = naff.Embed()
        new_characters = [instance for instance in scene_obj.characters if character_obj.id != instance.ref.id]
        if new_characters == scene_obj.characters:
            embed.color = naff.MaterialColors.PURPLE
            embed.description = f"Character '**{character_obj.name}**' is *not* in the scene '**{scene_obj.name}**' " \
                                f"of chapter '**{chapter_obj.name}**'"
        else:
            embed.color = naff.MaterialColors.INDIGO
            scene_obj.characters = new_characters
            await scene_obj.save()
            embed.description = f"Removed character '**{character_obj.name}**' from the scene '**{scene_obj.name}**' " \
                                f"of chapter '**{chapter_obj.name}**'"
        embed.fields.append(await self.scene_characters_field(ctx, chapter_obj, scene_obj))
        await ctx.send(embed=embed)

    @scene_remove_character.autocomplete("chapter")
    async def remove_character_autocomplete_chapter(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter, only_with_scenes=True)

    @scene_remove_character.autocomplete("scene")
    async def remove_character_autocomplete_scene(self, ctx: AutocompleteContext, chapter: str, scene: str, **_):
        return await self.scene_autocomplete(ctx, chapter, scene, only_wth_characters=True)

    @scene_remove_character.autocomplete("character")
    async def remove_character_autocomplete_character(self, ctx: AutocompleteContext,
                                                      chapter: str, scene: str, character: str, **_):
        chapter_obj = await Chapter.fuzzy_find(chapter)
        scene_obj = await Scene.fuzzy_find(chapter_obj, scene)
        return await self.character_ext.character_autocomplete(ctx, character, only_scene=scene_obj)

    @list_cmd.subcommand("scenes")
    async def scene_list(self, ctx: InteractionContext,
                         chapter: slash_str_option("chapter to list scenes in", required=True, autocomplete=True),
                         ):
        """List all scenes in specified chapter"""
        await ctx.defer(ephemeral=True)
        chapter_obj = await Chapter.fuzzy_find(chapter)

        embed = naff.Embed(color=naff.MaterialColors.LIGHT_BLUE)
        embed.title = f"Scenes list"
        embed.fields.append(await self.scenes_field(chapter_obj))
        await ctx.send(embed=embed)

    @scene_list.autocomplete("chapter")
    async def scene_list_autocomplete_chapter(self, ctx: AutocompleteContext, chapter: str, **_):
        return await self.chapter_ext.chapter_autocomplete(ctx, chapter, only_with_scenes=True)

    @property
    def character_ext(self) -> "CharacterCmd":
        return self.bot.get_ext("CharacterCmd")  # type: ignore

    @property
    def chapter_ext(self) -> "ChapterCmd":
        return self.bot.get_ext("ChapterCmd")  # type: ignore

    async def scene_autocomplete(self, ctx: AutocompleteContext, chapter: str, query: str,
                                 only_wth_characters: bool = False):
        chapter_obj = await Chapter.fuzzy_find(chapter)
        if chapter_obj.id != self.chapter_ext.get_last_chapter(ctx):
            self.clear_last_scene(ctx)

        db_query = Scene.in_chapter(chapter_obj.id).sort("+number")
        if only_wth_characters:
            db_query = db_query.find({"characters": {"$exists": True, "$not": {"$size": 0}}})

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

    async def scene_characters_field(self, ctx, chapter: Chapter, scene: Scene):
        description, characters_text, characters = await self.character_ext.make_character_list(
            ctx=ctx,
            chapter=chapter,
            scene=scene,
        )
        field = naff.EmbedField(
            name=f"Characters in '{scene.name}' scene [{len(characters)} total]:",
            value=characters_text or "No characters available!"
        )

        return field

    @naff.slash_command("roles")
    async def roles(self, ctx: InteractionContext):
        components = [naff.Button(label="Voicing", style=naff.ButtonStyles.BLUE),
                      naff.Button(label="Organization", style=naff.ButtonStyles.BLUE),
                      naff.Button(label="Editing", style=naff.ButtonStyles.BLUE),
                      ]
        await ctx.send("Please apply for your role in audio play:", components=components)


def setup(bot):
    SceneCmd(bot)
