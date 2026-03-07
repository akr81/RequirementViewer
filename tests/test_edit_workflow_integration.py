"""編集ワークフローの統合テスト。

RequirementManager の CRUD と file_io の保存/復元を通しで検証する。
"""

from __future__ import annotations

import datetime as real_datetime

_REAL_DATETIME_CLASS = real_datetime.datetime
from pathlib import Path

from src import file_io
from src.requirement_manager import RequirementManager


class _SessionState(dict):
    """streamlit.session_state 互換の最小実装。"""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __setattr__(self, name, value):
        self[name] = value


class _FakeStreamlit:
    """テスト用の streamlit 代替。"""

    def __init__(self):
        self.session_state = _SessionState()

    def error(self, *_args, **_kwargs):
        # 本テストでは error 呼び出しは失敗扱い
        raise AssertionError("st.error should not be called in this test")


class _FakeDateTime:
    """backup ファイル名が衝突しないよう now() を単調増加させる。"""

    _counter = 0
    _base = _REAL_DATETIME_CLASS(2026, 1, 1, 0, 0, 0)

    @classmethod
    def now(cls):
        dt = cls._base + real_datetime.timedelta(seconds=cls._counter)
        cls._counter += 1
        return dt

    @classmethod
    def strptime(cls, *args, **kwargs):
        return _REAL_DATETIME_CLASS.strptime(*args, **kwargs)


def _prepare_runtime(monkeypatch, tmp_path: Path, postfix: str = "req"):
    """file_io が期待する最小ランタイム状態を構築する。"""
    monkeypatch.chdir(tmp_path)
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(file_io, "st", fake_st)
    monkeypatch.setattr(file_io.datetime, "datetime", _FakeDateTime)

    app_name = "Requirement Diagram Viewer"
    file_path = tmp_path / "data" / "workflow.hjson"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    fake_st.session_state.app_name = app_name
    fake_st.session_state.app_data = {app_name: {"postfix": postfix}}
    fake_st.session_state.file_path = str(file_path)
    fake_st.session_state["save_png"] = False
    return fake_st, file_path


def test_crud_and_undo_restore(monkeypatch, tmp_path):
    """追加→更新→削除→Undo で1つ前の状態に戻ることを検証。"""
    _fake_st, file_path = _prepare_runtime(monkeypatch, tmp_path)

    data = {"nodes": [], "edges": []}
    manager = RequirementManager(data)

    # 追加
    manager.add({"unique_id": "n1", "title": "Initial"}, None, None)
    file_io.update_source_data(str(file_path), manager.requirements)

    # 更新
    manager.update("n1", {"unique_id": "tmp", "title": "Updated"}, [], [])
    file_io.update_source_data(str(file_path), manager.requirements)

    # 削除
    manager.remove("n1")
    file_io.update_source_data(str(file_path), manager.requirements)
    assert file_io.load_source_data(str(file_path))["nodes"] == []

    # Undo: 削除前（Updated状態）へ戻る
    assert file_io.undo_last_change() is True
    restored = file_io.load_source_data(str(file_path))
    assert len(restored["nodes"]) == 1
    assert restored["nodes"][0]["unique_id"] == "n1"
    assert restored["nodes"][0]["title"] == "Updated"


def test_copy_file_restores_selected_backup(monkeypatch, tmp_path):
    """バックアップ選択から copy_file でファイル復元できることを検証。"""
    fake_st, file_path = _prepare_runtime(monkeypatch, tmp_path, postfix="pfd")

    data = {"nodes": [], "edges": []}
    manager = RequirementManager(data)

    manager.add({"unique_id": "n1", "title": "v1"}, None, None)
    file_io.update_source_data(str(file_path), manager.requirements)
    manager.update("n1", {"unique_id": "tmp", "title": "v2"}, [], [])
    file_io.update_source_data(str(file_path), manager.requirements)

    backups = sorted((tmp_path / "back").glob("*_pfd.hjson"), reverse=True)
    assert len(backups) == 2
    # 1つ前のバックアップ（v1状態）を選択して復元
    fake_st.session_state["selected_backup_file"] = backups[1].name
    file_io.copy_file()

    restored = file_io.load_source_data(str(file_path))
    assert restored["nodes"][0]["title"] == "v1"
    assert fake_st.session_state.get("need_full_rerun") is True

