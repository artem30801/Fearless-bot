def format_lines(d: dict, delimiter="|"):
    max_len = max(map(len, d.keys()))
    lines = [f"`{name:<{max_len}}` {delimiter} {value}" for name, value in d.items()]
    return "\n".join(lines)
