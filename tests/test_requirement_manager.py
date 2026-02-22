"""RequirementManager のユニットテスト"""
import copy
import pytest
from src.requirement_manager import RequirementManager


# --- ヘルパー ---

def _make_data(nodes=None, edges=None):
    """テスト用データ構造を作成する。"""
    return {
        "nodes": nodes or [],
        "edges": edges or [],
    }


def _node(uid, **extra):
    """テスト用ノードを作成する。"""
    base = {"unique_id": uid, "title": uid}
    base.update(extra)
    return base


def _edge(src, dst, **extra):
    """テスト用エッジを作成する。"""
    base = {"source": src, "destination": dst, "type": "arrow"}
    base.update(extra)
    return base


# --- add ---

class TestAdd:
    def test_ノードが追加される(self):
        data = _make_data()
        mgr = RequirementManager(data)
        node = _node("n1")
        result = mgr.add(node, None, None)
        assert result == "n1"
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["unique_id"] == "n1"

    def test_有効なエッジが追加される(self):
        data = _make_data()
        mgr = RequirementManager(data)
        node = _node("n1")
        new_edges = [_edge("n1", "n2")]
        mgr.add(node, None, new_edges)
        assert len(data["edges"]) == 1

    def test_Noneエッジは除外される(self):
        data = _make_data()
        mgr = RequirementManager(data)
        node = _node("n1")
        # source が "None" のエッジは追加されない
        new_edges = [_edge("None", "n2"), _edge("n1", "None")]
        mgr.add(node, None, new_edges)
        assert len(data["edges"]) == 0

    def test_titleが自動補完される(self):
        data = _make_data()
        mgr = RequirementManager(data)
        node = {"unique_id": "n1"}  # title なし
        mgr.add(node, None, None)
        assert node["title"] == ""


# --- remove ---

class TestRemove:
    def test_ノードが削除される(self):
        data = _make_data(
            nodes=[_node("n1"), _node("n2")],
            edges=[_edge("n1", "n2")],
        )
        mgr = RequirementManager(data)
        mgr.remove("n1")
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["unique_id"] == "n2"

    def test_関連エッジも削除される(self):
        data = _make_data(
            nodes=[_node("n1"), _node("n2"), _node("n3")],
            edges=[_edge("n1", "n2"), _edge("n2", "n3")],
        )
        mgr = RequirementManager(data)
        mgr.remove("n2")
        # n2 に関連するエッジはすべて削除される
        assert len(data["edges"]) == 0

    def test_remove_relations_falseでエッジは残る(self):
        data = _make_data(
            nodes=[_node("n1"), _node("n2")],
            edges=[_edge("n1", "n2")],
        )
        mgr = RequirementManager(data)
        mgr.remove("n1", remove_relations=False)
        assert len(data["edges"]) == 1


# --- update_edge ---

class TestUpdateEdge:
    def test_新規エッジが追加される(self):
        data = _make_data(
            nodes=[_node("n1"), _node("n2")],
        )
        mgr = RequirementManager(data)
        mgr.update_edge("n1", "n2", {"type": "arrow", "and": "None"})
        assert len(data["edges"]) == 1
        assert data["edges"][0]["source"] == "n1"
        assert data["edges"][0]["destination"] == "n2"

    def test_既存エッジはトグル削除される(self):
        data = _make_data(
            nodes=[_node("n1"), _node("n2")],
            edges=[_edge("n1", "n2")],
        )
        mgr = RequirementManager(data)
        mgr.update_edge("n1", "n2", {"type": "arrow"})
        # 既存のエッジが削除される（トグル動作）
        assert len(data["edges"]) == 0

    def test_トグル後に再追加できる(self):
        data = _make_data(
            nodes=[_node("n1"), _node("n2")],
            edges=[_edge("n1", "n2")],
        )
        mgr = RequirementManager(data)
        # 1回目: 削除
        mgr.update_edge("n1", "n2", {"type": "arrow"})
        assert len(data["edges"]) == 0
        # 2回目: 再追加
        mgr.update_edge("n1", "n2", {"type": "arrow"})
        assert len(data["edges"]) == 1


# --- update ---

class TestUpdate:
    def test_ノードが更新される(self):
        data = _make_data(
            nodes=[_node("n1", text="old")],
            edges=[],
        )
        mgr = RequirementManager(data)
        new_req = _node("tmp_id", text="new")
        mgr.update("n1", new_req, None, None)
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["text"] == "new"
        assert data["nodes"][0]["unique_id"] == "n1"

    def test_エッジのunique_idが差し替えられる(self):
        data = _make_data(
            nodes=[_node("n1"), _node("n2")],
            edges=[_edge("n1", "n2")],
        )
        mgr = RequirementManager(data)
        new_req = _node("tmp_id")
        tmp_edges = copy.deepcopy(data["edges"])
        # new_req のIDから n1 への差し替えが起きる
        new_edges = [_edge("tmp_id", "n2")]
        mgr.update("n1", new_req, tmp_edges, new_edges)
        # tmp_id が n1 に差し替えられていること
        for e in data["edges"]:
            assert e["source"] != "tmp_id"
