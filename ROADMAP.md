# GardenLog Roadmap

Where GardenLog is heading after v0.1.0. These are real planned features,
roughly in the order they are likely to land — not promises with dates.

## Next

- **Fertiliser schedule** — track feeding separately from watering, with its
  own interval per plant and entries in `due`.

## Later

- **Weather-aware reminders** — optionally skip or delay a due watering when
  rain is forecast for outdoor plants (requires an opt-in weather source;
  GardenLog stays offline by default).
- **Zones** — group plants by location (balcony, kitchen, greenhouse) and
  filter `list` / `due` by zone.
- **Care profiles** — reusable presets ("succulent", "fern", "herb") that set
  sensible default intervals when adding a plant.

## Principles

- Standard library only, single JSON data file, no account, no network.
- Every feature lands with tests first or alongside.
