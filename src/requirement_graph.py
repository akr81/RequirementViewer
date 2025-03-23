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

    def extract_subgraph(self, target_node: str):
        """Extract subgraph from graph with target node.

        Args:
            target_node (str): Target node to extract subgraph

        """
        # Store graph itself as subgraph if target_node is None
        if target_node is None or target_node == "None":
            self.subgraph = self.graph.copy()
            return

        reachable_upper_nodes = nx.descendants(self.graph, target_node)
        reachable_lower_nodes = nx.ancestors(self.graph, target_node)
        reachable_nodes = reachable_upper_nodes.union(reachable_lower_nodes)
        reachable_nodes.add(target_node)  # 自分自身も含める

        # これらのノードを含むサブグラフを作成
        self.subgraph = self.graph.subgraph(reachable_nodes).copy()
        return
