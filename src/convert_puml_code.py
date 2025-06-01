from typing import Dict, List, Tuple, Any
import networkx as nx
import re
import unicodedata
import hjson
import copy

with open("setting/colors.json", "r", encoding="utf-8") as f:
    color_to_archimate = hjson.load(f)


class ConvertPumlCode:
    """Convert graph to PlantUML code."""

    def __init__(self, config: Dict[str, Any]):
        """Initializer

        Args:
            config (Dict[str, Any]): Config settings
        """
        self.detail = config["detail"]
        self.debug = config["debug"]
        self.diagram_converters = {
            "Requirement Diagram Viewer": self._convert_requirement_diagram,
            "Strategy and Tactics Tree Viewer": self._convert_strategy_and_tactics,
            "Current Reality Tree Viewer": self._convert_current_reality,
            "Process Flow Diagram Viewer": self._convert_process_flow_diagram,
            "Evaporating Cloud Viewer": self._convert_evaporating_cloud,
        }
        self.diagram_specific_settings = {
            "Requirement Diagram Viewer": {"ortho": True, "sep": 0},
            "Strategy and Tactics Tree Viewer": {"ortho": True, "sep": 0},
            "Current Reality Tree Viewer": {"ortho": False, "sep": 20},
            "Process Flow Diagram Viewer": {"ortho": False, "sep": 20},
            "Evaporating Cloud Viewer": {"ortho": False, "sep": 0},
        }

    def convert_to_puml(
        self, page_title: str, graph: nx.DiGraph, title: str, parameters_dict: Dict
    ) -> str:
        """Convert graph to requirement diagram as PlantUML code string.

        Args:
            page_title (str): Page title.
            graph (nx.DiGraph): Graph of requirements.
            title (str): Title of diagram.
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code
        """
        specific_settings = self.diagram_specific_settings.get(
            page_title, {"ortho": True, "sep": 0}
        )  # Default if not found
        ortho = specific_settings.get("ortho", True)
        sep = specific_settings.get("sep", 0)
        scale = parameters_dict.get("scale", 1.0)
        landscape = parameters_dict.get("landscape", False)

        puml_parts = [
            self._add_common_parameter_setting(scale, ortho, sep, landscape=landscape)
        ]

        converter_method = self.diagram_converters.get(page_title)
        if converter_method:
            diagram_body = converter_method(graph, title, parameters_dict)
            puml_parts.append(diagram_body)
        else:
            raise ValueError(f"Invalid page_title specified: {page_title}")
        puml_parts.append("@enduml")
        return "\n".join(puml_parts)

    def _add_common_parameter_setting(
        self, scale: float, ortho: bool = True, sep: int = 0, *, landscape: bool = False
    ) -> str:
        ortho_str = (
            """
skinparam linetype polyline
skinparam linetype ortho
"""
            if ortho
            else ""
        )
        sep_str = (
            f"""
skinparam nodesep {sep}
skinparam ranksep {sep}
"""
            if sep != 0
            else ""
        )
        landscape = "left to right direction" if landscape else ""

        return f"""
@startuml
'!pragma layout elk
hide circle
hide empty members
hide method
{ortho_str}
{sep_str}
{landscape}
skinparam HyperlinkUnderline false
skinparam usecase {{
BackgroundColor White
ArrowColor Black
BorderColor Black
FontSize 12
}}
skinparam card {{
BackgroundColor White
ArrowColor Black
BorderColor Black
FontSize 12
}}
skinparam class {{
BackgroundColor White
ArrowColor Black
BorderColor Black
}}
skinparam note {{
BackgroundColor White
ArrowColor Black
BorderColor Black
FontSize 12
}}
allowmixing

scale {scale}
"""

    def _get_puml_color(self, node_attributes: Dict) -> str:
        """ノード属性からPlantUML用の色指定文字列を取得する。"""
        color_name = node_attributes.get("color")
        if color_name and color_name != "None":
            # color_to_archimate に存在しないキーの場合は空文字を返す
            return color_to_archimate.get(color_name, "")
        return ""

    def _convert_requirement_diagram(
        self, graph: nx.DiGraph, title: str, parameters_dict: Dict
    ) -> str:
        """Convert requirement graph to PlantUML code.
        Args:

            target (str): Target node that filters the graph.
            graph (nx.DiGraph): Graph of requirements.
            title (str): Title of diagram.
            parameters_dict (Dict): Parameters for link.
        """
        # Draw package as frame
        target = parameters_dict.get("target", None)
        if not title:
            if target == None or target == "None":
                title = '"req Requirements [all]"'
            else:
                target_title = graph.nodes(data=True)[target]["title"]
                title = f'"req {target_title} ' + 'related requirements"'
        else:
            title = f'"req {title}"'

        puml_parts = []

        # Add title as package
        puml_parts.append(f"package {title} <<Frame>> " + "{")

        # Convert all nodes
        for node in graph.nodes(data=True):
            puml_parts.append(self._convert_requirement_node(node, parameters_dict))

        # Convert edges
        for edge in graph.edges(data=True):
            puml_parts.append(self._convert_requirement_edge(edge))

        puml_parts.append("}")
        return "\n".join(puml_parts)

    def _convert_parameters_dict(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Convert parameters dict to PlantUML link string.

        Args:
            node (Tuple[str, Dict]): Node information (unique_id is in node[1]['unique_id']).
            parameters_dict (Dict): Parameters for the link base.

        Returns:
            str: PlantUML link string like "[[?param1=val1&selected=id]]".
        """
        query_items = []
        if parameters_dict:  # parameters_dictがNoneや空でないことを確認
            for key, value in parameters_dict.items():
                query_items.append(f"{key}={value}")

        # 常にselectedパラメータを追加
        query_items.append(f"selected={node[1]['unique_id']}")

        if not query_items:  # 通常は発生しないはず (selectedが常に追加されるため)
            return "[[]]"  # 空のリンクの場合のデフォルト

        return f"[[?{'&'.join(query_items)}]]"

    def _convert_evaporating_cloud_note(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        # Get parameters string and modify for note
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        parameters_str = parameters_str[:-2] + " *]]"  # Specific for note links

        # Get color string
        color_str = self._get_puml_color(node_attrs)
        return f"""
note as {node_attrs['unique_id']} {color_str}
{node_attrs['title']} {parameters_str}
end note
"""

    def _convert_evaporating_cloud(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        puml_parts = []

        # Convert all nodes
        for node in graph.nodes(data=True):
            node_attrs = node[1]
            if node_attrs["type"] == "note":
                puml_parts.append(
                    self._convert_evaporating_cloud_note(node, parameters_dict)
                )
            else:
                puml_parts.append(
                    self._convert_evaporating_cloud_card_node(node, parameters_dict)
                )

        # Convert edges
        for edge in graph.edges(data=True):
            puml_parts.append(self._convert_card_edge(edge))

        # conflict
        puml_parts.append(
            """left_hand <=> right_hand #red
left_shoulder <=> right_shoulder #red
left_shoulder <.. right_hand #blue
right_shoulder <.. left_hand #blue
left_hand .. left_hand_note
right_hand .. right_hand_note
left_hand_to_shoulder .r. left_shoulder
left_hand_to_shoulder .. left_hand
right_hand_to_shoulder .l. right_shoulder
right_hand_to_shoulder .. right_hand
left_shoulder_to_head .r. head
left_shoulder_to_head .. left_shoulder
right_shoulder_to_head .l. head
right_shoulder_to_head .. right_shoulder"""
        )

        return "\n".join(puml_parts)

    def _create_card_puml(
        self, unique_id: str, content: str, parameters_str: str, color_str: str
    ) -> str:
        """Generates the PlantUML string for a card element."""
        return f"""card {unique_id} {parameters_str} {color_str} [
{content}
]
"""

    def _convert_evaporating_cloud_card_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        return self._create_card_puml(
            node_attrs["unique_id"], node_attrs["title"], parameters_str, color_str
        )

    def _convert_requirement_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Convert requirement node information to PlantUML code.

        Args:
            node (Tuple[str, Dict]): Node information.
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code.
        """
        parameters = self._convert_parameters_dict(node, parameters_dict)
        attr = node[1]
        type = attr["type"]
        ret = ""
        if type == "usecase":
            ret = self._convert_usecase(attr)
        elif (
            type == "requirement"
            or type == "functionalRequirement"
            or type == "interfaceRequirement"
            or type == "performanceRequirement"
            or type == "physicalRequirement"
            or type == "designConstraint"
        ):
            ret = self._convert_requirement(attr, type, parameters)
        elif type == "block" or type == "testCase":
            ret = self._convert_block(attr, type, parameters)
        elif type == "rationale" or type == "problem":
            ret = self._convert_note_entity(attr)
        else:
            raise ValueError(
                f"No convert rule defined error: Unknown type specified: {type}"
            )

        return ret

    def _convert_usecase(self, data: Dict[str, Any]) -> str:
        """Convert usecase information to PlantUML code.

        Args:
            data (Dict[str, Any]): Usecase information

        Returns:
            str: PlantUML code
        """
        # For PlantUML, the "usecase" entity cannot used on class diagram
        title = data["title"]
        ret = f"usecase \"{self._get_title_string(data['id'], title)}\" as {data['unique_id']} <<usecase>>"
        return ret

    def _convert_requirement(
        self, data: Dict[str, Any], type: str, parameters: str
    ) -> str:
        """Convert requirement information to PlantUML code.

        Args:
            data (Dict[str, Any]): Requirement information
            type (str): Type of requirement
            parameters (str): Parameter string for link

        Returns:
            str: PlantUML code
        """
        title = data["title"]
        text = data["text"]
        color_str = self._get_puml_color(data)

        # Ignore () as method using {field}
        ret = (
            f"class \"{title}\" as {data['unique_id']} <<{type}>> {parameters} {color_str} "
            + "{\n"
        )

        ret += "{field}" + f"id=\"{data['id']}\"\n"
        ret += "{field}" + f'text="{text}"\n'
        ret += "}\n"
        return ret

    def _convert_block(self, data: Dict[str, Any], type: str, parameters: str) -> str:
        """Convert block information to PlantUML code.

        Args:
            data (Dict[str, Any]): Block information
            type (str): Type information
            parameters (str): Parameter string for link

        Returns:
            str: PlantUML code
        """
        title = data["title"]
        ret = f"class \"{self._get_title_string(data['id'], title)}\" as {data['unique_id']} <<{type}>> {parameters}"
        return ret

    def _convert_note_entity(self, data: Dict[str, Any]) -> str:
        """Return note type entity string
        This method is for rationale, problem entity.

        Args:
            data (Dict[str, Any]): Entity (node)

        Returns:
            str: PlantUML string for note
        """
        # Display longer string from title and text
        if len(data["title"]) >= len(data["text"]):
            string = data["title"]
        else:
            string = data["text"]

        ret = ""
        ret += f"note as {data['unique_id']}\n"
        ret += f"<<{data['type']}>>\n"
        ret += f"{string}\n"
        ret += f"end note\n"

        return ret

    def _get_title_string(self, id: str, title: str) -> str:
        """Return title string (ID + title)

        Args:
            id (str): ID of requirement
            title (str): Title of requirement

        Returns:
            str: Title string
        """
        if id != "":
            return f"{id}\\n{title}"
        else:
            return f"{title}"

    def _convert_requirement_edge(self, data: Dict[str, Any]):
        """Return relationship string

        Args:
            data (Dict[str, Any]): Relationship (node)

        Returns:
            str: PlantUML string
        """
        src = data[0]
        dst = data[1]
        type = data[2]["type"]
        note = data[2]["note"]
        ret = ""
        if type == "containment":
            ret = f"{dst} +-- {src}"
        elif (
            type == "refine"
            or type == "deriveReqt"
            or type == "satisfy"
            or type == "verify"
            or type == "copy"
            or type == "trace"
        ):
            ret = f"{dst} <.. {src}: <<{type}>>"
        elif type == "problem" or type == "rationale":
            # For rationale and problem (entity) only
            ret = f"{dst} .. {src}"
        else:
            raise ValueError(f"No implement exist for relation type: {type}")

        if note and note["text"] != "":
            ret += "\n"
            ret += f"note on link\n"
            if note["type"] != "None":
                ret += f"<<{note['type']}>>\n"
            ret += f"{note['text']}\n"
            ret += f"end note\n"
        return ret

    def _convert_note_edge(self, note_id: str, nodes: List[Dict[str, Any]]) -> str:
        """Return note type entity string
        This method is for rationale, problem entity connected to relation.

        Args:
            data (Dict[str, Any]): Entity (node)

        Returns:
            str: PlantUML string for note
        """
        ret = ""
        for node in nodes:
            if node[1]["unique_id"] == note_id:
                # Display longer string from title and text
                if len(node[1]["title"]) >= len(node[1]["text"]):
                    string = node[1]["title"]
                else:
                    string = node[1]["text"]

                string = string.replace("\\n", "\n")

                ret = ""
                ret += f"note on link\n"
                ret += f"<<{node[1]['type']}>>\n"
                if self.debug:
                    ret += f'unique_id="{note_id}"\n'
                ret += f"{string}\n"
                ret += f"end note\n"
        return ret

    def _convert_strategy_and_tactics(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        """Convert graph to strategy and tactics tree diagram as PlantUML code string.

        Args:
            graph (nx.DiGraph): Graph of requirements.
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code
        """
        puml_parts = []

        # Convert all nodes
        for node in graph.nodes(data=True):
            puml_parts.append(self._convert_st_card_node(node, parameters_dict))

        # Convert edges
        for edge in graph.edges(data=True):
            puml_parts.append(self._convert_card_edge(edge))

        return "\n".join(puml_parts)

    def _convert_st_card_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Converts a node for Strategy and Tactics Tree into a card."""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        content = f"""{node_attrs["id"]}
---
{node_attrs["strategy"]}
---
{node_attrs["tactics"]}"""
        return self._create_card_puml(
            node_attrs["unique_id"], content, parameters_str, color_str
        )

    def _convert_card_edge(self, data: Dict[str, Any], reverse=False):
        src = data[0]
        dst = data[1]
        explanation = ""
        if "comment" in data[2] and data[2]["comment"] != "":
            explanation = ":" + data[2]["comment"]
        if data[2]["type"] == "arrow":
            if reverse:
                ret = f"{src} --> {dst} {explanation}"
            else:
                ret = f"{dst} <-- {src} {explanation}"
        elif data[2]["type"] == "flat":
            ret = f"{dst} . {src} {explanation}"
        elif data[2]["type"] == "flat_long":
            ret = f"{dst} .. {src} {explanation}"

        return ret

    def _convert_current_reality(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        """Convert graph to strategy and tactics tree diagram as PlantUML code string.

        Args:
            graph (nx.DiGraph): Graph of requirements.
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code
        """
        puml_parts = []

        # Convert all nodes
        for node in graph.nodes(data=True):
            node_attrs = node[1]
            if node_attrs["type"] == "and":
                # Convert "and" node
                puml_parts.append(
                    f"usecase \"AND{node_attrs['unique_id']}\" as {node_attrs['unique_id']}"
                )
            elif node_attrs["type"] == "entity":
                puml_parts.append(self._convert_crt_entity_node(node, parameters_dict))
            else:  # Assume note
                puml_parts.append(self._convert_crt_note_node(node, parameters_dict))

        # Convert edges
        for edge in graph.edges(data=True):
            # andに値が設定されている場合は、ANDを経由させる
            if (
                edge[2].get("and") and edge[2]["and"] != "None"
            ):  # Ensure 'and' key exists
                and_id = edge[2]["and"]
                # Ensure AND node is defined (it might have been defined above if it's also a standalone node)
                # For safety, we can add it here if not already added, or assume it's handled.
                # For simplicity, let's assume 'and' nodes are defined if they appear in edges.
                # A more robust way would be to collect all 'and' IDs first.
                if not any(
                    part.startswith(f'usecase "AND{and_id}"') for part in puml_parts
                ):
                    puml_parts.append(f'usecase "AND{and_id}" as {and_id}')

                puml_parts.append(
                    f"usecase \"AND{edge[2]['and']}\" as {edge[2]['and']}"
                )

        # Convert edges
        for edge in graph.edges(data=True):
            # andに値が設定されている場合は、ANDを経由させる
            if edge[2]["and"] != "None":
                puml_parts.append(
                    f"usecase \"AND{edge[2]['and']}\" as {edge[2]['and']}"
                )
                # edgeのdestinationをandにする
                edge_to_and = list(copy.deepcopy(edge))
                edge_to_and[1] = edge[2]["and"]
                puml_parts.append(self._convert_card_edge(edge_to_and))
                # edgeのsourceをandにする
                edge_from_and = list(copy.deepcopy(edge))
                edge_from_and[0] = edge[2]["and"]
                puml_parts.append(self._convert_card_edge(edge_from_and))
            else:
                puml_parts.append(self._convert_card_edge(edge))

        return "\n".join(puml_parts)

    def _convert_crt_entity_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        return self._create_card_puml(
            node_attrs["unique_id"], node_attrs["id"], parameters_str, color_str
        )

    def _convert_crt_note_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        # For note, parameters need modification for PlantUML syntax `note as ID color [ content *[[link]] ]`
        note_parameters_str = parameters_str[:-2] + " *]]"
        return f"""note as {node_attrs["unique_id"]} {color_str}
{node_attrs["id"]}{note_parameters_str}
end note
"""

    def _convert_process_flow_diagram(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        """Convert graph to Process Flow Diagram as PlantUML code string.

        Args:
            graph (nx.DiGraph): Graph of requirements.
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code
        """
        puml_parts = []

        # Convert all nodes
        for node in graph.nodes(data=True):
            node_attrs = node[1]
            node_type = node_attrs.get(
                "type", "card"
            )  # Default to card if type is not specified

            if node_type == "process":
                puml_parts.append(self._convert_pfd_usecase_node(node, parameters_dict))
            elif node_type == "cloud":
                puml_parts.append(self._convert_pfd_cloud_node(node, parameters_dict))
            elif node_type in ("card", "deliverable"):
                puml_parts.append(self._convert_pfd_card_node(node, parameters_dict))
            else:  # Assume other types (e.g., 'note' or unspecified) become notes
                puml_parts.append(self._convert_pfd_note_node(node, parameters_dict))
        # Convert edges
        for edge in graph.edges(data=True):
            puml_parts.append(self._convert_card_edge(edge, reverse=True))

        return "\n".join(puml_parts)

    def _convert_pfd_card_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Converts a card-like node for Process Flow Diagram."""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        return self._create_card_puml(
            node_attrs["unique_id"], node_attrs["id"], parameters_str, color_str
        )

    def _convert_pfd_note_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Converts a note-like node for Process Flow Diagram."""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        # For note, parameters need modification for PlantUML syntax
        note_parameters_str = parameters_str[:-2] + " *]]"
        return f"""note as {node_attrs["unique_id"]} {color_str}
{node_attrs["id"]}{note_parameters_str}
end note
"""

    def _convert_pfd_usecase_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Convert usecase information to PlantUML code.
        (Specifically for Process Flow Diagram)
        The original _convert_usecase method had a different signature for Requirement Diagram.

        Args:
            data (Dict[str, Any]): Usecase information

        Returns:
            str: PlantUML code
        """
        node_attrs = node[1]  # node is (unique_id, attributes_dict)
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        if node_attrs["type"] == "process":
            # Convert and node
            id_val = node_attrs["id"]
            id_val = id_val.replace("\n", "\\n")  # Escape newlines for PlantUML label
            return f"usecase \"{id_val}\" as {node_attrs['unique_id']} {parameters_str} {color_str}\n"
        return ""  # Should not happen if called correctly

    def _convert_pfd_cloud_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Convert cloud information to PlantUML code.
        (Specifically for Process Flow Diagram)

        Args:
            node (Tuple[str, Dict]): Cloud information (node_id, attributes_dict)
            id = id.replace("\n", "\\n")
            ret = f"usecase \"{id}\" as {node[1]['unique_id']} {parameters} {color}\n"
        return ret
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code
        """
        node_attrs = node[1]  # node is (unique_id, attributes_dict)
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        if node_attrs["type"] == "cloud":
            id_val = node_attrs["id"]
            id_val = id_val.replace("\n", "\\n")  # Escape newlines for PlantUML label
            return f"cloud \"{id_val}\" as {node_attrs['unique_id']} {parameters_str} {color_str}\n"
        return ""  # Should not happen if called correctly
