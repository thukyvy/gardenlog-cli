"""Allow running GardenLog with `python -m gardenlog`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
