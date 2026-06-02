import enum
import pathlib
from typing import TYPE_CHECKING, Any, TypeAlias, cast

from natsort import natsort_keygen, ns

if TYPE_CHECKING:
    from collections.abc import Callable


class PathSortOrder(str, enum.Enum):
    lexicographic = "lexicographic"
    natural = "natural"


_NatsortPrimaryKey: TypeAlias = tuple[Any, ...]
_SortKey: TypeAlias = tuple[_NatsortPrimaryKey, str]

_NATURAL_SORT_KEY = cast(
    "Callable[[str], _NatsortPrimaryKey]",
    natsort_keygen(alg=ns.INT | ns.IGNORECASE),
)


def normalize_path_sort_order(order: PathSortOrder | None) -> PathSortOrder:
    return order or PathSortOrder.lexicographic


def path_sort_key_text(value: str, order: PathSortOrder | None) -> _SortKey:
    order = normalize_path_sort_order(order)

    if order == PathSortOrder.lexicographic:
        return ((value.casefold(),), value)

    return (_NATURAL_SORT_KEY(value), value)


def path_sort_key_path(
    path: pathlib.PurePath,
    order: PathSortOrder | None,
) -> _SortKey:
    return path_sort_key_text(path.as_posix(), order)
