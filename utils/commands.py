import naff
from copy import deepcopy
from naff import SlashCommand, Permissions

from utils.fuzz import fuzzy_autocomplete

manage_cmd = SlashCommand(name="manage", dm_permission=False, default_member_permissions=Permissions.ADMINISTRATOR)
info_cmd = SlashCommand(name="info")
list_cmd = SlashCommand(name="list")


async def generic_rename(instance, class_name: str, new_name: str):
    old_name = instance.name
    instance.name = new_name
    await instance.save()

    embed = naff.Embed()
    if old_name == instance.name:
        embed.color = naff.MaterialColors.PURPLE
        embed.description = f"Name of the {class_name} '**{instance.name}**' did not change"
    else:
        embed.color = naff.MaterialColors.INDIGO
        embed.description = f"Renamed {class_name} '**{old_name}**' to '**{instance.name}**'"
    return embed


async def generic_move(instance, class_name: str, new_number: int):
    old_number = instance.number
    instance.number = new_number
    await instance.save()

    embed = naff.Embed()
    if old_number == instance.number:
        embed.color = naff.MaterialColors.PURPLE
        embed.description = f"Position of the {class_name} '**{instance.name}**' did not change (**#{instance.number}**)"
    else:
        embed.color = naff.MaterialColors.INDIGO
        embed.description = f"Moved {class_name} '**{instance.name}**' from position **#{old_number}** to **#{instance.number}**"
    return embed


async def generic_autocomplete(query, db_query, last_id=None, use_numbers=False):
    query = query.strip()

    results = []
    if use_numbers:
        try:
            number = int(query)
        except ValueError:
            pass
        else:
            last_instance = await deepcopy(db_query).find({"number": number}).first_or_none()
            if last_instance is None:
                query = ""
            else:
                results = [last_instance]

    if not results:
        instance_list = await deepcopy(db_query).to_list()
        if query:
            instance_dict = {instance: instance.name for instance in instance_list}
            results = fuzzy_autocomplete(query, instance_dict)
            results = [instance for _, _, instance in results]
        else:
            results = instance_list

    if not query and last_id is not None:
        # If exists, we move last used instance to the top of the list
        last_instance = await deepcopy(db_query).find({"_id": last_id}).first_or_none()
        if last_instance is not None:
            results = [result for result in results if result.id != last_instance.id]
            results.insert(0, last_instance)
    return results
