from typing import List, Dict
import networkx as nx
import copy


class RequirementGraph:
    def __init__(self, entities: List[Dict], page_title: str):
        self.entities = entities
        self.page_title = page_title

        # 要求図全体のグラフ
        self.graph = nx.DiGraph()

        # フィルタリングされたサブグラフ
        self.subgraph = nx.DiGraph()

        # グラフの構築
        self._build_graph()

    def _build_graph(self):
        """Build graph from entities."""
        # ノードの追加
        for node in self.entities["nodes"]:
            # デフォルト値の設定 (必要に応じて)
            # Evaporating Cloud, Current Reality Tree は color="None" がデフォルト
            if self.page_title in [
                "Evaporating Cloud Viewer",
                "Current Reality Tree Viewer",
            ]:
                node.setdefault("color", "None")
            
            self.graph.add_node(node["unique_id"], **node)

        # エッジの追加
        for edge in self.entities["edges"]:
            # デフォルト値の設定
            if self.page_title in [
                "Evaporating Cloud Viewer",
                "Current Reality Tree Viewer",
                "Process Flow Diagram Viewer",
            ]:
                edge.setdefault("type", "arrow")
            
            if self.page_title in [
                "Strategy and Tactics Tree Viewer",
                "Requirement Diagram Viewer",
            ]:
                edge.setdefault("color", "None")

            # Process Flow Diagram の特殊処理: note からのエッジは flat_long に変更
            if (
                self.page_title == "Process Flow Diagram Viewer"
                and self.graph.nodes[edge["source"]].get("type") == "note"
            ):
                modified_edge = copy.deepcopy(edge)
                modified_edge["type"] = "flat_long"
                self.graph.add_edge(
                    modified_edge["source"],
                    modified_edge["destination"],
                    **modified_edge,
                )
            else:
                self.graph.add_edge(edge["source"], edge["destination"], **edge)

    def extract_subgraph(
        self,
        target_node: str,
        upstream_distance: int,
        downstream_distance: int,
        detail: bool = True,
    ):
        """Extract subgraph from graph with target node.

        Args:
            target_node (str): Target node to extract subgraph
            upstream_distance (int): Distance of upstream nodes
            downstream_distance (int): Distance of downstream nodes

        """
        # Store graph itself as subgraph if target_node is None
        if target_node is None or target_node == "None":
            if not detail:
                # ノードの詳細情報がnoteの場合はreachable_nodesから除外する
                reachable_nodes = {
                    node
                    for node in self.graph.nodes()
                    if "type" not in self.graph.nodes[node]
                    or self.graph.nodes[node]["type"] != "note"
                }

                # これらのノードを含むサブグラフを作成
                self.subgraph = self.graph.subgraph(reachable_nodes).copy()
            else:
                self.subgraph = self.graph.copy()
            return

        reachable_upper_nodes = None
        reachable_lower_nodes = None
        reachable_nodes = None

        # Downstream
        lengths = nx.single_source_shortest_path_length(self.graph, target_node)
        reachable_lower_nodes = {
            node
            for node, length in lengths.items()
            if upstream_distance == -1 or length <= upstream_distance
        }

        # Upstream
        lengths_reverse = nx.single_source_shortest_path_length(
            self.graph.reverse(), target_node
        )
        reachable_upper_nodes = {
            node
            for node, length in lengths_reverse.items()
            if downstream_distance == -1 or length <= downstream_distance
        }
        reachable_nodes = reachable_upper_nodes.union(reachable_lower_nodes)

        if not detail:
            # ノードの詳細情報がnoteの場合はreachable_nodesから除外する
            reachable_nodes = {
                node
                for node in reachable_nodes
                if "type" not in self.graph.nodes[node]
                or self.graph.nodes[node]["type"] != "note"
            }

        # これらのノードを含むサブグラフを作成
        self.subgraph = self.graph.subgraph(reachable_nodes).copy()
        return
