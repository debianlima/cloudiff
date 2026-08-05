from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]


def test_repository_uses_root_readme_as_github_landing_page():
    assert (ROOT / "README.md").is_file()
    assert not (ROOT / ".github" / "README.md").exists()


def test_readme_visual_assets_exist_and_svg_is_valid():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assets = (
        "docs/assets/cloudiff-algoritmos-operacionais.svg",
        "docs/assets/cloudiff-interface.jpg",
    )
    for relative_path in assets:
        assert relative_path in readme
        assert (ROOT / relative_path).is_file()

    ET.parse(ROOT / assets[0])


def test_documentation_generator_does_not_recreate_shadow_readme():
    generator = (ROOT / "scripts" / "generate-directory-readmes.py").read_text(
        encoding="utf-8"
    )
    assert "LANDING_README_SHADOW" in generator
    assert "directory == ROOT / '.github'" in generator
