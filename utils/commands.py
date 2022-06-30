import naff
from naff import SlashCommand, Permissions

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
