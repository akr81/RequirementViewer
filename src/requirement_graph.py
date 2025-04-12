from typing import List, Dict
import networkx as nx


class RequirementGraph:
    def __init__(self, entities: List[Dict], title):
        self.entities = entities

        # 要求図全体のグラフ
        self.graph = nx.DiGraph()

        # フィルタリングされたサブグラフ
        self.subgraph = nx.DiGraph()

        # グラフの構築
        if title == "Requirement Diagram":
            self._convert_requirements()
        elif title == "Strategy and Tactics Tree":
            self._convert_strategy_and_tactics()
        elif title == "Current Reality Tree Viewer":
            self._convert_current_reality()
        elif title == "Process Flow Diagram":
            self._convert_process_flow()
        else:
            raise ValueError("Invalid title specified.")

    def _convert_strategy_and_tactics(self):
        for entity in self.entities:
            self.graph.add_node(
                entity["unique_id"],
                id=entity["id"],
                necessary_assumption=entity["necessary_assumption"],
                strategy=entity["strategy"],
                parallel_assumption=entity["parallel_assumption"],
                tactics=entity["tactics"],
                sufficient_assumption=entity["sufficient_assumption"],
                unique_id=entity["unique_id"],
            )
            for relation in entity["relations"]:
                self.graph.add_edge(
                    entity["unique_id"],
                    relation["destination"],
                )

    def _convert_process_flow(self):
        for entity in self.entities:
            self.graph.add_node(
                entity["unique_id"],
                id=entity["id"],
                unique_id=entity["unique_id"],
                type=entity["type"],
                color=entity["color"],
            )
            for relation in entity["relations"]:
                self.graph.add_edge(
                    entity["unique_id"],
                    relation["destination"],
                )

    def _convert_requirements(self):
        """Convert requirements to graph."""
        for entity in self.entities:
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

    def _convert_current_reality(self):
        """Convert current reality tree to graph."""
        for entity in self.entities:
            is_entity = False
            if "type" not in entity or entity["type"] == "entity":
                is_entity = True
            if is_entity:
                self.graph.add_node(
                    entity["unique_id"],
                    id=entity["id"],
                    color=(entity["color"] if "color" in entity else "None"),
                    unique_id=entity["unique_id"],
                    type="card",
                )
            else:
                self.graph.add_node(
                    entity["unique_id"],
                    id=entity["id"],
                    color=(entity["color"] if "color" in entity else "None"),
                    unique_id=entity["unique_id"],
                    type="note",
                )
            for relation in entity["relations"]:
                if is_entity:
                    if (
                        "and" in relation
                        and relation["and"] != None
                        and relation["and"] != "None"
                    ):
                        self.graph.add_node(
                            relation["and"],
                            id=relation["and"],
                            unique_id=relation["and"],
                            type="and",
                        )
                        # and経由の関係を追加
                        self.graph.add_edge(
                            entity["unique_id"], relation["and"], type="arrow"
                        )
                        self.graph.add_edge(
                            relation["and"], relation["destination"], type="arrow"
                        )
                    else:
                        self.graph.add_edge(
                            entity["unique_id"], relation["destination"], type="arrow"
                        )
                else:
                    # note
                    if len(entity["relations"]) > 1:
                        self.graph.add_edge(
                            entity["unique_id"],
                            relation["destination"],
                            type="flat_long",
                        )
                    else:
                        self.graph.add_edge(
                            entity["unique_id"], relation["destination"], type="flat"
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
