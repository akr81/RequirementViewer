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
                    entity["unique_id"], relation["destination"], type=relation["type"]
                )
