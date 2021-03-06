import enum
import naff
import beanie
from naff import InteractionContext
from pydantic import Field, validator

from utils.db import Document, validate_name, reshuffle_numbers
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

    async def member(self, guild: naff.Guild) -> naff.Member | None:
        return await guild.fetch_member(self.user_id)

    async def user(self, ctx: InteractionContext) -> naff.User:
        user = None
        if ctx.guild:
            user = await ctx.bot.fetch_member(self.user_id, ctx.guild)

        if user is None:  # obj not found or not in guild
            user = await ctx.bot.fetch_user(self.user_id)
        else:
            user = user.user  # obj is found, convert member to user

        return user

    async def mention(self, ctx: InteractionContext) -> str:
        if user := await self.user(ctx):
            return user.mention
        else:
            return self.user_tag

    async def display_name(self, guild: naff.Guild) -> str:
        if user := await self.member(guild):
            return user.display_name
        else:
            return self.user_tag


class CharacterGrade(enum.IntEnum):
    main = 1
    secondary = 2
    tertiary = 3


class Character(Document):
    name: beanie.Indexed(str)
    grade: CharacterGrade = Field(default=CharacterGrade.secondary)

    actor: beanie.Link[Actor] | None = Field(None)

    validate_name = validator("name", allow_reuse=True)(validate_name)

    @beanie.before_event(beanie.ValidateOnSave)
    async def validate_db(self):
        # validate name
        cls = self.__class__
        if await cls.find(cls.name == self.name, cls.id != self.id).exists():
            raise InvalidArgument(f"Character '**{self.name}**' already exists!")

    @classmethod
    async def fuzzy_find(cls, query: str) -> "Character":
        try:
            return await fuzzy_find_obj(query, cls.all())
        except ValueError:
            raise InvalidArgument(f"Character with name'**{query}**' not found!")


class Chapter(Document):
    name: str
    number: int = Field(default=None, ge=1)
    # scenes = list[beanie.Link[Scene]]

    validate_name = validator("name", allow_reuse=True)(validate_name)

    @beanie.before_event(beanie.ValidateOnSave)
    async def validate_db(self):
        # validate name
        cls = self.__class__
        if await cls.find(cls.name == self.name, cls.id != self.id).exists():
            raise InvalidArgument(f"Chapter '**{self.name}**' already exists!")

    @beanie.after_event([beanie.Insert, beanie.Replace, beanie.Delete])
    async def reshuffle(self):
        self.number = await reshuffle_numbers(self.__class__.all(), current_instance=self)

    @classmethod
    async def fuzzy_find(cls, query: str) -> "Chapter":
        try:
            return await fuzzy_find_obj(query, cls.all())
        except ValueError:
            raise InvalidArgument(f"Chapter with name'**{query}**' not found!")

    @property
    def scenes(self):
        return Scene.find({"chapter.$id": self.id}).sort("+number")

    @property
    def fullname(self):
        return f"{self.number}. {self.name}"


class Scene(Document):
    name: str
    number: int = Field(default=None, ge=1)

    chapter: beanie.Link[Chapter]
    characters: list[beanie.Link[Character]] = Field(default_factory=list)

    validate_name = validator("name", allow_reuse=True)(validate_name)

    @property
    def chapter_id(self):
        return self.chapter.ref.id if isinstance(self.chapter, beanie.Link) else self.chapter.id

    @beanie.before_event(beanie.ValidateOnSave)
    async def validate_db(self):
        # validate name
        cls = self.__class__
        if await cls.find(cls.name == self.name, cls.id != self.id).exists():
            raise InvalidArgument(f"Scene '**{self.name}**' already exists!")

    @beanie.after_event([beanie.Insert, beanie.Replace, beanie.Delete])
    async def reshuffle(self):
        self.number = await reshuffle_numbers(self.in_chapter(self.chapter_id), current_instance=self)

    @classmethod
    def in_chapter(cls, chapter_id):
        return cls.find({"chapter.$id": chapter_id})

    @classmethod
    async def fuzzy_find(cls, chapter: "Chapter", query: str) -> "Scene":
        try:
            return await fuzzy_find_obj(query, cls.in_chapter(chapter.id))
        except ValueError:
            raise InvalidArgument(f"Chapter with name'**{query}**' not found!")

    @property
    def fullname(self):
        return f"{self.number}. {self.name}"


def setup(bot):
    bot.add_model(Actor)
    bot.add_model(Character)
    bot.add_model(Scene)
    bot.add_model(Chapter)
