from typing import Dict, List, Tuple, Any
import networkx as nx
import re
import unicodedata
import hjson

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
        self.width = config["width"]
        self.left_to_right = config["left_to_right"]

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
            return self._convert_requirements_to_uml(graph, title, parameters_dict)
        elif page_title == "Strategy and Tactics Tree":
            return self._convert_strategy_and_tactics(graph, title, parameters_dict)
        elif page_title == "Current Reality Tree Viewer":
            return self._convert_current_reality(graph, title, parameters_dict)
        elif page_title == "Process Flow Diagram Viewer":
            return self._convert_process_flow(graph, title, parameters_dict)
        else:
            raise ValueError("Invalid title specified.")

    def _convert_requirements_to_uml(
        self, graph: nx.DiGraph, title: str, parameters_dict: Dict
    ) -> str:
        """Convert requirement graph to PlantUML code.
        Args:

            graph (nx.DiGraph): Graph of requirements.
            title (str): Title of diagram.
            parameters_dict (Dict): Parameters for link.
        """
        target = parameters_dict.get("target", None)
        scale = parameters_dict.get("scale", 1.0)
        if not title:
            if target == None or target == "None":
                title = '"req Requirements [all]"'
            else:
                target_title = graph.nodes(data=True)[target]["title"]
                title = f'"req {target_title} ' + 'related requirements"'
        else:
            title = f'"req {title}"'

        ret = f"""
@startuml
'!pragma layout elk
hide circle
hide empty members
hide method
skinparam linetype polyline
skinparam linetype ortho
skinparam HyperlinkUnderline false
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
        if self.left_to_right:
            ret += "left to right direction\n"

        # Add title as package
        # req Title [setting]
        ret += f"package {title} <<Frame>> " + "{\n"

        # Convert nodes other than orphan
        # for node in graph.nodes(data=True):
        #     if node[0] not in nx.isolates(graph):
        #         ret += self._convert_node(node) + "\n"

        # Convert all nodes
        for node in graph.nodes(data=True):
            ret += self._convert_node(node, parameters_dict) + "\n"

        # Convert edges
        for edge in graph.edges(data=True):
            ret += self._convert_edge(edge) + "\n"
            # if "note" in edge[2] and edge[2]["note"] != "":
            #     ret += self._convert_note_edge(edge[2]["note"], graph.nodes(data=True))

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

    def _convert_node(self, node: Tuple[str, Dict], parameters_dict: Dict) -> str:
        """Convert node information to PlantUML code.

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
            raise ValueError(f"No implement error: Unknown type specified: {type}")

        return ret

    def _convert_usecase(self, data: Dict[str, Any]) -> str:
        """Convert usecase information to PlantUML code.

        Args:
            data (Dict[str, Any]): Usecase information

        Returns:
            str: PlantUML code
        """
        # For PlantUML, the "usecase" entity cannot used on class diagram
        title = self._insert_newline(data["title"])
        if self.debug:
            ret = f"usecase \"unique_id=\"{data['unique_id']}\"\\n{self._get_title_string(data['id'], title)}\" as {data['unique_id']} <<usecase>>"
        else:
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
        title = self._insert_newline(data["title"])
        text = self._insert_newline(data["text"])
        color = color_to_archimate[data["color"]]
        if color == "None":
            color = ""

        if self.detail or self.debug:
            # Ignore () as method using {field}
            ret = (
                f"class \"{title}\" as {data['unique_id']} <<{type}>> {parameters} {color} "
                + "{\n"
            )

            if self.debug:
                ret += "{field}" + f"unique_id=\"{data['unique_id']}\"\n"
            ret += "{field}" + f"id=\"{data['id']}\"\n"
            ret += "{field}" + f'text="{text}"\n'
            ret += "}\n"
        else:
            ret = f"class \"{self._get_title_string(data['id'], title)}\" as {data['unique_id']} <<requirement>>"
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
        title = self._insert_newline(data["title"])
        if self.debug:
            ret = f"class \"unique_id=\"{data['unique_id']}\"\\n{self._get_title_string(data['id'], title)}\" as {data['unique_id']} <<{type}>> {parameters}"
        else:
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

        string = self._insert_newline(string)
        string = string.replace("\\n", "\n")
        ret = ""
        ret += f"note as {data['unique_id']}\n"
        ret += f"<<{data['type']}>>\n"
        if self.debug:
            ret += f"unique_id=\"{data['unique_id']}\"\n"
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

    def _convert_edge(self, data: Dict[str, Any]):
        """Return relationship string

        Args:
            data (Dict[str, Any]): Relationship (node)

        Returns:
            str: PlantUML string
        """
        src = data[0]
        dst = data[1]
        kind = data[2]["type"]
        note = data[2]["note"]
        ret = ""
        if kind == "containment":
            ret = f"{dst} +-- {src}"
        elif (
            kind == "refine"
            or kind == "deriveReqt"
            or kind == "satisfy"
            or kind == "verify"
            or kind == "copy"
            or kind == "trace"
        ):
            ret = f"{dst} <.. {src}: <<{kind}>>"
        elif kind == "problem" or kind == "rationale":
            # For rationale and problem (entity) only
            ret = f"{dst} .. {src}"
        else:
            raise ValueError(f"No implement exist for relation kind: {kind}")

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

                string = self._insert_newline(string)
                string = string.replace("\\n", "\n")

                ret = ""
                ret += f"note on link\n"
                ret += f"<<{node[1]['type']}>>\n"
                if self.debug:
                    ret += f'unique_id="{note_id}"\n'
                ret += f"{string}\n"
                ret += f"end note\n"
        return ret

    def _insert_newline(self, string: str) -> str:
        """Insert newline to long string to save width

        Args:
            string (str): long string

        Returns:
            str: inserted string
        """
        char_list = list(string)
        english_flag = True
        for char in char_list:
            if unicodedata.east_asian_width(char) == "W":
                # Japanese char exist
                english_flag = False
                break

        # Convert link to plantuml
        string = self._convert_link(string)
        string, stored = self._replace_link(string, "$")

        if english_flag:
            # For English text
            words = string.split(" ")
            string = ""
            temp_string = ""
            for _ in range(len(words)):
                word = words.pop(0)
                temp_string += word + " "
                if len(temp_string) > self.width:
                    string += temp_string.strip() + "\\n"
                    temp_string = ""
            string += temp_string.strip()
        else:
            # For Japanese text
            index_list = sorted(
                list(range(0, len(string), int(self.width * 0.66))), reverse=True
            )
            string_as_list = list(string)
            for index in index_list:
                if index == 0:
                    break
                else:
                    string_as_list.insert(index, "\\n")
            string = "".join(string_as_list)

        # Return unique char to link
        for link in stored:
            string = string.replace("$", link, 1)

        return string

    def _convert_link(self, string: str) -> str:
        """Convert markdown type link to PlantUML type link.

        Args:
            string (str): String possibly include link.

        Returns:
            str: Converted string
        """
        for _ in range(100):
            matched = re.findall(r".*(\[.*\]\(.*\)).*", string)
            if matched:
                target = matched[0]
                target_matched = re.findall(r"\[(.*)\]\((.*)\)", target)
                string = string.replace(
                    target, f"[[{target_matched[0][1]} {target_matched[0][0]}]]"
                )
            else:
                break
        return string

    def _replace_link(self, string: str, unique: str = "$") -> Tuple[str, List[str]]:
        """Replace PlantUML type link to unique char.

        Args:
            string (str): String possibly include link.

        Returns:
            str: Converted string
        """
        stored = []
        for _ in range(100):
            matched = re.findall(r".*(\[\[.*\]\]).*", string)
            if matched:
                target = matched[0]
                stored.append(target)
                string = string.replace(target, unique)
            else:
                break
        return string, stored

    def _convert_strategy_and_tactics(
        self, graph: nx.DiGraph, title: str, parameters_dict: Dict
    ) -> str:
        """Convert graph to strategy and tactics tree diagram as PlantUML code string.

        Args:
            graph (nx.DiGraph): Graph of requirements.
            title (str): Title of diagram.
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code
        """
        target = parameters_dict.get("target", None)
        scale = parameters_dict.get("scale", 1.0)

        ret = f"""
@startuml
skinparam linetype polyline
skinparam linetype ortho
skinparam HyperlinkUnderline false
skinparam card {{
BackgroundColor White
ArrowColor Black
BorderColor Black
FontSize 12
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
        ret = f"""card {node[1]["unique_id"]} {parameters} [
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
        if data[2]["type"] == "arrow":
            if reverse:
                ret = f"{src} --> {dst}"
            else:
                ret = f"{dst} <-- {src}"
        elif data[2]["type"] == "flat":
            ret = f"{dst} . {src}"
        elif data[2]["type"] == "flat_long":
            ret = f"{dst} .. {src}"

        return ret

    def _convert_current_reality(
        self, graph: nx.DiGraph, title: str, parameters_dict: Dict
    ) -> str:
        """Convert graph to strategy and tactics tree diagram as PlantUML code string.

        Args:
            graph (nx.DiGraph): Graph of requirements.
            title (str): Title of diagram.
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code
        """
        target = parameters_dict.get("target", None)
        scale = parameters_dict.get("scale", 1.0)

        ret = f"""
@startuml
skinparam HyperlinkUnderline false
skinparam nodesep 20
skinparam ranksep 20

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
skinparam note {{
BackgroundColor White
ArrowColor Black
BorderColor Black
FontSize 12
}}
allowmixing

scale {scale}

"""

        # Convert all nodes
        for node in graph.nodes(data=True):
            if node[1]["type"] == "and":
                # Convert and node
                ret += (
                    f"usecase \"AND{node[1]['unique_id']}\" as {node[1]['unique_id']}\n"
                )
            else:
                ret += self._convert_card_crt(node, parameters_dict) + "\n"

        # Convert edges
        for edge in graph.edges(data=True):
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

    def _convert_process_flow(
        self, graph: nx.DiGraph, title: str, parameters_dict: Dict
    ) -> str:
        """Convert graph to process_flow diagram as PlantUML code string.

        Args:
            graph (nx.DiGraph): Graph of requirements.
            title (str): Title of diagram.
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code
        """
        target = parameters_dict.get("target", None)
        scale = parameters_dict.get("scale", 1.0)

        ret = f"""
@startuml
skinparam HyperlinkUnderline false
skinparam nodesep 20
skinparam ranksep 20

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
skinparam note {{
BackgroundColor White
ArrowColor Black
BorderColor Black
FontSize 12
}}
allowmixing

scale {scale}

"""

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
            ret = f"usecase \"{node[1]['id']}\" as {node[1]['unique_id']} {parameters} {color}\n"
        return ret
