import naff


async def yes_no(ctx: naff.InteractionContext, content: str, **kwargs):
    no = naff.Button(style=naff.ButtonStyles.RED, label="No")
    yes = naff.Button(style=naff.ButtonStyles.GREEN, label="Yes")
    components = [no, yes]
    await ctx.send(
        content,
        components=components,
        **kwargs
    )
    btn_ctx = await ctx.bot.wait_for_component(components=components, timeout=15 * 60)
    btn_ctx = btn_ctx.context

    await btn_ctx.defer(edit_origin=True)
    answer = btn_ctx.custom_id == yes.custom_id
    return answer, btn_ctx
