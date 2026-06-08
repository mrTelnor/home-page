"""URL-friendly slug generator with cyrillic transliteration."""
from __future__ import annotations

import re

_CYR2LAT = str.maketrans({
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i",
    "й":"i","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t",
    "у":"u","ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y",
    "ь":"","э":"e","ю":"iu","я":"ia",
})


def slugify(text: str) -> str:
    """`"Электронный дневник"` → `"elektronnyi-dnevnik"`. Лексикографически детерминирован."""
    s = text.lower().translate(_CYR2LAT)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")
