"""Compiled packages are validated, fingerprinted data, never generated code."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from pydantic import Field

from inkbound.realm.models import Model, RealmSpec
from inkbound.realm.validation import require_valid


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(spec: RealmSpec) -> str:
    return hashlib.sha256(canonical(spec.model_dump(mode="json"))).hexdigest()


class Manifest(Model):
    realm_package_version: int = Field(default=1, ge=1, le=1)
    realm_spec_version: int = Field(default=1, ge=1, le=1)
    realm_id: str
    revision: int = Field(ge=1)
    spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assets: dict[str, str] = Field(default_factory=dict)


def safe_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("Path escapes package")
    return path


class RealmPackage:
    def __init__(self, spec: RealmSpec, root: Path | None = None):
        # Nested dict/list edits bypass Pydantic's assignment validation. Reparse
        # even an existing model before accepting it as an immutable snapshot.
        self._spec = require_valid(RealmSpec.model_validate(spec.model_dump(mode="python")))
        self._root = root
        self._raw = canonical(self._spec.model_dump(mode="json"))
        self._digest = hashlib.sha256(self._raw).hexdigest()

    @property
    def spec(self) -> RealmSpec:
        """A working copy; callers cannot mutate a published package's identity."""
        return self._spec.model_copy(deep=True)

    @property
    def root(self):
        return self._root

    @property
    def digest(self):
        return self._digest

    @classmethod
    def load(cls, path: str | Path) -> "RealmPackage":
        root = Path(path).resolve()
        raw = (root / "realm.json").read_bytes()
        spec = RealmSpec.model_validate_json(raw)
        manifest = Manifest.model_validate_json((root / "manifest.json").read_bytes())
        if manifest.spec_sha256 != hashlib.sha256(raw).hexdigest() or manifest.realm_id != spec.metadata.id or manifest.revision != spec.metadata.revision:
            raise ValueError("Package manifest does not match RealmSpec")
        expected = {a.path: a.sha256 for a in spec.assets if a.path}
        if manifest.assets != expected:
            raise ValueError("Asset manifest does not match RealmSpec")
        for relative, digest in manifest.assets.items():
            f = safe_file(root, relative)
            if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Missing or corrupted asset: {relative}")
        package = cls(spec, root)
        # Preserve the exact original contract bytes, including omitted optional
        # fields from older v1 packages. New model defaults must not change save
        # identity or invalidate their manifest.
        package._raw = raw
        package._digest = manifest.spec_sha256
        return package

    def write(self, destination: str | Path, asset_source: str | Path | None = None) -> Path:
        destination = Path(destination).resolve()
        if destination.exists():
            raise FileExistsError("Use a new package directory; published realms are immutable")
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
        try:
            assets: dict[str, str] = {}
            for asset in self._spec.assets:
                if asset.path:
                    if asset_source is None:
                        raise ValueError(f"Asset source required for {asset.id}")
                    source = safe_file(Path(asset_source), asset.path)
                    raw = source.read_bytes()
                    if hashlib.sha256(raw).hexdigest() != asset.sha256:
                        raise ValueError(f"Asset checksum mismatch: {asset.id}")
                    target = safe_file(stage, asset.path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                    assets[asset.path] = asset.sha256
            (stage / "realm.json").write_bytes(self._raw)
            manifest = Manifest(realm_id=self._spec.metadata.id, revision=self._spec.metadata.revision,
                                spec_sha256=self.digest, assets=assets)
            (stage / "manifest.json").write_bytes(canonical(manifest.model_dump()))
            # Validate exactly the bytes about to become playable.
            RealmPackage.load(stage)
            os.rename(stage, destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        return destination
