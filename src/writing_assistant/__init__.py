"""Writing Assistant - AI-powered document generation tool."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

# The distribution name on PyPI; also how a running server identifies itself.
DIST_NAME = "talkpipe-writing-assistant"

try:
    __version__ = _dist_version(DIST_NAME)
except PackageNotFoundError:  # a checkout that was never installed
    __version__ = "0.0.0+unknown"
from .core.definitions import Metadata  # noqa: E402 - needs the metadata above

__author__ = "Travis Bauer"
__email__ = "tlbauer@sandia.gov"

__all__ = ["DIST_NAME", "Metadata", "__version__"]
