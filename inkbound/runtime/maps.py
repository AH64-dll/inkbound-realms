"""Wrap original Inkbound terrain/interior algorithms with stable topology."""
from __future__ import annotations

import hashlib
import random
from collections import deque

from pydantic import Field

from inkbound.realm.models import Model, RealmSpec
from legacy.ascii_rpg.src.dungeon import gen_interior, gen_town
from legacy.ascii_rpg.src.worldgen import _gen_terrain


def stable_seed(*parts: object) -> int:
    return int.from_bytes(hashlib.sha256("\0".join(map(str, parts)).encode()).digest()[:8], "big")


class MapData(Model):
    id: str
    grid: list[str]
    entrance: list[int]
    exit: list[int] | None = None
    points: dict[str, list[int]] = Field(default_factory=dict)
    floor: int = 0
    origin: list[int] = Field(default_factory=lambda: [0, 0])
    terrain_seed: int = 0
    thresholds: list[float] = Field(default_factory=list)

    def walkable(self, x: int, y: int) -> bool:
        return 0 <= y < len(self.grid) and 0 <= x < len(self.grid[0]) and self.grid[y][x] not in "#^~HIS"

    def reachable(self, start: list[int] | None = None) -> set[tuple[int, int]]:
        first = tuple(start or self.entrance)
        if not self.walkable(*first):
            return set()
        seen = {first}
        queue = deque([first])
        while queue:
            x, y = queue.popleft()
            for p in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                if p not in seen and self.walkable(*p):
                    seen.add(p)
                    queue.append(p)
        return seen


def connect(grid: list[list[str]], start: tuple[int, int], end: tuple[int, int], glyph: str = "=") -> None:
    x, y = start
    tx, ty = end
    while (x, y) != (tx, ty):
        if x != tx:
            x += 1 if tx > x else -1
        else:
            y += 1 if ty > y else -1
        grid[y][x] = glyph


def build_maps(spec: RealmSpec) -> dict[str, MapData]:
    maps: dict[str, MapData] = {}
    for region in spec.regions:
        seed = stable_seed(spec.metadata.seed, region.id)
        rng = random.Random(seed)
        thresholds = []
        if region.generator == "station":
            grid = [["#" if x in (0, region.width - 1) or y in (0, region.height - 1) else "."
                     for x in range(region.width)] for y in range(region.height)]
            for x in range(6, region.width - 2, 9):
                for y in range(2, region.height - 2):
                    if y % 7 != 0:
                        grid[y][x] = "#"
        else:
            grid, _, thresholds = _gen_terrain(rng, region.width, region.height, seed % 1000000)
            if region.generator == "nautical":
                # Navigable water is a distinct tile; islands become obstacles.
                grid = [["," if c == "~" else "." if c in ",rs=" else "T" for c in row] for row in grid]
        locations = sorted((loc for loc in spec.locations if loc.region_id == region.id), key=lambda loc: loc.id)
        points = {loc.id: [loc.x, loc.y] for loc in locations}
        if any(not (0 < x < region.width - 1 and 0 < y < region.height - 1) for x, y in points.values()):
            raise ValueError(f"Location outside {region.id}")
        anchors = [(loc.x, loc.y) for loc in locations]
        if not anchors:
            anchors = [(region.width // 2, region.height // 2)]
        grid[anchors[0][1]][anchors[0][0]] = "."
        # Guarantee a traversable world spine; decorative terrain cannot trap an objective.
        for a, b in zip(anchors, anchors[1:]):
            connect(grid, a, b)
        for loc in locations:
            grid[loc.y][loc.x] = {"settlement": "O", "dungeon": "D", "ruin": "R", "shrine": "*",
                                  "camp": "X", "farm": "v", "tower": "!"}[loc.kind]
        maps[region.id] = MapData(id=region.id, grid=["".join(row) for row in grid], entrance=list(anchors[0]), points=points,
                                 terrain_seed=seed % 1000000, thresholds=thresholds)
        for loc in locations:
            if loc.kind == "settlement":
                data = gen_town(stable_seed(seed, loc.id), "hamlet")
                town_grid = [list(row) for row in data["grid"]]
                entrance = list(data["gates"][-1]); entrance[1] -= 1
                # Original interiors have decorative houses/shops; service NPCs are interactive.
                maps[loc.id] = MapData(id=loc.id, grid=["".join(row) for row in town_grid], entrance=entrance,
                                      exit=list(data["gates"][-1]))
            elif loc.kind in ("dungeon", "ruin"):
                for floor in range(loc.depth):
                    key = loc.id if floor == 0 else f"{loc.id}:{floor}"
                    data = gen_interior(stable_seed(seed, loc.id), loc.id, loc.kind, floor, loc.depth, theme=loc.theme)
                    grid2 = [list(row) for row in data["grid"]]
                    # Ruin rubble can obstruct a room; clear a critical route to the boss.
                    connect(grid2, tuple(data["stairs"]), tuple(data["boss_room"]), ".")
                    grid2[data["stairs"][1]][data["stairs"][0]] = "<"
                    if data["stairs_down"]:
                        x, y = data["stairs_down"]; grid2[y][x] = ">"
                    points2 = {c["id"]: [c["x"], c["y"]] for c in data["chests"]}
                    points2["boss"] = list(data["boss_room"])
                    maps[key] = MapData(id=key, grid=["".join(row) for row in grid2], entrance=list(data["stairs"]),
                                        exit=list(data["stairs_down"]) if data["stairs_down"] else None,
                                        points=points2, floor=floor)
    return maps
