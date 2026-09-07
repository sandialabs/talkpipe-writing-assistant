"""Writing Assistant - AI-powered document generation tool."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

try:
    __version__ = _dist_version("talkpipe-writing-assistant")
except PackageNotFoundError:  # a checkout that was never installed
    __version__ = "0.0.0+unknown"
__author__ = "Travis Bauer"
__email__ = "tlbauer@sandia.gov"

from .core.definitions import Metadata

__all__ = ["Metadata"]
