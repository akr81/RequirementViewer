"""ccpm_engine のユニットテスト。"""
import networkx as nx
import pytest
from src.ccpm_engine import (
    get_in_out_edge_list,
    calculate_critical_path,
    make_gantt_puml,
    calculate_priority_table,
)


def _make_test_graph():
    """テスト用のグラフを作成する。
    A(3日) -> B(5日) -> D(2日)
    A(3日) -> C(1日) -> D(2日)
    クリティカルパス: A -> B -> D = 10日
    """
    g = nx.DiGraph()
    g.add_node("A", days=3, title="タスクA", resource="田中", start="", end="", remains=0, finished=False)
    g.add_node("B", days=5, title="タスクB", resource="鈴木", start="", end="", remains=0, finished=False)
    g.add_node("C", days=1, title="タスクC", resource="佐藤", start="", end="", remains=0, finished=False)
    g.add_node("D", days=2, title="タスクD", resource="田中", start="", end="", remains=0, finished=False)
    g.add_edge("A", "B")
    g.add_edge("A", "C")
    g.add_edge("B", "D")
    g.add_edge("C", "D")
    return g


class TestGetInOutEdgeList:
    def test_入力端と終端を正しく取得(self):
        g = _make_test_graph()
        inputs, outputs = get_in_out_edge_list(g)
        assert inputs == ["A"]
        assert outputs == ["D"]

    def test_空グラフ(self):
        g = nx.DiGraph()
        inputs, outputs = get_in_out_edge_list(g)
        assert inputs == []
        assert outputs == []


class TestCalculateCriticalPath:
    def test_最長パスを正しく計算(self):
        g = _make_test_graph()
        inputs, outputs = get_in_out_edge_list(g)
        length, path = calculate_critical_path(g, inputs, outputs)
        assert length == 10  # A(3) + B(5) + D(2) = 10
        assert path == ["A", "B", "D"]

    def test_空グラフでは空(self):
        g = nx.DiGraph()
        length, path = calculate_critical_path(g, [], [])
        assert length == 0
        assert path == []

    def test_残日数がクリティカルパスに反映されること(self):
        # タスクBが開始され、残日数(remains)が6日に増えた場合、CPが伸びるか
        g = _make_test_graph()
        g.nodes["B"]["start"] = "2025/07/01"
        g.nodes["B"]["remains"] = 6
        inputs, outputs = get_in_out_edge_list(g)
        length, path = calculate_critical_path(g, inputs, outputs)
        # Bのdays(5)ではなくremains(6)が使われるため、A(3) + B(6) + D(2) = 11 になるはず
        assert length == 11
        assert path == ["A", "B", "D"]

    def test_完了タスクは計算から除外されること(self):
        # タスクAが完了した場合、後続のB, Cから計算が再始動する
        g = _make_test_graph()
        g.nodes["A"]["finished"] = True
        inputs, outputs = get_in_out_edge_list(g)
        length, path = calculate_critical_path(g, inputs, outputs)
        # A(0) + B(5) + D(2) = 7
        assert length == 7
        assert path == ["A", "B", "D"]


class TestMakeGanttPuml:
    def test_ガントチャートコード生成(self):
        g = _make_test_graph()
        project = {"start": "2025/07/01", "end": "2025/08/01", "holidays": [], "today": "2025/07/01"}
        cp = ["A", "B", "D"]
        result = make_gantt_puml(g, project, cp)
        assert "@startgantt" in result
        assert "@endgantt" in result
        assert "[A] lasts 3 days" in result
        assert "colored in pink" in result  # クリティカルパス上のタスク


class TestCalculatePriorityTable:
    def test_優先度テーブル生成(self):
        g = _make_test_graph()
        cp = ["A", "B", "D"]
        result = calculate_priority_table(g, cp)
        assert len(result) > 0
        # 全タスクにbuffer情報がある
        for item in result:
            assert "buffer" in item
            assert "task" in item

    def test_空パスでは空リスト(self):
        g = _make_test_graph()
        result = calculate_priority_table(g, [])
        assert result == []


class TestCalculateCriticalChain:
    def test_リソース競合なしではCPと一致(self):
        """全タスクが異なるリソースなら CC == CP。"""
        from src.ccpm_engine import calculate_critical_chain
        g = _make_test_graph()
        # 全員別リソースなので競合なし
        cc_length, cc_path, virtual_edges = calculate_critical_chain(g)
        cp_length, cp_path = calculate_critical_path(
            g, *get_in_out_edge_list(g)
        )
        assert cc_path == cp_path
        assert cc_length == cp_length
        assert virtual_edges == []

    def test_リソース競合でCCが変わる(self):
        """同一リソースの並行タスクがあると CC が CP より長くなる。"""
        from src.ccpm_engine import calculate_critical_chain
        # A(3日,田中) → C(2日,鈴木)
        # B(4日,田中) → C  ← A と B は並行パスだが田中が競合
        g = nx.DiGraph()
        g.add_node("A", days=3, title="A", resource="田中", start="", end="", remains=0, finished=False)
        g.add_node("B", days=4, title="B", resource="田中", start="", end="", remains=0, finished=False)
        g.add_node("C", days=2, title="C", resource="鈴木", start="", end="", remains=0, finished=False)
        g.add_edge("A", "C")
        g.add_edge("B", "C")

        # CP: B→C = 6日 (A→C は 5日で短い)
        cp_length, cp_path = calculate_critical_path(
            g, *get_in_out_edge_list(g)
        )
        assert cp_length == 6

        # CC: 田中が競合するので A と B は直列化
        # → A→B→C = 9日 or B→A→C = 9日
        cc_length, cc_path, virtual_edges = calculate_critical_chain(g)
        assert cc_length > cp_length  # CC は CP より長くなるはず
        assert len(virtual_edges) == 1  # 1件のリソース競合解消
        assert virtual_edges[0][2] == "田中"  # 田中のリソース競合

