import naff
from naff import SlashCommand, Permissions

manage = SlashCommand(name="manage", dm_permission=False, default_member_permissions=Permissions.ADMINISTRATOR)


async def generic_rename(ctx: naff.InteractionContext, obj, obj_name: str, new_name: str):
    old_name = obj.name
    obj.name = new_name
    await obj.save()

    embed = naff.Embed()
    if old_name == obj.name:
        embed.color = naff.MaterialColors.PURPLE
        embed.description = f"Name of the {obj_name} '**{obj.name}**' did not change"
    else:
        embed.color = naff.MaterialColors.INDIGO
        embed.description = f"Renamed {obj_name} '**{old_name}**' to '**{obj.name}**'"
    return embed
