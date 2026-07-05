import argparse
import subprocess
from pathlib import Path

from PIL import Image

from posture_guardian.app_bundle import build_icon_image, build_info_plist_xml, build_launcher_script

BUNDLE_NAME = "Posture Guardian.app"
BUNDLE_ID = "com.nuvirahub.postureguardian"
LOG_PATH = str(Path.home() / ".posture_guardian" / "launch_error.log")

_ICONSET_SIZES = (16, 32, 128, 256, 512)


def find_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def generate_icns(resources_dir: Path) -> None:
    resources_dir.mkdir(parents=True, exist_ok=True)
    iconset_dir = resources_dir / "icon.iconset"
    iconset_dir.mkdir(exist_ok=True)

    source = build_icon_image(1024)
    for size in _ICONSET_SIZES:
        source.resize((size, size), Image.LANCZOS).save(iconset_dir / f"icon_{size}x{size}.png")
        source.resize((size * 2, size * 2), Image.LANCZOS).save(iconset_dir / f"icon_{size}x{size}@2x.png")

    subprocess.run(
        ["iconutil", "--convert", "icns", "--output", str(resources_dir / "icon.icns"), str(iconset_dir)],
        check=True,
    )
    for f in iconset_dir.iterdir():
        f.unlink()
    iconset_dir.rmdir()


def build_bundle(project_root: Path, force_icon: bool) -> Path:
    bundle_dir = project_root / BUNDLE_NAME
    contents_dir = bundle_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    (contents_dir / "Info.plist").write_text(build_info_plist_xml(BUNDLE_ID, "launch", "icon.icns"))

    launcher_path = macos_dir / "launch"
    launcher_path.write_text(build_launcher_script(LOG_PATH))
    launcher_path.chmod(0o755)

    icns_path = resources_dir / "icon.icns"
    if force_icon or not icns_path.exists():
        generate_icns(resources_dir)

    subprocess.run(["plutil", "-lint", str(contents_dir / "Info.plist")], check=True)
    return bundle_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate the icon even if it already exists")
    args = parser.parse_args()

    project_root = find_project_root()
    bundle_dir = build_bundle(project_root, force_icon=args.force)
    print(f"Built {bundle_dir}")


if __name__ == "__main__":
    main()
