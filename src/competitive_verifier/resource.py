import sys
from logging import getLogger

logger = getLogger(__name__)

if sys.platform in ["win32", "darwin"]:  # pragma: no cover
    resource = None
else:  # pragma: no cover
    import resource


def ulimit_stack() -> None:
    """Run `ulimit -s unlimited`."""
    if resource is not None:  # pragma: no cover
        _, hard = resource.getrlimit(resource.RLIMIT_STACK)
        resource.setrlimit(resource.RLIMIT_STACK, (hard, hard))


def try_ulimit_stack() -> None:  # pragma: no cover
    """Run `ulimit -s unlimited` and ignore any errors."""
    try:
        ulimit_stack()
    except (OSError, ValueError):
        logger.warning("failed to increase the stack size[ulimit]")
