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
    to_highlight = instance == highlight
    style = "***" if to_highlight else "*"
    return f"{instance.number}. {style}{instance.name}{style}"


def pluralize(number: int, measure: str) -> str:
    return f"{number} {measure}{'' if number == 1 else 's'}"

# print(make_table([["hello", "world"], ["hey", "yoi"]], [True, False]))