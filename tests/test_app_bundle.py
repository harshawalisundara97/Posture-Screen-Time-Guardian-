from PIL import Image

from posture_guardian.app_bundle import build_icon_image, build_info_plist_xml, build_launcher_script


def test_build_info_plist_xml_contains_required_keys():
    xml = build_info_plist_xml("com.example.app", "launch", "icon.icns")
    assert "<key>CFBundleExecutable</key>" in xml
    assert "<string>launch</string>" in xml
    assert "<key>CFBundleIdentifier</key>" in xml
    assert "<string>com.example.app</string>" in xml
    assert "<key>CFBundleIconFile</key>" in xml
    assert "<string>icon.icns</string>" in xml
    assert "<key>LSUIElement</key>" in xml
    assert "<key>LSRequiresNativeExecution</key>" in xml
    assert "<true/>" in xml


def test_build_launcher_script_execs_module_with_log_redirect():
    script = build_launcher_script("/tmp/example/launch_error.log")
    assert script.startswith("#!/usr/bin/env bash")
    assert "posture_guardian.main" in script
    assert "/tmp/example/launch_error.log" in script
    assert "osascript" in script


def test_build_launcher_script_resolves_path_relative_to_itself():
    script = build_launcher_script("/tmp/example/launch_error.log")
    assert "BASH_SOURCE" in script
    assert ".venv/bin/python" in script


def test_build_icon_image_returns_requested_size_rgba():
    image = build_icon_image(256)
    assert image.size == (256, 256)
    assert image.mode == "RGBA"


def test_build_icon_image_corners_are_transparent():
    image = build_icon_image(256)
    r, g, b, a = image.getpixel((0, 0))
    assert a == 0


def test_build_icon_image_center_is_opaque():
    image = build_icon_image(256)
    r, g, b, a = image.getpixel((128, 128))
    assert a > 0
