"""Asset registry with a content-hashed on-disk cache.

Sprites are *generated*, not committed: each asset id maps to a Python generator
built out of :class:`mario.engine.ink.Canvas` shapes.  Generators run once per
build and their output is cached as PNG next to a manifest entry keyed by the
hash of the generator source, so editing art invalidates the cache by itself.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import wave
import io
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np
import pygame
from PIL import Image

from . import ink
from .res import RES_SCALE
from .audio import to_wav

DEFAULT_CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "art_cache")


@dataclass
class Asset:
    """A loaded asset: one surface, or a list of frames for animations."""

    id: str
    frames: list[pygame.Surface] = field(default_factory=list)

    @property
    def surface(self) -> pygame.Surface:
        return self.frames[0]

    def frame(self, i: float) -> pygame.Surface:
        if len(self.frames) == 1:
            return self.frames[0]
        return self.frames[int(i) % len(self.frames)]

    def strip(self) -> pygame.Surface:
        """All frames packed in a row (used to save/reload from the cache)."""
        if len(self.frames) == 1:
            return self.frames[0]
        return ink.strip(self.frames)

    @property
    def size(self):
        """Size of a single frame (frames are stored unpacked; strip() packs them)."""
        return self.frames[0].get_size()


class UnknownAsset(KeyError):
    pass


_REGISTRY: dict[str, tuple[Callable, dict, str]] = {}
_FP_MEMO: dict[tuple, str] = {}       # 指纹备忘录：会话内模块源码不变，重算纯浪费
_SIG_MEMO: dict[str, frozenset] = {}  # 生成器形参集合，同样按 id 缓存
_IDS: frozenset | None = None        # registered_ids 的缓存（注册时失效）


def asset(id: str, **kwargs):
    """Register a sprite generator under ``id``.

    The wrapped function is called with no arguments and returns a :class:`Canvas`
    (or a list of them for animation frames), or raw bytes for audio/json assets.
    """
    def deco(fn: Callable):
        register(id, fn, **kwargs)
        return fn

    return deco


def register(id: str, fn: Callable, **kwargs):
    global _IDS
    _REGISTRY[id] = (fn, kwargs, fn.__module__ + ":" + fn.__qualname__)
    _IDS = None
    # 同名热替换后旧指纹/签名缓存必须失效（测试里会覆盖注册）
    _FP_MEMO.clear()
    _SIG_MEMO.pop(id, None)


def registered() -> list[str]:
    return sorted(_REGISTRY)


def registered_ids() -> frozenset:
    """O(1) 成员测试用（registered() 每次都 sorted，热路径 draw 里很贵）。"""
    global _IDS
    if _IDS is None:
        _IDS = frozenset(_REGISTRY)
    return _IDS


def _fingerprint(id: str, opts: dict) -> str:
    """Hash the generator's source *and* the options it will run with: edit the art or
    recolour a block and the cached file stops matching, so it is simply rebuilt.

    结果按 (id, opts) 备忘录化——inspect.getsource 要重新 tokenize 整个美术模块，
    而热路径（每帧几十次 sprite 查询）查的永远是同一批键。
    """
    key = (id, repr(sorted(opts.items())))
    fp = _FP_MEMO.get(key)
    if fp is not None:
        return fp
    fn, _kwargs, _ = _REGISTRY[id]
    try:
        src = inspect.getsource(inspect.getmodule(fn)) + inspect.getsource(fn)
    except OSError:  # pragma: no cover
        src = ""
    h = hashlib.sha256(src.encode())
    h.update(key[1].encode())
    fp = h.hexdigest()[:16]
    _FP_MEMO[key] = fp
    return fp


class Assets:
    """Lazy loader + LRU-ish cache in front of the PNG/WAV cache dir."""

    def __init__(self, cache_dir: str = DEFAULT_CACHE, enable_cache: bool = True):
        import mario.art  # noqa: F401  importing registers every sprite/audio generator
        self.cache_dir = cache_dir
        self.enable_cache = enable_cache
        self._mem: dict[str, Asset] = {}
        self._manifest_path = os.path.join(cache_dir, "manifest.json")
        self._manifest: dict[str, str] = {}
        if enable_cache and os.path.exists(self._manifest_path):
            try:
                with open(self._manifest_path) as fh:
                    self._manifest = json.load(fh)
            except (OSError, ValueError):
                # 缓存是纯派生数据，损坏时回退为空并重建，不能让游戏起不来
                self._manifest = {}
        self.built = 0  # generators actually run this session (tests assert cache hits)

    # -- public api ------------------------------------------------------------------
    def sprite(self, id: str, **over) -> Asset:
        """Load an asset by id, generating it (once) if the cache is cold.

        ``over`` overrides the registered generator kwargs, which is how one terrain
        generator serves five palettes without a decorator per environment.

        优先查真实素材图集（mario/assets/atlas.json）：命中直接裁剪，
        未命中回落到程序化生成器——两条路径共用同一套 id。
        """
        from ..assets import atlas as _atlas
        try:
            frames = _atlas.atlas_asset(id, RES_SCALE)
        except (OSError, ValueError, pygame.error):
            frames = None
        if frames is not None and not over:
            key = f"atlas:{id}@{RES_SCALE}"
            if key not in self._mem:
                self._mem[key] = Asset(id, frames)
            return self._mem[key]
        if id not in _REGISTRY:
            raise UnknownAsset(id)
        fn, kwargs, _ = _REGISTRY[id]
        kind = kwargs.get("kind", "sprite")
        ext = {"sprite": "png", "wav": "wav"}[kind]
        finish = kwargs.get("finish", {})
        meta = {"frames": int(kwargs.get("frames", 1)), "finish": finish}
        accepted = _SIG_MEMO.get(id)
        if accepted is None:
            _SIG_MEMO[id] = accepted = frozenset(inspect.signature(fn).parameters)
        opts = {k: v for k, v in kwargs.items() if k in accepted}
        opts.update({k: v for k, v in over.items() if k in accepted})
        opts.update({"_frames": meta["frames"], "_finish": meta["finish"],
                     "_res": RES_SCALE})
        fp = _fingerprint(id, opts)
        if f"{id}@{fp}" in self._mem:
            return self._mem[f"{id}@{fp}"]
        stem = id.replace("/", "_").replace(".", "_")
        path = os.path.join(self.cache_dir, f"{stem}@{fp}.{ext}")
        loaded = None
        if self.enable_cache and self._manifest.get(os.path.basename(path)) == fp and os.path.exists(path):
            loaded = self._read_cached(id, path, kind, meta)
        if loaded is None:
            self.built += 1
            os.makedirs(self.cache_dir, exist_ok=True)
            loaded = self._build(id, fn, {k: v for k, v in opts.items()
                                         if not k.startswith("_")}, kind, meta)
            if self.enable_cache:
                self._write_cached(path, kind, loaded)
                self._manifest[os.path.basename(path)] = fp
        self._mem[f"{id}@{fp}"] = loaded
        return loaded

    def flush(self):
        if not self.enable_cache:
            return
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self._manifest_path, "w") as fh:
            json.dump(self._manifest, fh, indent=1, sort_keys=True)

    def load_all(self):
        for id in _REGISTRY:
            self.sprite(id)

    # -- internals -------------------------------------------------------------------
    def _build(self, id, fn, opts, kind, meta) -> Asset:
        n = meta["frames"]
        if kind == "sprite" and n > 1 and "frame" in inspect.signature(fn).parameters:
            result = [fn(**opts, frame=i) for i in range(n)]   # per-frame generator
        else:
            result = fn(**opts)
        if kind == "sprite":
            frames = result if isinstance(result, (list, tuple)) else [result]
            fin = {**meta["finish"], "out_scale": RES_SCALE}
            surfaces = [f.finish(**fin) if isinstance(f, ink.Canvas) else f
                        for f in frames]
            return Asset(id, surfaces)
        if isinstance(result, np.ndarray):        # note tables arrive as samples
            result = to_wav(result)
        return Asset(id, [result])

    def _read_cached(self, id, path, kind, meta):
        try:
            if kind == "sprite":
                with Image.open(path) as im:
                    surf = pygame.image.frombuffer(im.convert("RGBA").tobytes(), im.size, "RGBA")
                n = meta["frames"]
                fw = surf.get_width() // n
                frames = [surf.subsurface(pygame.Rect(i * fw, 0, fw, surf.get_height()))
                          for i in range(n)]
                return Asset(id, frames)
            with open(path, "rb") as fh:
                return Asset(id, [fh.read()])
        except (OSError, ValueError):
            return None

    def _write_cached(self, path, kind, asset: Asset):
        if kind == "sprite":
            im = Image.frombytes("RGBA", asset.strip().get_size(),
                                pygame.image.tobytes(asset.strip(), "RGBA"))
            im.save(path)
        else:
            with open(path, "wb") as fh:
                fh.write(asset.frames[0])
