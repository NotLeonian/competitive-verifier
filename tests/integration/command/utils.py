import datetime as dt
import pathlib
from collections.abc import Iterable
from hashlib import md5


def md5_number(seed: bytes) -> int:
    return int(md5(seed, usedforsecurity=False).hexdigest(), 16)


def dummy_commit_time(files: Iterable[pathlib.Path]) -> dt.datetime:
    md5 = md5_number(b"".join(sorted(f.as_posix().encode() for f in files)))

    return dt.datetime.fromtimestamp(
        md5 % 300000000000 / 100,
        tz=dt.timezone(dt.timedelta(hours=md5 % 25 - 12)),
    )
