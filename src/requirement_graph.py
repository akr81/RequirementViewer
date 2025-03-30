from typing import List, Dict
import networkx as nx


class RequirementGraph:
    def __init__(self, entities: List[Dict]):
        self.entities = entities

        # 要求図全体のグラフ
        self.graph = nx.DiGraph()

        # フィルタリングされたサブグラフ
        self.subgraph = nx.DiGraph()

        # グラフの構築
        for entity in entities:
            self.graph.add_node(
                entity["unique_id"],
                id=entity["id"],
                title=entity["title"],
                text=entity["text"],
                unique_id=entity["unique_id"],
                type=entity["type"],
            )
            for relation in entity["relations"]:
                self.graph.add_edge(
                    entity["unique_id"],
                    relation["destination"],
                    type=relation["type"],
                    note=relation["note"],
                )

    def extract_subgraph(
        self, target_node: str, upstream_distance: int, downstream_distance: int
    ):
        """Extract subgraph from graph with target node.

        Args:
            target_node (str): Target node to extract subgraph
            upstream_distance (int): Distance of upstream nodes
            downstream_distance (int): Distance of downstream nodes

        """
        # Store graph itself as subgraph if target_node is None
        if target_node is None or target_node == "None":
            self.subgraph = self.graph.copy()
            return

        reachable_upper_nodes = None
        reachable_lower_nodes = None
        reachable_nodes = None

        # Downstream
        lengths = nx.single_source_shortest_path_length(self.graph, target_node)
        reachable_lower_nodes = {
            node for node, length in lengths.items() if length <= upstream_distance
        }

        # Upstream
        lengths_reverse = nx.single_source_shortest_path_length(
            self.graph.reverse(), target_node
        )
        reachable_upper_nodes = {
            node
            for node, length in lengths_reverse.items()
            if length <= downstream_distance
        }
        reachable_nodes = reachable_upper_nodes.union(reachable_lower_nodes)

        # これらのノードを含むサブグラフを作成
        self.subgraph = self.graph.subgraph(reachable_nodes).copy()
        return
