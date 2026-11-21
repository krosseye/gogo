import math


def format_bytes(size_bytes: int) -> str:
    """Human-readable size, e.g. '1.24 MiB'."""
    if size_bytes <= 0:
        return "0 B"

    units = ("B", "KiB", "MiB", "GiB", "TiB")
    i = min(math.floor(math.log(size_bytes, 1024)), len(units) - 1)

    if i == 0:
        return f"{size_bytes} B"
    value = size_bytes / math.pow(1024, i)
    return f"{value:.2f} {units[i]}"


def plural(count: int, noun: str) -> str:
    """e.g. '1 file', '3 files'."""
    return f"{count} {noun}{'' if count == 1 else 's'}"
