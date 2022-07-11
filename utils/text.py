from dateutil.relativedelta import relativedelta

clock_emojis = {"⌚", "⏰", "⏱️", "⏲️", "🕰️"}


def format_lines(d: dict, delimiter="|"):
    max_len = max(map(len, d.keys()))
    lines = [f"`{name:<{max_len}}` {delimiter} {value}" for name, value in d.items()]
    return "\n".join(lines)


def _wr(wrap: bool):
    return '`' if wrap else ''


def _make_data_line(column_widths: list[int], wrap: list[bool], line: list[str], align: str) -> str:
    return '│'.join(f'{_wr(ap)} {str(value): {align}{width}} {_wr(ap)}' for width, ap, value in zip(column_widths, wrap, line))


def make_table(rows: list[list[str]], wrap: list[bool]) -> list[str]:
    columns = zip(*rows)
    column_widths = [max(len(str(value)) for value in column) for column in columns]
    lines = []
    for row in rows:
        lines.append(_make_data_line(column_widths, wrap, row, "<"))
    return lines


def format_entry(instance, highlight=None):
    if highlight is not None:
        to_highlight = instance.id == highlight.id
    else:
        to_highlight = False
    style = "***" if to_highlight else "*"
    return f"{instance.number}. {style}{instance.name}{style}"


def pluralize(number: int, measure: str) -> str:
    return f"{number: <2} {measure}{'' if number == 1 else 's'}"


def format_delta(delta: relativedelta, positive=False, display_values_amount: int = 3):
    d = {
        "year": delta.years,
        "month": delta.months,
        "day": delta.days,
        "hour": delta.hours,
        "minute": delta.minutes,
    }
    values = [f"{abs(value) if positive else value} {key + 's' if value != 1 else key}"
              for key, value in d.items() if value != 0]
    if display_values_amount:
        values = values[:display_values_amount]
    result = ", ".join(values)
    return result
