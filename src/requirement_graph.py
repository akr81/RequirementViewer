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
        if title == "Requirement Diagram Viewer":
            self._convert_requirements()
        elif title == "Strategy and Tactics Tree Viewer":
            self._convert_strategy_and_tactics()
        elif title == "Current Reality Tree Viewer":
            self._convert_current_reality()
        elif title == "Process Flow Diagram Viewer":
            self._convert_process_flow()
        elif title == "Evaporating Cloud Viewer":
            self._convert_evaporating_cloud()
        elif title == "Evaporating Cloud Viewer":
            self._convert_evaporating_cloud()
        else:
            raise ValueError("Invalid title specified.")

    def _convert_evaporating_cloud(self):
        for entity in self.entities:
            entity.setdefault("color", "None")  # colorがない場合はNoneを設定
            self.graph.add_node(entity["unique_id"], **entity)
            for relation in entity["relations"]:
                relation.setdefault("type", "arrow")  # typeがない場合はarrowを設定
                self.graph.add_edge(
                    entity["unique_id"],
                    relation["destination"],
                    type=relation["type"],
                )

    def _convert_strategy_and_tactics(self):
        for entity in self.entities:
            entity.setdefault("color", "None")  # colorがない場合はNoneを設定
            self.graph.add_node(entity["unique_id"], **entity)
            for relation in entity["relations"]:
                relation.setdefault("type", "arrow")  # typeがない場合はarrowを設定
                self.graph.add_edge(
                    entity["unique_id"],
                    relation["destination"],
                    type=relation["type"],
                )

    def _convert_process_flow(self):
        for entity in self.entities:
            self.graph.add_node(entity["unique_id"], **entity)
            for relation in entity["relations"]:
                relation.setdefault("type", "arrow")  # typeがない場合はarrowを設定
                if entity["type"] == "note":
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
                else:
                    self.graph.add_edge(
                        entity["unique_id"],
                        relation["destination"],
                        type=relation["type"],
                    )

    def _convert_requirements(self):
        """Convert requirements to graph."""
        for entity in self.entities:
            entity.setdefault("color", "None")  # colorがない場合はNoneを設定
            self.graph.add_node(entity["unique_id"], **entity)
            for relation in entity["relations"]:
                self.graph.add_edge(
                    entity["unique_id"],
                    relation["destination"],
                    type=relation["type"],
                    note=relation["note"],
                )

    def _add_note_edge(self, entity, relation):
        """Add edge for note type entity.
        Note type entity is connected to destination with flat or flat_long edge.
        """
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

    def _convert_current_reality(self):
        """Convert current reality tree to graph."""
        for entity in self.entities:
            entity.setdefault("color", "None")  # colorがない場合はNoneを設定
            if "type" not in entity or entity["type"] == "entity":
                # entity["type"] = "card"  # cardとして描画する
                pass
            self.graph.add_node(entity["unique_id"], **entity)
            print(f"added {entity['unique_id']}")
            for relation in entity["relations"]:
                # if entity["type"] == "card":
                if entity["type"] == "entity":
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
                    self._add_note_edge(entity, relation)

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
