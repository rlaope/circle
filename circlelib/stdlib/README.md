# circlelib standard library

Reusable, fixed-shape components shipped with the package. Import them
from any user `.crl` with the `@stdlib/` prefix:

```crl
import "@stdlib/furniture/chair" as ch
import "@stdlib/vehicles/car"    as v
import "@stdlib/geometry/axes"   as ax

scene {
    ax.Axes(position=(0, 0, 0))
    ch.Chair(position=(0, 0, 2))
    v.Car(position=(6, 0, 0), rotation=(0, 30, 0))
}
```

## Catalog

| Path                              | Components       |
|-----------------------------------|------------------|
| `@stdlib/furniture/chair`         | `Chair`, `Stool` |
| `@stdlib/furniture/table`         | `Table`, `Desk`  |
| `@stdlib/furniture/lamp`          | `Lamp`           |
| `@stdlib/vehicles/wheels`         | `Pair`, `Quad`   |
| `@stdlib/vehicles/car`            | `Car`, `Truck`   |
| `@stdlib/structures/tower`        | `Tower`          |
| `@stdlib/structures/column`       | `Column`         |
| `@stdlib/structures/arch`         | `Arch`           |
| `@stdlib/geometry/axes`           | `Axes`           |
| `@stdlib/geometry/crosshair`      | `Crosshair`      |

## Conventions

- Components are **fixed-shape**. The only "parameter" is the call's
  `position` / `rotation`, which become the parent transform for every
  body statement.
- Each component is built so its base sits at `y = 0` (with a few
  obvious exceptions like `Axes`, which is centred on the origin).
- Colors lean neutral so callers can drop a stdlib piece into a scene
  without it dominating the palette.

## Resolver behaviour

`@stdlib/<sub>` resolves to `circlelib/stdlib/<sub>.crl` shipped inside
the installed package. Imports without the prefix continue to be
resolved relative to the importing file. The two systems do not
interact.
