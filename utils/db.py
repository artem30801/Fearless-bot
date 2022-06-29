import re
from copy import deepcopy

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


async def get_new_number(query, number=None):
    number = number if number is not None else float('inf')
    number = max(number, 1)
    max_number = await deepcopy(query).max("number") or 0
    number = min(number, max_number + 1)
    return number


async def ensure_number_ordering(query: FindMany, number: int):
    if await deepcopy(query).find({"number": number}).exists():
        await deepcopy(query).find({"number": {"$gte": number}}).inc({"number": 1})


async def reshuffle_numbers(query, number, exclude_instance=None):
    query = deepcopy(query).find({"number": {"$gte": number}})
    if exclude_instance is not None:
        query = deepcopy(query).find({"_id": {"$ne": exclude_instance.id}})

    query = query.sort("+number")

    async for instance in query:
        print(instance)
        instance.number = number
        await instance.save()
        number += 1
        print(instance)


def validate_name(value: str):
    value = re.sub(r"\s{2,}", ' ', value)
    value = value.strip()
    value = value.title()

    return value
