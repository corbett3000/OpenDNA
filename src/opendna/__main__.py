"""Allow `python -m opendna` and `opendna` entry-point script."""
import sys

from opendna.cli import main

if __name__ == "__main__":
    sys.exit(main())
