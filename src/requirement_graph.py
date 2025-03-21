from typing import List, Dict
import networkx as nx

class RequirementGraph:
    def __init__(self, entities: List[Dict]):
        self.entities = entities
        self.graph = nx.DiGraph()
        for entity in entities:
            self.graph.add_node(entity["unique_id"], id=entity["id"], title=entity["title"], text=entity["text"], unique_id=entity["unique_id"])
            for relation in entity["relations"]:
                self.graph.add_edge(entity["unique_id"], relation["destination"], type=relation["type"])

