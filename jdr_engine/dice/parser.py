# jdr_engine/dice/parser.py
# Parse une notation de dés D&D (XdY+Z) sans dépendance Discord.
import re

from jdr_engine.dice.models import DiceError, MAX_DICE, MAX_FACES

# Accepte : "3d6+2", "1d20", "2d8-1", "d20", "d6+3", "4d6"
_DICE_RE = re.compile(
    r"^"
    r"(?:(?P<count>\d*)d(?P<faces>\d+))?"
    r"(?:(?P<sign>[+-])(?P<mod>\d+))?"
    r"$"
)


def parse(dice_str: str) -> tuple[int, int, int, str]:
    """
    Parse une chaîne de notation de dés D&D.

    Retourne (count, faces, modifier, sign).

    Lance DiceError si le format est invalide ou si les limites sont dépassées.
    """
    dice_str = dice_str.strip().lower()

    if not dice_str:
        raise DiceError(
            "Notation de dé vide. Utilise par ex. : 3d6+2, d20, 2d8-1"
        )

    m = _DICE_RE.match(dice_str)
    if not m or (
        not m.group("count") and not m.group("faces") and not m.group("mod")
    ):
        raise DiceError(
            f'Notation invalide : "{dice_str}".\n'
            "Formats attendus : XdY+Z, dY+Z, XdY-Z, dY-Z, dY\n"
            "Exemples : 3d6+2, 1d20, 2d8-1, d20, d6, 4d6"
        )

    count_str = m.group("count")
    count = int(count_str) if count_str else 1

    faces_str = m.group("faces")
    faces = int(faces_str) if faces_str else None

    sign = m.group("sign") or "+"
    mod = int(m.group("mod") or "0")

    if faces is None:
        faces = 20

    if count > MAX_DICE:
        raise DiceError(
            f"Trop de dés : maximum {MAX_DICE} dés par lancer (reçu : {count})."
        )
    if faces > MAX_FACES:
        raise DiceError(
            f"Trop de faces : maximum {MAX_FACES} faces (reçu : d{faces})."
        )
    if faces < 1:
        raise DiceError(f"Nombre de faces invalide : d{faces}. Minimum : 1.")
    if count < 1:
        raise DiceError(f"Nombre de dés invalide : {count}. Minimum : 1.")

    modifier = mod if sign == "+" else -mod
    return count, faces, modifier, sign
