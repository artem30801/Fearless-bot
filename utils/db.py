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


async def get_new_number(instance, query):
    number = instance.number if instance.number is not None else float('inf')
    number = max(number, 1)
    max_number = await deepcopy(query).find({"_id": {"$ne": instance.id}}).max("number") or 0
    number = min(number, max_number + 1)
    return number


async def reshuffle_numbers(query, current_instance=None, to_delete=False):
    instances: list = await query.sort("+number").to_list()
    return_number = None
    if current_instance is not None:
        # We remove current instance from the list and add it back on the *proper* position
        new_instances = [instance for instance in instances if instance.id != current_instance.id]
        if instances != new_instances:  # Don't add instance back if it wasn't in the list
            instances = new_instances
            current_number = current_instance.number-1 if current_instance.number is not None else len(instances)
            instances.insert(current_number, current_instance)

    for number, instance in enumerate(instances, 1):
        instance.number = number
        await instance.save(skip_actions=["validate_db", "reshuffle"])

        if current_instance is not None and instance.id == current_instance.id:
            return_number = number

    return return_number


def validate_name(value: str):
    value = re.sub(r"\s{2,}", ' ', value)
    value = value.strip()
    value = value.title()

    return value
