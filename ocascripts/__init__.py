from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version('ocascripts')  # distribution name from pyproject
except PackageNotFoundError:
    # Running from a source checkout without install
    __version__ = 'unknown-not-installed'
