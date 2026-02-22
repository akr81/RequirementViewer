from typing import List, Dict
import networkx as nx
import copy


from src.constants import AppName, NodeType, EdgeType, Color

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
        """エンティティからグラフを構築する。"""
        # ノードの追加
        for node in self.entities["nodes"]:
            # デフォルト値の設定 (必要に応じて)
            # Evaporating Cloud, Current Reality Tree は color="None" がデフォルト
            if self.page_title in [
                AppName.EVAPORATING_CLOUD,
                AppName.CURRENT_REALITY,
            ]:
                node.setdefault("color", Color.NONE)
            
            self.graph.add_node(node["unique_id"], **node)

        # エッジの追加
        for edge in self.entities["edges"]:
            # source/destination がグラフのノードに存在しないエッジはスキップ
            # （過去に混入した "default" 等の不正エッジへの耐性）
            if edge["source"] not in self.graph or edge["destination"] not in self.graph:
                continue

            # デフォルト値の設定
            if self.page_title in [
                AppName.EVAPORATING_CLOUD,
                AppName.CURRENT_REALITY,
                AppName.PROCESS_FLOW,
            ]:
                edge.setdefault("type", EdgeType.ARROW)
            
            if self.page_title in [
                AppName.STRATEGY_TACTICS,
                AppName.REQUIREMENT,
            ]:
                edge.setdefault("color", Color.NONE)

            # Process Flow Diagram の特殊処理: note からのエッジは flat_long に変更
            if (
                self.page_title == AppName.PROCESS_FLOW
                and self.graph.nodes[edge["source"]].get("type") == NodeType.NOTE
            ):
                modified_edge = copy.deepcopy(edge)
                modified_edge["type"] = EdgeType.FLAT_LONG
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
        """対象ノードを含むサブグラフを抽出する。

        Args:
            target_node (str): サブグラフ抽出の起点となるターゲットノード
            upstream_distance (int): 遡る上流ノードの距離制限 (-1で無制限)
            downstream_distance (int): 辿る下流ノードの距離制限 (-1で無制限)
            detail (bool): 詳細(note等)を含めるかどうか
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

        # 下流（Downstream）の探索
        lengths = nx.single_source_shortest_path_length(self.graph, target_node)
        reachable_lower_nodes = {
            node
            for node, length in lengths.items()
            if downstream_distance == -1 or length <= downstream_distance
        }

        # 上流（Upstream）の探索
        lengths_reverse = nx.single_source_shortest_path_length(
            self.graph.reverse(), target_node
        )
        reachable_upper_nodes = {
            node
            for node, length in lengths_reverse.items()
            if upstream_distance == -1 or length <= upstream_distance
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
