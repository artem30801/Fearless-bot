import naff
import beanie
from naff import InteractionContext
from pydantic import Field, validator

from utils.db import Document, validate_name
from utils.fuzz import fuzzy_find_obj
from utils.exceptions import InvalidArgument


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

    validate_name = validator("name", allow_reuse=True)(validate_name)

    @beanie.before_event(beanie.ValidateOnSave)
    async def validate_db(self):
        # validate name
        cls = self.__class__
        if await cls.find(cls.name == self.name, cls.id != self.id).exists():
            raise InvalidArgument(f"Character '**{self.name}**' already exists!")

    @classmethod
    async def fuzzy_find(cls, query) -> "Character":
        try:
            return await fuzzy_find_obj(query, cls)
        except ValueError:
            raise InvalidArgument(f"Character with name'**{query}**' not found!")


class Scene(Document):
    name: str
    number: int
    characters: list[beanie.Link[Character]]

    validate_name = validator("name", allow_reuse=True)(validate_name)


class Chapter(Document):
    name: str
    number: int
    scenes = list[beanie.Link[Scene]]

    validate_name = validator("name", allow_reuse=True)(validate_name)


def setup(bot):
    bot.add_model(Actor)
    bot.add_model(Character)
    bot.add_model(Scene)
    bot.add_model(Chapter)
