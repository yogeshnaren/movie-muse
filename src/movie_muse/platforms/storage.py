"""Platform-native storage roots, protection classes, and origin isolation."""

from __future__ import annotations

from pathlib import Path

from movie_muse.platforms.types import PlatformId, ProtectionClass, StorageProfile

WEB_DEFAULT_ORIGIN = "https://app.moviemuse.local"
DEVICE_KEY_NAME = "device_key"


def origin_slug(origin: str) -> str:
    return origin.strip().replace("://", "_").replace("/", "_")


def storage_root(
    platform: PlatformId,
    home: Path,
    *,
    origin: str = WEB_DEFAULT_ORIGIN,
) -> Path:
    home = Path(home)
    if platform is PlatformId.WEB:
        return home / "origin" / origin_slug(origin) / "opfs" / "MovieMuse"
    if platform is PlatformId.MACOS:
        return home / "Library" / "Application Support" / "MovieMuse"
    if platform is PlatformId.WINDOWS:
        return home / "AppData" / "Local" / "MovieMuse"
    if platform is PlatformId.IOS:
        return home / "Documents" / "MovieMuse"
    return home / "data" / "data" / "com.moviemuse.app" / "files"


def protection_for(platform: PlatformId) -> ProtectionClass:
    mapping = {
        PlatformId.WEB: ProtectionClass.ORIGIN_ISOLATED,
        PlatformId.MACOS: ProtectionClass.APPLICATION_SUPPORT_0700,
        PlatformId.WINDOWS: ProtectionClass.LOCALAPPDATA_RESTRICTED,
        PlatformId.IOS: ProtectionClass.NSFILEPROTECTION_COMPLETE,
        PlatformId.ANDROID: ProtectionClass.MODE_PRIVATE,
    }
    return mapping[platform]


def prepare_storage(
    platform: PlatformId,
    home: Path,
    *,
    origin: str = WEB_DEFAULT_ORIGIN,
) -> StorageProfile:
    root = storage_root(platform, home, origin=origin)
    root.mkdir(parents=True, exist_ok=True)
    mode = 0o700
    if platform is PlatformId.WEB:
        mode = 0o700
    elif platform in {PlatformId.IOS, PlatformId.ANDROID}:
        mode = 0o700
    root.chmod(mode)
    key_path = root / DEVICE_KEY_NAME
    if not key_path.exists():
        key_path.write_bytes(b"platform-device-key")
        key_path.chmod(0o600)
    marker = root / "protection.txt"
    marker.write_text(protection_for(platform).value + "\n", encoding="utf-8")
    marker.chmod(0o600)
    return StorageProfile(
        platform=platform,
        root=str(root),
        protection=protection_for(platform),
        mode=mode,
        origin=origin if platform is PlatformId.WEB else None,
    )
