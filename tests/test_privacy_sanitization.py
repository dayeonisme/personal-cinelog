from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backup_cleanup_derives_the_repository_root() -> None:
    source = (ROOT / "tools" / "cleanup_db_backups.sh").read_text(encoding="utf-8")

    assert 'REPO="$(cd "$(dirname "$0")/.." && pwd)"' in source
    assert "/Users/" not in source


def test_deployment_readme_uses_generic_vm_placeholders() -> None:
    source = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")

    assert "<VM_NAME>" in source
    assert "<ZONE>" in source
