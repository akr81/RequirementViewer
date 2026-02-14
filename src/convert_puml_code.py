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
        self,
        page_title: str,
        graph: nx.DiGraph,
        title: str,
        parameters_dict: Dict,
        diagram_title: str = "",
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
        title_flag = parameters_dict.get("title", False)

        puml_parts = [
            self._add_common_parameter_setting(
                scale,
                ortho,
                sep,
                landscape=landscape,
                title_flag=title_flag,
                diagram_title=diagram_title,
            )
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
        self,
        scale: float,
        ortho: bool = True,
        sep: int = 0,
        *,
        landscape: bool = False,
        title_flag: bool = False,
        diagram_title: str = "",
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
        diagram_title = (
            f"title {diagram_title}"
            if diagram_title != "" and title_flag is not False
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
FontSize 12
}}
skinparam cloud {{
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
{diagram_title}
"""

    def _get_puml_color(self, node_attributes: Dict) -> str:
        """ノード属性からPlantUML用の色指定文字列を取得する。"""
        color_name = node_attributes.get("color")
        if color_name and color_name != "None":
            # color_to_archimate に存在しないキーの場合は空文字を返す
            return color_to_archimate.get(color_name, "")
        return ""

    def _convert_nodes_to_puml(
        self, graph: nx.DiGraph, parameters_dict: Dict, node_converter_method
    ) -> List[str]:
        """Helper to convert all nodes in a graph to PUML strings using a specific node converter."""
        puml_node_parts = []
        for node_data_tuple in graph.nodes(data=True):
            puml_node_parts.append(
                node_converter_method(node_data_tuple, parameters_dict)
            )
        return puml_node_parts

    def _convert_edges_to_puml(
        self, graph: nx.DiGraph, edge_converter_method, **kwargs
    ) -> List[str]:
        """Helper to convert all edges in a graph to PUML strings using a specific edge converter."""
        puml_edge_parts = []
        for edge_data_tuple in graph.edges(data=True):
            puml_edge_parts.append(edge_converter_method(edge_data_tuple, **kwargs))
        return puml_edge_parts

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
        puml_parts.extend(
            self._convert_nodes_to_puml(
                graph, parameters_dict, self._convert_requirement_node
            )
        )
        # Convert edges
        puml_parts.extend(
            self._convert_edges_to_puml(graph, self._convert_requirement_edge)
        )
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

        return f"[[?{'&'.join(query_items)}]]"

    def _create_note_puml(
        self,
        unique_id: str,
        content_text: str,
        parameters_for_link: str,
        color_str: str,
        stereotype: str = None,
        apply_link_modification: bool = False,
    ) -> str:
        """汎用的なノート要素のPlantUML文字列を生成する。"""
        link_for_content = parameters_for_link
        if apply_link_modification:
            if link_for_content.startswith("[[?") and link_for_content.endswith("]]"):
                link_for_content = link_for_content[:-2] + " *]]"
            else:  # 安全策として、予期しない形式の場合は空のリンクにする
                link_for_content = "[[]]"

        stereotype_line = f"<<{stereotype}>>\n" if stereotype else ""

        body_content = stereotype_line + content_text
        # リンクが存在し、かつ空リンクでない場合にスペースを挟んで結合
        if link_for_content and link_for_content != "[[]]":
            body_content += " " + link_for_content

        return f"""note as {unique_id} {color_str}
{body_content}
end note"""

    def _convert_evaporating_cloud_note(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        return self._create_note_puml(
            node_attrs["unique_id"],
            node_attrs["title"],
            parameters_str,
            color_str,
            apply_link_modification=True,
        )

    def _dispatch_evaporating_cloud_node_conversion(
        self, node_data_tuple: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Dispatches node conversion for Evaporating Cloud based on node type."""
        node_attrs = node_data_tuple[1]
        if node_attrs["type"] == "note":
            return self._convert_evaporating_cloud_note(
                node_data_tuple, parameters_dict
            )
        else:  # Assumes card or other types are card-like
            return self._convert_evaporating_cloud_card_node(
                node_data_tuple, parameters_dict
            )

    def _convert_evaporating_cloud(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        puml_parts = list(
            self._convert_nodes_to_puml(  # Ensure it's a list for extend
                graph, parameters_dict, self._dispatch_evaporating_cloud_node_conversion
            )
        )
        puml_parts.extend(self._convert_edges_to_puml(graph, self._convert_card_edge))
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

    def _convert_simple_card_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict, content_field: str
    ) -> str:
        """指定されたフィールドを内容とする単純なカードノードをPUMLに変換する。"""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        content = node_attrs.get(
            content_field, ""
        )  # content_field が存在しない場合も考慮
        return self._create_card_puml(
            node_attrs["unique_id"], content, parameters_str, color_str
        )

    def _convert_evaporating_cloud_card_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        return self._convert_simple_card_node(
            node, parameters_dict, content_field="title"
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
        if type == "usecase":  # Requirement Diagram specific usecase
            ret = self._convert_req_diagram_usecase_node(attr, parameters)
        elif (  # Requirement Diagram specific requirement types
            type == "requirement"
            or type == "functionalRequirement"
            or type == "interfaceRequirement"
            or type == "performanceRequirement"
            or type == "physicalRequirement"
            or type == "designConstraint"
        ):
            ret = self._convert_req_diagram_requirement_node(
                attr, type, parameters, parameters_dict.get("detail", True)
            )
        elif (
            type == "block" or type == "testCase"
        ):  # Requirement Diagram specific block/testCase
            ret = self._convert_req_diagram_block_node(attr, type, parameters)
        elif (
            type == "rationale" or type == "problem"
        ):  # Requirement Diagram specific note-like entities
            ret = self._convert_req_diagram_note_node(attr, parameters)
        else:
            raise ValueError(
                f"Requirement Diagram: No convert rule defined for type: {type}"
            )

        return ret

    def _convert_req_diagram_usecase_node(
        self, data: Dict[str, Any], parameters: str
    ) -> str:
        """Convert usecase node for Requirement Diagram to PlantUML code.

        Args:
            data (Dict[str, Any]): Usecase node attributes.
            parameters (str): Parameter string for link.

        Returns:
            str: PlantUML code
        """
        # For PlantUML, the "usecase" entity cannot used on class diagram
        title = data["title"]
        color_str = self._get_puml_color(data)
        return f"usecase \"{self._get_title_string(data['id'], title)}\" as {data['unique_id']} <<usecase>> {parameters} {color_str}"

    def _convert_req_diagram_requirement_node(
        self, data: Dict[str, Any], type: str, parameters: str, detail: bool = True
    ) -> str:
        """Convert requirement node for Requirement Diagram to PlantUML code.

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
        if detail:
            ret = (
                f"class \"{title}\" as {data['unique_id']} <<{type}>> {parameters} {color_str} "
                + "{\n"
            )

            ret += "{field}" + f"id=\"{data['id']}\"\n"
            ret += "{field}" + f'text="{text}"\n'
            ret += "}\n"
        else:
            ret = f"class \"{title}\" as {data['unique_id']} <<{type}>> {parameters} {color_str} "
        return ret

    def _convert_req_diagram_block_node(
        self, data: Dict[str, Any], type: str, parameters: str
    ) -> str:
        """Convert block/testCase node for Requirement Diagram to PlantUML code.

        Args:
            data (Dict[str, Any]): Block information
            type (str): Type information
            parameters (str): Parameter string for link

        Returns:
            str: PlantUML code
        """
        title = data["title"]
        color_str = self._get_puml_color(data)
        return f"class \"{self._get_title_string(data['id'], title)}\" as {data['unique_id']} <<{type}>> {parameters} {color_str}"

    def _convert_req_diagram_note_node(
        self, data: Dict[str, Any], parameters: str
    ) -> str:
        """Convert rationale/problem (note-like) node for Requirement Diagram to PlantUML code.

        Args:
            data (Dict[str, Any]): Node attributes for rationale or problem.
            parameters (str): Parameter string for link.


        Returns:
            str: PlantUML string for note
        """
        # Display longer string from title and text
        if len(data["title"]) >= len(data["text"]):
            string = data["title"]
        else:
            string = data["text"]

        color_str = self._get_puml_color(data)
        # Requirement Diagramのノートはリンク形式の変更が不要
        # リンクはノートのコンテンツの末尾に配置されるように変更
        return self._create_note_puml(
            data["unique_id"],
            string,  # content_text
            parameters,  # parameters_for_link
            color_str,
            stereotype=data["type"],
            apply_link_modification=False,  # 通常のリンク形式を使用
        )

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

    def _create_note_on_link_puml(self, note_data: Dict[str, Any]) -> str:
        """Creates PlantUML string for a 'note on link'.

        Args:
            note_data (Dict[str, Any]): Dictionary containing note information (type, text).

        Returns:
            str: PlantUML string for the note on link, or empty string if no text.
        """
        if not note_data or not note_data.get("text"):
            return ""

        note_puml = "\nnote on link\n"
        if note_data.get("type") and note_data["type"] != "None":
            note_puml += f"<<{note_data['type']}>>\n"
        note_puml += f"{note_data['text']}\n"
        note_puml += "end note\n"
        return note_puml

    def _create_generic_edge_puml(
        self,
        puml_node1: str,
        puml_node2: str,
        line_style: str,
        label_text: str = "",
        note_on_link_puml: str = "",
    ) -> str:
        """Generates a generic PlantUML string for an edge."""
        label_part = f" : {label_text}" if label_text else ""
        return f"{puml_node1} {line_style} {puml_node2}{label_part}{note_on_link_puml}"

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
        edge_attrs = data[2]
        note_data = edge_attrs.get("note")

        # (puml_node1, puml_node2, puml_line_style, label_content_template)
        edge_configs = {
            "containment": (dst, src, "+--", ""),
            "refine": (dst, src, "<..", "<<{type}>>"),
            "deriveReqt": (dst, src, "<..", "<<{type}>>"),
            "satisfy": (dst, src, "<..", "<<{type}>>"),
            "verify": (dst, src, "<..", "<<{type}>>"),
            "copy": (dst, src, "<..", "<<{type}>>"),
            "trace": (dst, src, "<..", "<<{type}>>"),
            "problem": (dst, src, "..", ""),
            "rationale": (dst, src, "..", ""),
        }

        config = edge_configs.get(type)
        if not config:
            raise ValueError(f"No implement exist for relation type: {type}")

        puml_node1, puml_node2, puml_line_style, label_template = config
        label_text = label_template.format(type=type) if label_template else ""
        note_puml = self._create_note_on_link_puml(note_data) if note_data else ""

        return self._create_generic_edge_puml(
            puml_node1, puml_node2, puml_line_style, label_text, note_puml
        )

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
        puml_parts.extend(
            self._convert_nodes_to_puml(
                graph, parameters_dict, self._convert_st_card_node
            )
        )
        # Convert edges
        puml_parts.extend(self._convert_edges_to_puml(graph, self._convert_card_edge))
        return "\n".join(puml_parts)

    def _convert_st_card_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Converts a node for Strategy and Tactics Tree into a card."""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)

        # Determine if detail mode is enabled
        detail = parameters_dict.get("detail", False)

        # Ensure all expected keys exist, providing defaults if necessary
        node_id = node_attrs.get("id", "")
        necessary_assumption = node_attrs.get("necessary_assumption", "")
        strategy = node_attrs.get("strategy", "")
        parallel_assumption = node_attrs.get("parallel_assumption", "")
        tactics = node_attrs.get("tactics", "")
        sufficient_assumption = node_attrs.get("sufficient_assumption", "")
        if not detail:
            content = f"""{node_id}
---
{strategy}
---
{tactics}"""
        else:
            content = f"""{node_id}
---
{necessary_assumption}
---
{strategy}
---
{parallel_assumption}
---
{tactics}
---
{sufficient_assumption}"""
        return self._create_card_puml(
            node_attrs["unique_id"], content, parameters_str, color_str
        )

    def _convert_card_edge(
        self, data: Dict[str, Any], use_src_arrow_dst_style: bool = False
    ):
        """
        Converts a card edge to PlantUML.
        Args:
            data: Edge data (tuple: (src_id, dst_id, attributes_dict)).
            use_src_arrow_dst_style:
                If True, arrow type defaults to "src --> dst" (e.g., PFD).
                If False (default), arrow type defaults to "dst <-- src" (e.g., S&T, EC, CRT).
        Returns:
            PlantUML string for the edge.
        """
        src_id = data[0]
        dst_id = data[1]
        edge_attrs = data[2]

        edge_type = edge_attrs.get("type", "arrow")  # Default to arrow if not specified
        comment_text = edge_attrs.get("comment", "")

        # Determine node order based on style
        puml_node1, puml_node2 = (
            (src_id, dst_id) if use_src_arrow_dst_style else (dst_id, src_id)
        )

        # Determine line style based on edge_type and style
        if edge_type == "arrow":
            line_style = "-->" if use_src_arrow_dst_style else "<--"
        elif edge_type == "flat":
            line_style = "."
        elif edge_type == "flat_long":
            line_style = ".."
        else:
            raise ValueError(f"Unknown card edge type: {edge_type}")

        return self._create_generic_edge_puml(
            puml_node1, puml_node2, line_style, comment_text
        )

    def _dispatch_crt_node_conversion(
        self, node_data_tuple: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Dispatches node conversion for Current Reality Tree based on node type."""
        node_attrs = node_data_tuple[1]
        if node_attrs["type"] == "and":
            # Convert "and" node
            return (
                f"usecase \"AND{node_attrs['unique_id']}\" as {node_attrs['unique_id']}"
            )
        elif node_attrs["type"] == "entity":
            return self._convert_crt_entity_node(node_data_tuple, parameters_dict)
        else:  # Assume note
            return self._convert_crt_note_node(node_data_tuple, parameters_dict)

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
        puml_parts = list(
            self._convert_nodes_to_puml(  # Ensure it's a list for extend
                graph, parameters_dict, self._dispatch_crt_node_conversion
            )
        )

        # Convert edges for Current Reality Tree
        seen_and_nodes = set()
        seen_edges_from_and = set()

        for edge_data_tuple in graph.edges(data=True):
            src_node_id = edge_data_tuple[0]
            dst_node_id = edge_data_tuple[1]
            edge_attributes = edge_data_tuple[2]

            and_node_id = edge_attributes.get("and")

            if and_node_id and and_node_id != "None":
                # ANDノードを経由するエッジ: src -> AND -> dst
                
                # ANDノードをここで追加 (重複回避)
                if and_node_id not in seen_and_nodes:
                    puml_parts.append(f'usecase "AND{and_node_id}" as {and_node_id}')
                    seen_and_nodes.add(and_node_id)

                # src -> AND エッジ (これは常にユニークはず)
                attrs_to_and = copy.deepcopy(edge_attributes)
                attrs_to_and.pop("and", None)  # このエッジ自体はANDを経由しない
                edge_to_and_representation = (src_node_id, and_node_id, attrs_to_and)
                puml_parts.append(self._convert_card_edge(edge_to_and_representation))

                # AND -> dst エッジ (重複回避)
                # ANDノードと宛先が同じなら、既に生成されている可能性がある
                edge_key = (and_node_id, dst_node_id)
                if edge_key not in seen_edges_from_and:
                    attrs_from_and = copy.deepcopy(edge_attributes)
                    attrs_from_and.pop("and", None)
                    edge_from_and_representation = (
                        and_node_id,
                        dst_node_id,
                        attrs_from_and,
                    )
                    puml_parts.append(self._convert_card_edge(edge_from_and_representation))
                    seen_edges_from_and.add(edge_key)
            else:
                # 通常のエッジ
                puml_parts.append(self._convert_card_edge(edge_data_tuple))

        return "\n".join(puml_parts)

    def _convert_crt_entity_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        return self._convert_simple_card_node(node, parameters_dict, content_field="id")

    def _convert_crt_note_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        return self._create_note_puml(
            node_attrs["unique_id"],
            node_attrs["id"],  # content_text
            parameters_str,  # parameters_for_link
            color_str,
            apply_link_modification=True,
        )

    def _dispatch_pfd_node_conversion(
        self, node_data_tuple: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Dispatches node conversion for Process Flow Diagram based on node type."""
        node_attrs = node_data_tuple[1]
        node_type = node_attrs.get(
            "type", "card"
        )  # Default to card if type is not specified

        if node_type == "process":
            return self._convert_pfd_usecase_node(node_data_tuple, parameters_dict)
        elif node_type == "cloud":
            return self._convert_pfd_cloud_node(node_data_tuple, parameters_dict)
        elif node_type in ("card", "deliverable"):
            return self._convert_pfd_card_node(node_data_tuple, parameters_dict)
        else:  # Assume other types (e.g., 'note' or unspecified) become notes
            return self._convert_pfd_note_node(node_data_tuple, parameters_dict)

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
        puml_parts = list(
            self._convert_nodes_to_puml(  # Ensure it's a list for extend
                graph, parameters_dict, self._dispatch_pfd_node_conversion
            )
        )
        puml_parts.extend(
            self._convert_edges_to_puml(
                graph, self._convert_card_edge, use_src_arrow_dst_style=True
            )
        )

        return "\n".join(puml_parts)

    def _convert_pfd_card_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        return self._convert_simple_card_node(node, parameters_dict, content_field="id")

    def _convert_pfd_note_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        return self._create_note_puml(
            node_attrs["unique_id"],
            node_attrs["id"],  # content_text
            parameters_str,  # parameters_for_link
            color_str,
            apply_link_modification=True,
        )

    def _convert_pfd_usecase_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """Convert usecase information to PlantUML code.
        (Specifically for Process Flow Diagram)
        The original _convert_usecase method had a different signature for Requirement Diagram.

        Args:
            node (Tuple[str, Dict]): Usecase information (node_id, attributes_dict).
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code.
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
            parameters_dict (Dict): Parameters for link.

        Returns:
            str: PlantUML code.
        """
        node_attrs = node[1]  # node is (unique_id, attributes_dict)
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        if node_attrs["type"] == "cloud":
            id_val = node_attrs["id"]
            id_val = id_val.replace("\n", "\\n")  # Escape newlines for PlantUML label
            return f"cloud \"{id_val}\" as {node_attrs['unique_id']} {parameters_str} {color_str}\n"
        return ""  # Should not happen if called correctly
