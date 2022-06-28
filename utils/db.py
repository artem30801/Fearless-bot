import re

from beanie.odm.queries.find import FindMany
from beanie import Document as BeanieDocument


class Document(BeanieDocument):
    def __hash__(self):
        return hash(self.id)

    class Settings:
        # beanie config
        validate_on_save = True

    class Config:
        # pydantic config
        validate_assignment = True
        validate_all = True


async def ensure_number_ordering(query: FindMany, number: int):
    if await query.find({"number": number}).exists():
        await query.find({"number": {"$gte": number}}).inc({"number": 1})


def validate_name(value: str):
    value = re.sub(r"\s{2,}", ' ', value)
    value = value.strip()
    value = value.title()

    return value
