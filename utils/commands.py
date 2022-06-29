import naff
from naff import SlashCommand, Permissions

manage = SlashCommand(name="manage", dm_permission=False, default_member_permissions=Permissions.ADMINISTRATOR)