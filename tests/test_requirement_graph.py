"""RequirementGraph のユニットテスト"""
import pytest
from src.requirement_graph import RequirementGraph
from src.constants import AppName, EdgeType


def _make_crt_data(nodes, edges):
    """CRT用テストデータを作成する。"""
    return {
        "nodes": [
            {"unique_id": uid, "text": text, "type": "entity", "color": "None"}
            for uid, text in nodes
        ],
        "edges": [
            {"source": src, "destination": dst, "type": "arrow", "and": "None"}
            for src, dst in edges
        ],
    }


class TestBuildGraph:
    def test_ノード数が正しい(self):
        data = _make_crt_data(
            nodes=[("n1", "A"), ("n2", "B"), ("n3", "C")],
            edges=[("n1", "n2"), ("n2", "n3")],
        )
        g = RequirementGraph(data, AppName.CURRENT_REALITY)
        assert g.graph.number_of_nodes() == 3

    def test_エッジ数が正しい(self):
        data = _make_crt_data(
            nodes=[("n1", "A"), ("n2", "B"), ("n3", "C")],
            edges=[("n1", "n2"), ("n2", "n3")],
        )
        g = RequirementGraph(data, AppName.CURRENT_REALITY)
        assert g.graph.number_of_edges() == 2

    def test_ノードがない場合(self):
        data = _make_crt_data(nodes=[], edges=[])
        g = RequirementGraph(data, AppName.CURRENT_REALITY)
        assert g.graph.number_of_nodes() == 0


class TestExtractSubgraph:
    @pytest.fixture
    def chain_graph(self):
        """n1 → n2 → n3 → n4 の直線チェーン"""
        data = _make_crt_data(
            nodes=[("n1", "A"), ("n2", "B"), ("n3", "C"), ("n4", "D")],
            edges=[("n1", "n2"), ("n2", "n3"), ("n3", "n4")],
        )
        return RequirementGraph(data, AppName.CURRENT_REALITY)

    def test_全ノード抽出_target_None(self, chain_graph):
        chain_graph.extract_subgraph(None, -1, -1)
        assert chain_graph.subgraph.number_of_nodes() == 4

    def test_全ノード抽出_target_None文字列(self, chain_graph):
        chain_graph.extract_subgraph("None", -1, -1)
        assert chain_graph.subgraph.number_of_nodes() == 4

    def test_距離制限なし(self, chain_graph):
        chain_graph.extract_subgraph("n2", -1, -1)
        assert chain_graph.subgraph.number_of_nodes() == 4

    def test_下流のみ距離1(self, chain_graph):
        chain_graph.extract_subgraph("n2", 0, 1)
        nodes = set(chain_graph.subgraph.nodes())
        # n2 自身 + 下流1つ(n3)
        assert "n2" in nodes
        assert "n3" in nodes
        assert "n4" not in nodes

    def test_上流のみ距離1(self, chain_graph):
        chain_graph.extract_subgraph("n3", 1, 0)
        nodes = set(chain_graph.subgraph.nodes())
        # n3 自身 + 上流1つ(n2)
        assert "n3" in nodes
        assert "n2" in nodes
        assert "n1" not in nodes

    def test_detailがfalseでnoteが除外される(self):
        data = {
            "nodes": [
                {"unique_id": "n1", "text": "A", "type": "entity", "color": "None"},
                {"unique_id": "note1", "text": "メモ", "type": "note", "color": "None"},
            ],
            "edges": [
                {"source": "n1", "destination": "note1", "type": "flat_long", "and": "None"},
            ],
        }
        g = RequirementGraph(data, AppName.CURRENT_REALITY)
        g.extract_subgraph(None, -1, -1, detail=False)
        nodes = set(g.subgraph.nodes())
        assert "n1" in nodes
        assert "note1" not in nodes
