import random
from collections.abc import Iterable

MODIFIERS = (
    "Amber", "Ash", "Birch", "Brass", "Bronze", "Cedar", "Chalk", "Clay", "Cobalt",
    "Copper", "Coral", "Cotton", "Dusk", "Ember", "Flint", "Frost", "Gilded", "Glass",
    "Granite", "Hazel", "Honey", "Indigo", "Ivory", "Jade", "Juniper", "Lacquer",
    "Linen", "Maple", "Marble", "Mist", "Moss", "Nickel", "Oak", "Ochre", "Opal",
    "Paper", "Pewter", "Pine", "Quartz", "Rain", "Rust", "Saffron", "Salt", "Silk",
    "Slate", "Smoke", "Teal", "Thistle", "Tin", "Umber", "Vellum", "Velvet", "Wax",
    "Willow", "Wool", "Yarrow", "Zinc",
)  # fmt: skip

NOUNS = (
    "Anchor", "Anvil", "Arch", "Atlas", "Attic", "Bell", "Bridge", "Bucket", "Cellar",
    "Chimney", "Compass", "Dial", "Dock", "Easel", "Ferry", "Fountain", "Garden",
    "Gate", "Harbour", "Hearth", "Hinge", "Inkwell", "Island", "Jar", "Jetty",
    "Kettle", "Kite", "Ladder", "Lantern", "Lighthouse", "Locket", "Loom", "Market",
    "Meadow", "Mill", "Mirror", "Needle", "Observatory", "Orchard", "Pier", "Quarry",
    "Raft", "Ribbon", "Satchel", "Sextant", "Signal", "Spindle", "Staircase",
    "Teapot", "Telescope", "Thimble", "Tower", "Tram", "Umbrella", "Vane", "Wagon",
    "Well", "Whistle", "Windmill", "Yard", "Zeppelin",
)  # fmt: skip


def _key(name: str) -> str:
    return "_".join(name.lower().replace("-", " ").replace("_", " ").split())


def generate_name(taken: Iterable[str] = ()) -> str:
    """Generates a two-word project codename, e.g. 'Copper Lantern'.

    Names in `taken` (project names or folder names) are avoided where possible.
    """
    taken_keys = {_key(t) for t in taken}
    for _ in range(100):
        name = f"{random.choice(MODIFIERS)} {random.choice(NOUNS)}"
        if _key(name) not in taken_keys:
            break
    return name
