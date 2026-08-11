#!/usr/bin/env python3
"""Find duplicate photos in a folder and quarantine the extras.

Two passes:
  1. Exact duplicates  - SHA-256 of the file bytes. Works on any format.
  2. Near duplicates   - 64-bit difference hash (dHash) on a decoded thumbnail,
                         grouped by Hamming distance. Catches re-saves, resizes,
                         burst frames and screenshot re-crops that are visually
                         the same but byte-different.

Nothing is deleted. Without --apply it only reports. With --apply the extras are
*moved* into a quarantine folder alongside an undo manifest, so every action is
reversible until you empty that folder yourself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

# Formats worth decoding for perceptual comparison. HEIC needs the optional
# pillow-heif plugin; without it HEIC files still get exact-duplicate matching.
DECODABLE = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".heic", ".heif"}
SCANNABLE = DECODABLE | {".mov", ".mp4", ".m4v", ".aae", ".dng", ".raw", ".cr2", ".nef"}

HASH_SIDE = 8  # dHash grid: 8x9 samples -> 64 bits


@dataclass
class Photo:
    path: Path
    size: int
    mtime: float
    sha256: str = ""
    dhash: int | None = None
    pixels: int = 0

    @property
    def label(self) -> str:
        # Byte-identical files are never decoded, so pixels is only known for
        # photos that went through the perceptual pass.
        dimensions = f"{self.pixels}px, " if self.pixels else ""
        return f"{self.path.name} ({dimensions}{self.size // 1024}KB)"


@dataclass
class Group:
    kind: str  # "exact" or "near"
    keeper: Photo
    extras: list[Photo] = field(default_factory=list)

    @property
    def reclaimable(self) -> int:
        return sum(p.size for p in self.extras)


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def dhash_of(path: Path) -> tuple[int, int] | None:
    """Return (64-bit perceptual hash, pixel count), or None if undecodable."""
    if Image is None:
        return None
    try:
        with Image.open(path) as img:
            pixels = img.width * img.height
            small = img.convert("L").resize((HASH_SIDE + 1, HASH_SIDE), Image.LANCZOS)
            data = list(small.tobytes())
    except Exception:
        return None

    bits = 0
    for row in range(HASH_SIDE):
        offset = row * (HASH_SIDE + 1)
        for col in range(HASH_SIDE):
            left = data[offset + col]
            right = data[offset + col + 1]
            bits = (bits << 1) | int(left > right)
    return bits, pixels


def collect(root: Path, include_all: bool) -> list[Photo]:
    found: list[Photo] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if not include_all and path.suffix.lower() not in SCANNABLE:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_size == 0:
            continue
        found.append(Photo(path=path, size=stat.st_size, mtime=stat.st_mtime))
    return found


def pick_keeper(candidates: list[Photo]) -> Photo:
    """Best copy wins: most pixels, then largest file, then oldest, then shortest
    name (a plain name beats 'IMG_0042 copy 2')."""
    return min(
        candidates,
        key=lambda p: (-p.pixels, -p.size, p.mtime, len(p.path.name), str(p.path)),
    )


def find_exact(photos: list[Photo]) -> list[Group]:
    # Only files that share a byte size can be identical, so hash within those
    # buckets and skip the rest entirely.
    by_size: dict[int, list[Photo]] = defaultdict(list)
    for photo in photos:
        by_size[photo.size].append(photo)

    groups: list[Group] = []
    for bucket in by_size.values():
        if len(bucket) < 2:
            continue
        by_digest: dict[str, list[Photo]] = defaultdict(list)
        for photo in bucket:
            if not photo.sha256:
                photo.sha256 = sha256_of(photo.path)
            by_digest[photo.sha256].append(photo)
        for matches in by_digest.values():
            if len(matches) < 2:
                continue
            keeper = pick_keeper(matches)
            groups.append(Group("exact", keeper, [p for p in matches if p is not keeper]))
    return groups


def find_near(photos: list[Photo], distance: int) -> list[Group]:
    """Union-find over perceptual hashes: any two photos within `distance` bits
    land in the same group, so a chain of near-identical burst frames collapses
    into one cluster."""
    hashed = [p for p in photos if p.dhash is not None]
    parent = list(range(len(hashed)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[rb] = ra

    # Exact-hash buckets are free; only pay for pairwise comparison when the
    # caller actually asked for fuzzy matching.
    if distance == 0:
        buckets: dict[int, list[int]] = defaultdict(list)
        for idx, photo in enumerate(hashed):
            buckets[photo.dhash].append(idx)
        for members in buckets.values():
            for other in members[1:]:
                union(members[0], other)
    else:
        for i in range(len(hashed)):
            for j in range(i + 1, len(hashed)):
                if bin(hashed[i].dhash ^ hashed[j].dhash).count("1") <= distance:
                    union(i, j)

    clusters: dict[int, list[Photo]] = defaultdict(list)
    for idx, photo in enumerate(hashed):
        clusters[root(idx)].append(photo)

    groups: list[Group] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        keeper = pick_keeper(members)
        groups.append(Group("near", keeper, [p for p in members if p is not keeper]))
    return groups


def human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{value:.1f}GB"


def quarantine(groups: list[Group], root: Path, bin_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = bin_dir / stamp
    target.mkdir(parents=True, exist_ok=True)

    moves = []
    for group in groups:
        for extra in group.extras:
            try:
                relative = extra.path.relative_to(root)
            except ValueError:
                relative = Path(extra.path.name)
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Never clobber inside the bin: two folders can hold the same name.
            counter = 1
            while destination.exists():
                destination = destination.with_name(
                    f"{destination.stem}~{counter}{destination.suffix}"
                )
                counter += 1
            shutil.move(str(extra.path), str(destination))
            moves.append(
                {"from": str(extra.path), "to": str(destination), "kept": str(group.keeper.path)}
            )

    manifest = target / "undo-manifest.json"
    manifest.write_text(json.dumps({"root": str(root), "moves": moves}, indent=2))
    return manifest


def restore(manifest_path: Path) -> int:
    data = json.loads(manifest_path.read_text())
    restored = 0
    for move in data["moves"]:
        source, destination = Path(move["to"]), Path(move["from"])
        if not source.exists() or destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        restored += 1
    return restored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find and quarantine duplicate photos.")
    parser.add_argument("folder", type=Path, help="folder of photos to scan (searched recursively)")
    parser.add_argument(
        "--distance",
        type=int,
        default=0,
        help="perceptual-hash tolerance in bits, 0-16. 0 = visually identical only "
        "(default), 4-6 = also catch resizes and re-saves, 10+ = aggressive",
    )
    parser.add_argument(
        "--exact-only", action="store_true", help="skip perceptual matching, compare bytes only"
    )
    parser.add_argument(
        "--apply", action="store_true", help="move the extra copies into the quarantine folder"
    )
    parser.add_argument(
        "--bin",
        type=Path,
        default=None,
        help="quarantine folder (default: <folder>/_duplicates_bin)",
    )
    parser.add_argument("--json", type=Path, default=None, help="also write the report as JSON")
    parser.add_argument(
        "--restore", type=Path, default=None, metavar="MANIFEST", help="undo a previous --apply run"
    )
    parser.add_argument("--all-files", action="store_true", help="scan every file, not just media")
    args = parser.parse_args(argv)

    if args.restore:
        count = restore(args.restore)
        print(f"Restored {count} file(s) from {args.restore}")
        return 0

    root = args.folder.expanduser().resolve()
    if not root.is_dir():
        print(f"error: {root} is not a folder", file=sys.stderr)
        return 2
    if not 0 <= args.distance <= 16:
        print("error: --distance must be between 0 and 16", file=sys.stderr)
        return 2

    bin_dir = (args.bin or root / "_duplicates_bin").expanduser().resolve()

    photos = [p for p in collect(root, args.all_files) if bin_dir not in p.path.parents]
    print(f"Scanned {len(photos)} file(s) under {root}")
    if not photos:
        return 0

    groups = find_exact(photos)
    claimed = {p.path for g in groups for p in [g.keeper, *g.extras]}

    undecodable = 0
    if not args.exact_only:
        if Image is None:
            print("note: Pillow not installed, falling back to exact matching only")
        else:
            remaining = [p for p in photos if p.path not in claimed]
            for photo in remaining:
                if photo.path.suffix.lower() not in DECODABLE:
                    continue
                result = dhash_of(photo.path)
                if result is None:
                    undecodable += 1
                    continue
                photo.dhash, photo.pixels = result
            groups.extend(find_near(remaining, args.distance))

    if undecodable:
        print(f"note: {undecodable} file(s) could not be decoded (HEIC needs `pip install pillow-heif`)")

    if not groups:
        print("No duplicates found.")
        return 0

    groups.sort(key=lambda g: -g.reclaimable)
    total_extras = sum(len(g.extras) for g in groups)
    total_bytes = sum(g.reclaimable for g in groups)

    print(f"\n{len(groups)} duplicate group(s), {total_extras} extra copy(s), {human(total_bytes)} reclaimable\n")
    for index, group in enumerate(groups, 1):
        print(f"[{index}] {group.kind} match")
        print(f"    keep   {group.keeper.label}")
        for extra in group.extras:
            print(f"    extra  {extra.label}")
    print()

    if args.json:
        payload = {
            "root": str(root),
            "scanned": len(photos),
            "reclaimable_bytes": total_bytes,
            "groups": [
                {
                    "kind": g.kind,
                    "keep": str(g.keeper.path),
                    "extras": [str(e.path) for e in g.extras],
                }
                for g in groups
            ],
        }
        args.json.write_text(json.dumps(payload, indent=2))
        print(f"Report written to {args.json}")

    if not args.apply:
        print("Dry run — nothing moved. Re-run with --apply to quarantine the extras.")
        return 0

    manifest = quarantine(groups, root, bin_dir)
    print(f"Moved {total_extras} file(s) to {manifest.parent}")
    print(f"Undo with: {Path(sys.argv[0]).name} --restore {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
