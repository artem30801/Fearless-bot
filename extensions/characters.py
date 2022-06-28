import asyncio

import naff
from naff import subcommand, slash_str_option, slash_user_option, slash_bool_option
from naff import InteractionContext, AutocompleteContext, Permissions

import beanie
from pydantic import Field

from utils.db import Document
from utils.fuzz import fuzzy_find_obj, fuzzy_autocomplete
from utils.intractions import yes_no
from utils.text import format_lines


class Actor(Document):
    user_id: beanie.Indexed(int)
    user_tag: str

    @classmethod
    async def get_or_insert(cls, member: naff.Member):
        actor = await cls.find_one({'user_id': member.id})
        if actor is None:
            actor = cls(user_id=member.id, user_tag=member.tag)
            actor = await actor.insert()
        return actor

    @classmethod
    async def get_by_member(cls, member: naff.Member):
        return await cls.find_one({'user_id': member.id})

    # def member(self, guild: naff.Guild):
    #     return guild.get_member(self.user_id)

    async def user(self, ctx: InteractionContext) -> naff.User:
        user = None
        if ctx.guild:
            user = await ctx.bot.fetch_member(self.user_id, ctx.guild)

        if user is None:  # obj not found or not in guild
            user = await ctx.bot.bot.fetch_user(self.user_id)
        else:
            user = user.user  # obj is found, convert member to user

        return user

    async def mention(self, ctx: InteractionContext) -> str:
        if user := await self.user(ctx):
            return user.mention
        else:
            return self.user_tag


class Character(Document):
    name: beanie.Indexed(str)
    actor: beanie.Link[Actor] | None = Field(None)

    @classmethod
    async def fuzzy_find(cls, query) -> "Character":
        return await fuzzy_find_obj(query, cls)


class Scene(Document):
    name: str
    number: int
    characters: list[beanie.Link[Character]]


class Chapter(Document):
    name: str
    number: int
    scenes = list[beanie.Link[Scene]]


class CharactersTrack(naff.Extension):
    @subcommand(base="manage", subcommand_group="character", name="create")
    async def character_create(
            self,
            ctx: InteractionContext,
            name: slash_str_option("character name", required=True),
    ):
        """Adds a new character (but you can also just use /character assign)"""
        await ctx.defer(ephemeral=True)
        try:
            await Character.fuzzy_find(name)
        except ValueError:
            pass
        else:
            await ctx.send(f"Sorry, character '**{name}**' already exists")
            return

        character_obj = Character(name=name)
        await character_obj.insert()
        await ctx.send(f"Created character '**{character_obj.name}**'!")

    @subcommand(base="manage", subcommand_group="character", name="remove")
    async def character_remove(
            self,
            ctx: InteractionContext,
            character: slash_str_option("character to assign actor to", required=True, autocomplete=True),
    ):
        """Removes a character"""
        await ctx.defer(ephemeral=True)
        try:
            character_obj = await Character.fuzzy_find(character)
        except ValueError:
            await ctx.send(f"Character '**{character}**' not found! I can't remove what's not there ;)")
        else:
            await character_obj.delete()
            await ctx.send(f"Removed character '**{character_obj.name}**'!")

    @character_remove.autocomplete("character")
    async def character_remove_autocomplete(self, ctx: AutocompleteContext, character: str, **_):
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
        except ValueError:
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
                    await ctx.send(
                        f"Character '**{character}**' already has {member.mention} as an actor!",
                        allowed_mentions=naff.AllowedMentions.none(),
                    )
                    return

                old_member_mention = await character_obj.actor.mention(ctx)

                result, btn_ctx = await yes_no(
                    ctx,
                    f"Character '**{character}**' already has an actor: {old_member_mention}.\n"
                    f"Do you wish to replace the actor with {member.mention}?",
                    allowed_mentions=naff.AllowedMentions.none(),
                )

                if result:
                    actor = await Actor.get_or_insert(member)
                    character_obj.actor = actor
                    await character_obj.save()

                    await btn_ctx.edit_origin("Done!", components=[])
                    await ctx.channel.send(
                        f"Replaced {old_member_mention} with {member.mention} as an actor for character '**{character}**'",
                        allowed_mentions=naff.AllowedMentions.none(),
                    )
                else:
                    await btn_ctx.edit_origin(f"Ok, aborted ;(", components=[])
            else:
                actor = await Actor.get_or_insert(member)
                character_obj.actor = actor
                await character_obj.save()

                await ctx.send("Done!")
                await ctx.channel.send(
                    f"Assigned character '**{character_obj.name}**' to {member.mention}! 🎉",
                    allowed_mentions=naff.AllowedMentions.none(),
                )

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
        try:
            character_obj = await Character.fuzzy_find(character)
        except ValueError:
            await ctx.send(f"Sorry, but character '**{character}**' does not exist!")
        else:
            await character_obj.fetch_all_links()
            if character_obj.actor is None:
                await ctx.send(f"Character '**{character}**' is already free and without an actor :(")
                return

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
            free_characters: slash_bool_option("whether to show only free characters or assigned", required=False) = None,
    ):
        """Clear the role from the assigned actor"""
        await ctx.defer()
        query = dict()
        embed = naff.Embed(title="Character list", description="")
        show_actors = True

        if free_characters is not None:
            if member:
                await ctx.send("You should not specify `member` and `free_characters` options at the same time!", ephemeral=True)
                return

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
                await ctx.send("Sorry, this member is not assigned as an actor yet!", ephemeral=True)
                return

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
    CharactersTrack(bot)
    bot.add_model(Actor)
    bot.add_model(Character)
    bot.add_model(Scene)
