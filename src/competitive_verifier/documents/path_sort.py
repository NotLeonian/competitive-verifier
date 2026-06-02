import enum
import pathlib
from typing import TYPE_CHECKING, TypeAlias, cast

from natsort import natsort_keygen, ns

if TYPE_CHECKING:
    from collections.abc import Callable


class PathSortOrder(str, enum.Enum):
    lexicographic = "lexicographic"
    natural = "natural"


_NaturalPrimaryKey: TypeAlias = tuple[object, ...]
_NaturalSortKey: TypeAlias = tuple[_NaturalPrimaryKey, str]
_LexicographicSortKey: TypeAlias = tuple[str]
_PathSortKey: TypeAlias = _NaturalSortKey | _LexicographicSortKey

_NATURAL_PATH_SORT_KEY = cast(
    "Callable[[pathlib.PurePath], _NaturalPrimaryKey]",
    natsort_keygen(alg=ns.INT | ns.IGNORECASE | ns.PATH),
)


def normalize_path_sort_order(order: PathSortOrder | None) -> PathSortOrder:
    return order or PathSortOrder.lexicographic


def is_natural_path_sort(order: PathSortOrder | None) -> bool:
    return normalize_path_sort_order(order) == PathSortOrder.natural


def path_sort_key_path(
    path: pathlib.PurePath,
    order: PathSortOrder | None,
) -> _PathSortKey:
    value = path.as_posix()
    if not is_natural_path_sort(order):
        return (value.casefold(),)

    return (_NATURAL_PATH_SORT_KEY(path), value)
