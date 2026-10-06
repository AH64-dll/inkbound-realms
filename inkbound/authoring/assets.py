"""Interchangeable optional asset providers with an unconditional playable fallback."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Callable, Protocol

from inkbound.realm.models import Asset, RealmSpec
from inkbound.realm.package import safe_file
from inkbound.realm.validation import require_valid


class AssetProvider(Protocol):
    def generate(self, request: Asset, destination: Path) -> Path: ...


class ExistingAssets:
    def __init__(self, library: dict[str, str | Path]):
        self.library = {key: Path(value) for key, value in library.items()}

    def generate(self, request, destination):
        source = self.library[request.id]
        target = destination / (request.id + source.suffix)
        shutil.copyfile(source, target)
        return target


class ProceduralAssets:
    def generate(self, request, destination):
        if request.kind not in ("sprite", "portrait", "tile", "icon", "background", "glyph"):
            raise ValueError("Procedural raster provider does not support this asset kind")
        import pygame
        pygame.font.init()
        size = 96 if request.kind == "portrait" else 32
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        color = pygame.Color(request.fallback.color)
        pygame.draw.circle(surface, color, (size // 2, size // 2), size // 3)
        font = pygame.font.SysFont("DejaVu Sans Mono,monospace", size // 2)
        glyph = font.render(request.fallback.glyph, True, (15, 18, 26))
        surface.blit(glyph, glyph.get_rect(center=(size // 2, size // 2)))
        target = destination / (request.id + ".png")
        pygame.image.save(surface, str(target))
        return target


class CallableAssets:
    """Local or remote plugins are registered by application code, never AI code."""
    def __init__(self, callback: Callable[[Asset, Path], Path]):
        self.callback = callback

    def generate(self, request, destination):
        return self.callback(request, destination)


def build_assets(spec: RealmSpec, root: str | Path, providers: dict[str, AssetProvider]) -> tuple[RealmSpec, list[str]]:
    root = Path(root).resolve(); destination = root / "assets"; destination.mkdir(parents=True, exist_ok=True)
    data = spec.model_dump(mode="json"); report = []
    for asset, output in zip(spec.assets, data["assets"]):
        if asset.provider == "fallback":
            continue
        provider = providers.get(asset.provider)
        try:
            if provider is None:
                raise ValueError("Provider unavailable")
            path = provider.generate(asset, destination).resolve()
            if not path.is_relative_to(destination) or not path.is_file():
                raise ValueError("Asset provider returned a path outside its output directory")
            output["path"] = str(path.relative_to(root))
            output["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            report.append(f"{asset.id}: generated with {asset.provider}")
        except (OSError, ValueError, KeyError, RuntimeError):
            output.update(provider="fallback", path=None, sha256=None)
            report.append(f"{asset.id}: using its playable glyph/audio fallback")
    return require_valid(RealmSpec.model_validate(data)), report
