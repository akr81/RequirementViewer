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
        if page_title == "Requirement Diagram Viewer":
            return self._convert_requirement_diagram(graph, title, parameters_dict)
        elif page_title == "Strategy and Tactics Tree Viewer":
            return self._convert_strategy_and_tactics(graph, title, parameters_dict)
        elif page_title == "Current Reality Tree Viewer":
            return self._convert_current_reality(graph, title, parameters_dict)
        elif page_title == "Process Flow Diagram Viewer":
            return self._convert_process_flow_diagram(graph, title, parameters_dict)
        elif page_title == "Evaporating Cloud Viewer":
            return self._convert_evaporating_cloud(graph, title, parameters_dict)
        else:
            raise ValueError("Invalid title specified.")

    def _add_common_parameter_setting(
        self, scale: float, ortho: bool = True, sep: int = 0
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

        return f"""
@startuml
'!pragma layout elk
hide circle
hide empty members
hide method
{ortho_str}
{sep_str}
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
skinparam usecase {{
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

        # Add common parameter setting
        scale = parameters_dict.get("scale", 1.0)
        ret = self._add_common_parameter_setting(scale)

        # Add title as package
        ret += f"package {title} <<Frame>> " + "{\n"

        # Convert all nodes
        for node in graph.nodes(data=True):
            ret += self._convert_requirement_node(node, parameters_dict) + "\n"

        # Convert edges
        for edge in graph.edges(data=True):
            ret += self._convert_requirement_edge(edge) + "\n"

        ret += "\n}\n@enduml\n"
        return ret

    def _convert_parameters_dict(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Convert parameters dict to PlantUML code.

        Args:
            node (Tuple[str, Dict]): Node information.
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code.
        """
        is_first = True
        ret = "[["
        for key, value in parameters_dict.items():
            if is_first:
                ret += f"?{key}={value}"
                is_first = False
            else:
                ret += f"&{key}={value}"
        ret += f"&selected={node[1]['unique_id']}]]"
        return ret

    def _convert_evaporating_cloud_note(self, node, parameters_dict):
        # Get parameters string and modify for note
        parameters = self._convert_parameters_dict(node, parameters_dict)
        parameters = parameters[:-2] + " *]]"

        # Get color string
        if node[1]["color"] != "None":
            color = color_to_archimate[node[1]["color"]]
        else:
            color = ""

        return f"""
note as {node[1]['unique_id']} {color}
{node[1]['title']} {parameters}
end note
"""

    def _convert_evaporating_cloud(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        scale = parameters_dict.get("scale", 1.0)

        ret = self._add_common_parameter_setting(scale, ortho=False)

        # Convert all nodes
        for node in graph.nodes(data=True):
            if node[1]["type"] == "note":
                ret += (
                    self._convert_evaporating_cloud_note(node, parameters_dict) + "\n"
                )
            else:
                ret += (
                    self._convert_evaporating_cloud_card(node, parameters_dict) + "\n"
                )

        # Convert edges
        for edge in graph.edges(data=True):
            ret += self._convert_card_edge(edge) + "\n"

        # conflict
        ret += """
left_hand <=> right_hand #red
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
right_shoulder_to_head .. right_shoulder
"""

        ret += "\n}\n@enduml\n"
        return ret

    def _convert_evaporating_cloud_card(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        parameters = self._convert_parameters_dict(node, parameters_dict)
        if node[1]["color"] != "None":
            color = color_to_archimate[node[1]["color"]]
        else:
            color = ""
        ret = f"""card {node[1]["unique_id"]} {parameters} {color} [
{node[1]["title"]}
]
"""
        return ret

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
        color = color_to_archimate[data["color"]]
        if color == "None":
            color = ""

        # Ignore () as method using {field}
        ret = (
            f"class \"{title}\" as {data['unique_id']} <<{type}>> {parameters} {color} "
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
        scale = parameters_dict.get("scale", 1.0)

        ret = self._add_common_parameter_setting(scale)

        # Convert all nodes
        for node in graph.nodes(data=True):
            ret += self._convert_card(node, parameters_dict) + "\n"

        # Convert edges
        for edge in graph.edges(data=True):
            ret += self._convert_card_edge(edge) + "\n"

        ret += "\n}\n@enduml\n"
        return ret

    def _convert_card(self, node: Tuple[str, Dict], parameters_dict: Dict) -> str:
        parameters = self._convert_parameters_dict(node, parameters_dict)
        if node[1]["color"] != "None":
            color = color_to_archimate[node[1]["color"]]
        else:
            color = ""
        ret = f"""card {node[1]["unique_id"]} {parameters} {color} [
{node[1]["id"]}
---
{node[1]["strategy"]}
---
{node[1]["tactics"]}
]
"""
        return ret

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
        scale = parameters_dict.get("scale", 1.0)

        ret = self._add_common_parameter_setting(scale, ortho=False, sep=20)

        # Convert all nodes
        for node in graph.nodes(data=True):
            if "color" not in node[1]:
                node[1]["color"] = "None"
            parameters = self._convert_parameters_dict(node, parameters_dict)
            if node[1]["color"] != "None":
                color = color_to_archimate[node[1]["color"]]
            else:
                color = ""
            if node[1]["type"] == "and":
                # Convert "and" node
                ret += (
                    f"usecase \"AND{node[1]['unique_id']}\" as {node[1]['unique_id']}\n"
                )
            elif node[1]["type"] == "entity":
                ret += f"""card {node[1]["unique_id"]} {parameters} {color} [
{node[1]["id"]}
]
"""
            else:
                parameters = parameters[:-2] + " *]]"
                ret += f"""note as {node[1]["unique_id"]} {color}
{node[1]["id"]}{parameters}
end note
"""

        # Convert edges
        for edge in graph.edges(data=True):
            # andに値が設定されている場合は、ANDを経由させる
            if edge[2]["and"] != "None":
                ret += f"usecase \"AND{edge[2]['and']}\" as {edge[2]['and']}\n"
                # edgeのdestinationをandにする
                edge_to_and = list(copy.deepcopy(edge))
                edge_to_and[1] = edge[2]["and"]
                ret += self._convert_card_edge(edge_to_and) + "\n"
                # edgeのsourceをandにする
                edge_from_and = list(copy.deepcopy(edge))
                edge_from_and[0] = edge[2]["and"]
                ret += self._convert_card_edge(edge_from_and) + "\n"
            else:
                ret += self._convert_card_edge(edge) + "\n"

        ret += "\n}\n@enduml\n"
        return ret

    def _convert_card_crt(self, node: Tuple[str, Dict], parameters_dict: Dict) -> str:
        parameters = self._convert_parameters_dict(node, parameters_dict)
        if node[1]["color"] != "None":
            color = color_to_archimate[node[1]["color"]]
        else:
            color = ""

        if (
            "type" not in node[1]
            or node[1]["type"] == "card"
            or node[1]["type"] == "deliverable"
        ):
            ret = f"""card {node[1]["unique_id"]} {parameters} {color} [
{node[1]["id"]}
]
"""
        else:
            parameters = parameters[:-2] + " *]]"
            ret = f"""note as {node[1]["unique_id"]} {color}
{node[1]["id"]}{parameters}
end note
"""

        return ret

    def _convert_process_flow_diagram(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        """Convert graph to process_flow diagram as PlantUML code string.

        Args:
            graph (nx.DiGraph): Graph of requirements.
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code
        """
        scale = parameters_dict.get("scale", 1.0)

        ret = self._add_common_parameter_setting(scale, ortho=False, sep=20)

        # Convert all nodes
        for node in graph.nodes(data=True):
            if node[1]["type"] == "process":
                ret += self._convert_usecase(node, parameters_dict) + "\n"
            else:
                ret += self._convert_card_crt(node, parameters_dict) + "\n"

        # Convert edges
        for edge in graph.edges(data=True):
            ret += self._convert_card_edge(edge, reverse=True) + "\n"

        ret += "\n}\n@enduml\n"
        return ret

    def _convert_usecase(self, node: Dict[str, Any], parameters_dict: Dict) -> str:
        """Convert usecase information to PlantUML code.

        Args:
            data (Dict[str, Any]): Usecase information

        Returns:
            str: PlantUML code
        """
        parameters = self._convert_parameters_dict(node, parameters_dict)
        if node[1]["color"] != "None":
            color = color_to_archimate[node[1]["color"]]
        else:
            color = ""
        if node[1]["type"] == "process":
            # Convert and node
            id = node[1]["id"]
            id = id.replace("\n", "\\n")
            ret = f"usecase \"{id}\" as {node[1]['unique_id']} {parameters} {color}\n"
        return ret
