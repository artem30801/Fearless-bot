import naff
from naff import subcommand, slash_str_option, slash_user_option, slash_bool_option
from naff import InteractionContext, AutocompleteContext, Permissions

from utils.text import format_lines
from utils.fuzz import fuzzy_autocomplete
from utils.intractions import yes_no
from utils.exceptions import InvalidArgument, edit_origin_exception

from extensions.character_models import Actor, Character


class CharacterCmd(naff.Extension):
    @subcommand(base="manage", subcommand_group="character", name="create")
    async def character_create(
            self,
            ctx: InteractionContext,
            name: slash_str_option("character name", required=True),
    ):
        """Adds a new character (but you can also just use /character assign)"""
        await ctx.defer(ephemeral=True)
        character_obj = Character(name=name)
        await character_obj.insert()
        await ctx.send(f"Created character '**{character_obj.name}**'!")

    @subcommand(base="manage", subcommand_group="character", name="remove")
    async def character_remove(
            self,
            ctx: InteractionContext,
            character: slash_str_option("character to remove", required=True, autocomplete=True),
    ):
        """Removes a character"""
        await ctx.defer(ephemeral=True)
        character_obj = await Character.fuzzy_find(character)
        await character_obj.delete()
        await ctx.send(f"Removed character '**{character_obj.name}**'!")

    @character_remove.autocomplete("character")
    async def character_remove_autocomplete(self, ctx: AutocompleteContext, character: str, **_):
        return await self.character_autocomplete(ctx, character)

    @subcommand(base="manage", subcommand_group="character", name="rename")
    async def character_rename(
            self,
            ctx: InteractionContext,
            character: slash_str_option("character to rename", required=True, autocomplete=True),
            new_name: slash_str_option("new name for the character", required=True),
    ):
        """Renames a character"""
        await ctx.defer(ephemeral=True)
        character_obj = await Character.fuzzy_find(character)
        old_name = character_obj.name
        character_obj.name = new_name
        await character_obj.save()
        await ctx.send(f"Renamed character '**{old_name}**' to '**{character_obj.name}**'!")

    @character_rename.autocomplete("character")
    async def character_rename_autocomplete(self, ctx: AutocompleteContext, character: str, **_):
        return await self.character_autocomplete(ctx, character)

    @subcommand(base="manage", subcommand_group="character", name="assign")
    async def character_assign(
            self,
            ctx: InteractionContext,
            character: slash_str_option("character to assign actor to", required=True, autocomplete=True),
            member: slash_user_option("actor to assign to the character", required=True),
    ):
        """Assign an actor to the character"""
        await ctx.defer(ephemeral=True)
        try:
            character_obj = await Character.fuzzy_find(character)
        except InvalidArgument:
            result, btn_ctx = await yes_no(
                ctx,
                f"This character does not exist yet. "
                f"Do you wish to create character '**{character}**'?",
            )
            if result:
                actor = await Actor.get_or_insert(member)
                character_obj = Character(name=character, actor=actor)
                character_obj = await character_obj.insert()
                await btn_ctx.edit_origin("Done!", components=[])
                await ctx.channel.send(
                    f"Created character '**{character_obj.name}**' and assigned to {member.mention}! 🎉",
                    allowed_mentions=naff.AllowedMentions.none(),
                )
            else:
                await btn_ctx.edit_origin(f"Ok, aborted :(", components=[])
        else:
            await character_obj.fetch_all_links()
            if character_obj.actor is not None:
                if character_obj.actor.user_id == member.id:
                    raise InvalidArgument(f"Character '**{character_obj.name}**' already has {member.mention} as an actor!")

                old_member_mention = await character_obj.actor.mention(ctx)

                result, btn_ctx = await yes_no(
                    ctx,
                    f"Character '**{character_obj.name}**' already has an actor: {old_member_mention}.\n"
                    f"Do you wish to replace the actor with {member.mention}?",
                    allowed_mentions=naff.AllowedMentions.none(),
                )

                if result:
                    msg = f"Replaced {old_member_mention} with {member.mention} as an actor for character '**{character}**'"
                else:
                    await btn_ctx.edit_origin(f"Ok, aborted ;(", components=[])
                    return
            else:
                msg = f"Assigned character '**{character_obj.name}**' to {member.mention}! 🎉"

            actor = await Actor.get_or_insert(member)
            character_obj.actor = actor
            await character_obj.save()

            await ctx.send("Done!")
            await ctx.channel.send(msg, allowed_mentions=naff.AllowedMentions.none())

    @character_assign.autocomplete("character")
    async def character_assign_autocomplete(self, ctx: AutocompleteContext, character: str, **_):
        return await self.character_autocomplete(ctx, character)

    @subcommand(base="manage", subcommand_group="character", name="free")
    async def character_free(
            self,
            ctx: InteractionContext,
            character: slash_str_option("character to free from the actor", required=True, autocomplete=True),
    ):
        """Clear the role from the assigned actor"""
        await ctx.defer(ephemeral=True)
        character_obj = await Character.fuzzy_find(character)
        await character_obj.fetch_all_links()
        if character_obj.actor is None:
            raise InvalidArgument(f"Character '**{character}**' is already free and without an actor :(")

        old_member_mention = character_obj.actor.mention(ctx)
        character_obj.actor = None
        await character_obj.save()
        await ctx.send(f"Removed {old_member_mention} as an actor for the character {character}",
                       allowed_mentions=naff.AllowedMentions.none(),
                       )

    @character_free.autocomplete("character")
    async def character_free_autocomplete(self, ctx: AutocompleteContext, character: str, **_):
        return await self.character_autocomplete(ctx, character)

    @subcommand(base="list", name="characters")
    async def character_list(
            self,
            ctx: InteractionContext,
            member: slash_user_option("actor to list characters for", required=False) = None,
            free_characters: slash_bool_option("whether to show only free characters or assigned",
                                               required=False) = None,
    ):
        """Clear the role from the assigned actor"""
        await ctx.defer()
        query = dict()
        embed = naff.Embed(title="Character list", description="")
        show_actors = True

        if free_characters is not None:
            if member:
                raise InvalidArgument("You should not specify `member` and `free_characters` options at the same time!")

            if free_characters:
                query["actor"] = None
                embed.description += "Showing only **free** characters"
                show_actors = False
            else:
                query["actor"] = {"$ne": None}
                embed.description += "Showing only **assigned** characters"

        if member:
            actor = await Actor.get_by_member(member)
            if actor:
                query["actor.$id"] = actor.id
                embed.description += f"For actor: {member.mention}"
                show_actors = False
            else:
                raise InvalidArgument("Sorry, this member is not assigned as an actor yet!")

        characters = await Character.find(query).to_list()
        for character in characters:
            await character.fetch_all_links()

        async def get_actor(character):
            if character.actor is None:
                return " [**FREE**]"
            else:
                return await character.actor.mention(ctx)

        print(characters)
        if show_actors:
            # name: actor
            characters_dict = {character.name: await get_actor(character) for character in characters}
            characters_text = format_lines(characters_dict)
        else:
            # only name
            characters_text = "\n".join([character.name for character in characters])

        embed.add_field(
            "Characters", characters_text or "No characters available!"
        )

        await ctx.send(
            embed=embed,
            allowed_mentions=naff.AllowedMentions.none(),
        )

    async def character_autocomplete(self, ctx: AutocompleteContext, query: str):
        character_list = await Character.find_many().to_list()
        characters = [character.name for character in character_list]
        results = fuzzy_autocomplete(query, characters)
        await ctx.send(results)


def setup(bot):
    CharacterCmd(bot)
