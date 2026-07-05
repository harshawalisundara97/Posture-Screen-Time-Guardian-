from posture_guardian import launch_agent


def test_build_plist_xml_contains_label_and_command():
    xml = launch_agent.build_plist_xml("com.example.app", "/usr/bin/python3", "posture_guardian.main")
    assert "<string>com.example.app</string>" in xml
    assert "<string>/usr/bin/python3</string>" in xml
    assert "<string>posture_guardian.main</string>" in xml
    assert "<true/>" in xml  # RunAtLoad


def test_is_enabled_false_when_plist_missing(tmp_path):
    plist_path = str(tmp_path / "missing.plist")
    assert launch_agent.is_enabled(plist_path) is False


def test_is_enabled_true_when_plist_exists(tmp_path):
    plist_path = tmp_path / "present.plist"
    plist_path.write_text("<plist/>")
    assert launch_agent.is_enabled(str(plist_path)) is True
