"""End-to-end tests for the CLI."""

from __future__ import annotations

import json

import pytest

from pawprint.cli import main


def _site(tmp_path):
    (tmp_path / "index.md").write_text(
        "---\ntitle: My Site\ndescription: The home page.\n---\n# My Site\n\nWelcome.\n",
        encoding="utf-8",
    )
    sub = tmp_path / "guide"
    sub.mkdir()
    (sub / "start.md").write_text(
        "---\ntitle: Start Here\ndescription: First guide page.\n---\n# Start\n\nBegin.\n",
        encoding="utf-8",
    )


def test_no_args_prints_help(capsys):
    assert main([]) == 0
    assert "pawprint" in capsys.readouterr().out


def test_build_writes_both_files(tmp_path, capsys):
    _site(tmp_path)
    assert main(["build", str(tmp_path)]) == 0
    assert (tmp_path / "llms.txt").exists()
    assert (tmp_path / "llms-full.txt").exists()
    out = capsys.readouterr().out
    assert "2 pages" in out


def test_build_out_dir_is_separate(tmp_path, capsys):
    _site(tmp_path)
    out_dir = tmp_path / "dist"
    assert main(["build", str(tmp_path), "--out", str(out_dir)]) == 0
    assert (out_dir / "llms.txt").exists()
    assert not (tmp_path / "llms.txt").exists()


def test_build_json_summary(tmp_path, capsys):
    _site(tmp_path)
    assert main(["build", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["pages"] == 2
    assert data["index_bytes"] > 0
    assert data["full_bytes"] > 0


def test_build_respects_drafts(tmp_path, capsys):
    (tmp_path / "live.md").write_text("# Live\n", encoding="utf-8")
    (tmp_path / "wip.md").write_text("---\ndraft: true\ntitle: WIP\n---\n# W\n", encoding="utf-8")
    assert main(["build", str(tmp_path), "--include-drafts", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["pages"] == 2


def test_build_with_base_url(tmp_path):
    _site(tmp_path)
    main(["build", str(tmp_path), "--base-url", "https://example.com"])
    text = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    assert "https://example.com/guide/start" in text


def test_build_empty_tree_still_writes(tmp_path, capsys):
    assert main(["build", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["pages"] == 0


def test_audit_text_output(tmp_path, capsys):
    _site(tmp_path)
    assert main(["audit", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "AI-readiness:" in out
    assert "Pages: 2" in out


def test_audit_json_output(tmp_path, capsys):
    _site(tmp_path)
    assert main(["audit", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert "score" in data
    assert "grade" in data
    assert len(data["checks"]) == 5


def test_policy_uses_robots_in_cwd(tmp_path, capsys, monkeypatch):
    (tmp_path / "robots.txt").write_text(
        "User-agent: GPTBot\nAllow: /\nSitemap: https://x/s.xml\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    assert main(["policy"]) == 0
    out = capsys.readouterr().out
    assert "GPTBot" in out
    assert "Recommendations:" in out


def test_policy_json_output(tmp_path, capsys):
    robots = tmp_path / "robots.txt"
    robots.write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    assert main(["policy", str(robots), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert any(c["name"] == "GPTBot" for c in data["crawlers"])
    assert isinstance(data["recommendations"], list)


def test_policy_missing_file_still_reports(tmp_path, capsys):
    assert main(["policy", str(tmp_path / "nope.txt")]) == 0
    out = capsys.readouterr().out
    assert "no robots.txt found" in out


def test_policy_fix_prints_starter(tmp_path, capsys):
    assert main(["policy", "--fix"]) == 0
    out = capsys.readouterr().out
    assert "User-agent: GPTBot" in out
    assert "Sitemap:" in out


class TestBuildCheck:
    """`build --check` answers "is the committed llms.txt current?" without writing."""

    def test_check_fails_when_llms_txt_missing(self, tmp_path, capsys):
        _site(tmp_path)
        assert main(["build", str(tmp_path), "--check"]) == 1
        out = capsys.readouterr().out
        assert "missing" in out
        assert not (tmp_path / "llms.txt").exists()

    def test_check_passes_when_fresh(self, tmp_path, capsys):
        _site(tmp_path)
        main(["build", str(tmp_path)])
        capsys.readouterr()
        assert main(["build", str(tmp_path), "--check"]) == 0
        assert "up to date" in capsys.readouterr().out

    def test_check_fails_when_content_added(self, tmp_path, capsys):
        _site(tmp_path)
        main(["build", str(tmp_path)])
        (tmp_path / "guide" / "later.md").write_text(
            "---\ntitle: Later\ndescription: Added after the build.\n---\n# Later\n\nMore.\n",
            encoding="utf-8",
        )
        capsys.readouterr()
        assert main(["build", str(tmp_path), "--check"]) == 1
        assert "stale" in capsys.readouterr().out

    def test_check_fails_when_content_edited(self, tmp_path, capsys):
        _site(tmp_path)
        main(["build", str(tmp_path)])
        text = (tmp_path / "guide" / "start.md").read_text(encoding="utf-8")
        (tmp_path / "guide" / "start.md").write_text(
            text.replace("Begin.", "Begin here, with more words than before."), encoding="utf-8"
        )
        capsys.readouterr()
        assert main(["build", str(tmp_path), "--check"]) == 1

    def test_check_does_not_write(self, tmp_path, capsys):
        _site(tmp_path)
        main(["build", str(tmp_path)])
        (tmp_path / "guide" / "later.md").write_text(
            "---\ntitle: Later\ndescription: Added after the build.\n---\n# Later\n\nMore.\n",
            encoding="utf-8",
        )
        before = (tmp_path / "llms.txt").read_text(encoding="utf-8")
        assert main(["build", str(tmp_path), "--check"]) == 1
        assert (tmp_path / "llms.txt").read_text(encoding="utf-8") == before

    def test_check_json_reports_state(self, tmp_path, capsys):
        _site(tmp_path)
        main(["build", str(tmp_path)])
        capsys.readouterr()
        assert main(["build", str(tmp_path), "--check", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["stale"] is False
        assert data["pages"] == 2

    def test_check_json_missing_is_stale(self, tmp_path, capsys):
        _site(tmp_path)
        assert main(["build", str(tmp_path), "--check", "--json"]) == 1
        data = json.loads(capsys.readouterr().out)
        assert data["stale"] is True
        assert data["reason"] == "missing"

    def test_check_reads_out_dir(self, tmp_path, capsys):
        _site(tmp_path)
        out_dir = tmp_path / "dist"
        main(["build", str(tmp_path), "--out", str(out_dir)])
        capsys.readouterr()
        assert main(["build", str(tmp_path), "--out", str(out_dir), "--check"]) == 0
        assert main(["build", str(tmp_path), "--check"]) == 1

    def test_check_without_build_exits_one(self, tmp_path, capsys):
        _site(tmp_path)
        assert main(["build", str(tmp_path), "--check", "--include-drafts"]) == 1


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "pawprint" in capsys.readouterr().out
