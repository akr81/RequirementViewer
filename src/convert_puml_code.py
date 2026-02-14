from typing import Dict, List, Tuple, Any
import networkx as nx
import re
import unicodedata
import hjson
import copy
from src.constants import AppName, NodeType, Color
from src.puml_templates import (
    PUML_HEADER_TEMPLATE,
    ORTHO_SETTINGS,
    SEP_SETTINGS,
    EVAPORATING_CLOUD_LAYOUT,
    CARD_TEMPLATE,
    NOTE_TEMPLATE,
    REQ_NODE_DETAIL_TEMPLATE,
    REQ_NODE_SIMPLE_TEMPLATE,
    REQ_USECASE_TEMPLATE,
    ST_CONTENT_SIMPLE,
    ST_CONTENT_DETAIL,
)


class ConvertPumlCode:
    """Convert graph to PlantUML code."""

    def _dispatch_conversion(
        self,
        node_data: Tuple[str, Dict],
        parameters_dict: Dict,
        converters: Dict,
        default_converter=None,
    ) -> str:
        """Generic dispatch for node conversion."""
        node_attrs = node_data[1]
        node_type = node_attrs.get("type", NodeType.CARD)
        converter = converters.get(node_type, default_converter)
        if converter:
            return converter(node_data, parameters_dict)
        return ""

    def _convert_note_using_field(
        self,
        node: Tuple[str, Dict],
        parameters_dict: Dict,
        field: str,
        keep_newline: bool = False,
    ) -> str:
        """Generic note converter using a specific field for content."""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        return self._create_note_puml(
            node_attrs["unique_id"],
            node_attrs.get(field, ""),
            parameters_str,
            color_str,
            apply_link_modification=True,
            keep_newline=keep_newline,
        )

    def __init__(self, config: Dict[str, Any]):
        """Initializer

        Args:
            config (Dict[str, Any]): Config settings
        """
        self.detail = config["detail"]
        self.debug = config["debug"]
        # 色マッピングの読み込み
        with open("setting/colors.json", "r", encoding="utf-8") as f:
            self._color_to_archimate = hjson.load(f)
        self.diagram_converters = {
            AppName.REQUIREMENT: self._convert_requirement_diagram,
            AppName.STRATEGY_TACTICS: self._convert_strategy_and_tactics,
            AppName.CURRENT_REALITY: self._convert_current_reality,
            AppName.PROCESS_FLOW: self._convert_process_flow_diagram,
            AppName.EVAPORATING_CLOUD: self._convert_evaporating_cloud,
        }
        self.diagram_specific_settings = {
            AppName.REQUIREMENT: {"ortho": True, "sep": 0},
            AppName.STRATEGY_TACTICS: {"ortho": True, "sep": 0},
            AppName.CURRENT_REALITY: {"ortho": False, "sep": 20},
            AppName.PROCESS_FLOW: {"ortho": False, "sep": 20},
            AppName.EVAPORATING_CLOUD: {"ortho": False, "sep": 0},
        }

        # Requirement Diagram Node Converters
        self.req_node_converters = {
            NodeType.USECASE: self._convert_req_diagram_usecase_node,
            NodeType.REQUIREMENT: self._convert_req_diagram_requirement_node,
            NodeType.FUNCTIONAL_REQUIREMENT: self._convert_req_diagram_requirement_node,
            NodeType.INTERFACE_REQUIREMENT: self._convert_req_diagram_requirement_node,
            NodeType.PERFORMANCE_REQUIREMENT: self._convert_req_diagram_requirement_node,
            NodeType.PHYSICAL_REQUIREMENT: self._convert_req_diagram_requirement_node,
            NodeType.DESIGN_CONSTRAINT: self._convert_req_diagram_requirement_node,
            NodeType.BLOCK: self._convert_req_diagram_block_node,
            NodeType.TEST_CASE: self._convert_req_diagram_block_node,
            NodeType.RATIONALE: self._convert_req_diagram_note_node,
            NodeType.PROBLEM: self._convert_req_diagram_note_node,
        }
        
        # Process Flow Diagram Node Converters
        # Process Flow Diagram Node Converters
        self.pfd_node_converters = {
            NodeType.PROCESS: lambda n, p: self._convert_pfd_element(n, p, NodeType.USECASE),
            NodeType.CLOUD: lambda n, p: self._convert_pfd_element(n, p, NodeType.CLOUD),
            NodeType.CARD: lambda n, p: self._convert_simple_card_node(n, p, "id"),
            NodeType.DELIVERABLE: lambda n, p: self._convert_simple_card_node(n, p, "id"),
            NodeType.NOTE: lambda n, p: self._convert_note_using_field(n, p, "id", keep_newline=True),
        }

        # Current Reality Tree Node Converters
        self.crt_node_converters = {
            NodeType.AND: lambda n, p: f'usecase "AND{n[1]["unique_id"]}" as {n[1]["unique_id"]}',
            NodeType.ENTITY: lambda n, p: self._convert_simple_card_node(n, p, "id"),
            NodeType.NOTE: lambda n, p: self._convert_note_using_field(n, p, "id", keep_newline=True),
        }

        # Evaporating Cloud Node Converters
        self.ec_node_converters = {
            NodeType.NOTE: lambda n, p: self._convert_note_using_field(n, p, "title", keep_newline=True),
            NodeType.CARD: lambda n, p: self._convert_simple_card_node(n, p, "title"),
        }

    def _escape_puml(self, text: str, keep_newline: bool = False) -> str:
        """Escape text for PlantUML.
        
        Args:
            text (str): Input text
            keep_newline (bool): If True, keeps newline characters as is. 
                                 If False (default), replaces newline with \\n.
        """
        if not text:
            return ""
        # PlantUMLで特別扱いされる文字をエスケープまたは置換
        # ダブルクォートをシングルクォートに置換して文字列リテラル脱出を防ぐ
        text = text.replace('"', "'")
        
        if not keep_newline:
            # 改行を \n に置換
            text = text.replace("\n", "\\n")
            
        return text

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
        ortho_str = ORTHO_SETTINGS if ortho else ""
        sep_str = SEP_SETTINGS.format(sep=sep) if sep != 0 else ""

        landscape = "left to right direction" if landscape else ""
        
        # タイトルをエスケープ
        escaped_title = self._escape_puml(diagram_title)
        diagram_title_str = (
            f"title {escaped_title}"
            if escaped_title != "" and title_flag is not False
            else ""
        )

        return PUML_HEADER_TEMPLATE.format(
            ortho_str=ortho_str,
            sep_str=sep_str,
            landscape=landscape,
            scale=scale,
            diagram_title_str=diagram_title_str,
        )

    def _get_puml_color(self, node_attributes: Dict) -> str:
        """ノード属性からPlantUML用の色指定文字列を取得する。"""
        color_name = node_attributes.get("color")
        if color_name and color_name != "None":
            # color_to_archimate に存在しないキーの場合は空文字を返す
            return self._color_to_archimate.get(color_name, "")
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
                # タイトルの一部として使われるためエスケープ
                escaped_target_title = self._escape_puml(target_title)
                title = f'"req {escaped_target_title} ' + 'related requirements"'
        else:
            # タイトル全体をエスケープ
            escaped_title = self._escape_puml(title)
            title = f'"req {escaped_title}"'

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
        keep_newline: bool = False,
    ) -> str:
        """汎用的なノート要素のPlantUML文字列を生成する。"""
        link_for_content = parameters_for_link
        if apply_link_modification:
            if link_for_content.startswith("[[?") and link_for_content.endswith("]]"):
                link_for_content = link_for_content[:-2] + " *]]"
            else:  # 安全策として、予期しない形式の場合は空のリンクにする
                link_for_content = "[[]]"

        stereotype_line = f"<<{stereotype}>>\n" if stereotype else ""
        
        # コンテンツをエスケープ
        escaped_content = self._escape_puml(content_text, keep_newline=keep_newline)
        
        body_content = stereotype_line + escaped_content
        # リンクが存在し、かつ空リンクでない場合にスペースを挟んで結合
        if link_for_content and link_for_content != "[[]]":
            body_content += " " + link_for_content

        return NOTE_TEMPLATE.format(
            unique_id=unique_id,
            color_str=color_str,
            body_content=body_content,
        )





    def _convert_evaporating_cloud(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        puml_parts = list(
            self._convert_nodes_to_puml(  # Ensure it's a list for extend
                graph,
                parameters_dict,
                lambda n, p: self._dispatch_conversion(
                    n, p, self.ec_node_converters, self.ec_node_converters["card"]
                ),
            )
        )
        puml_parts.extend(self._convert_edges_to_puml(graph, self._convert_card_edge))
        # conflict
        puml_parts.append(EVAPORATING_CLOUD_LAYOUT)

        return "\n".join(puml_parts)

    def _create_card_puml(
        self, unique_id: str, content: str, parameters_str: str, color_str: str
    ) -> str:
        """Generates the PlantUML string for a card element."""
        # contentは呼び出し元ですでに整形されている場合があるため、ここではエスケープしない
        # 呼び出し元で個別にエスケープを行う
        return CARD_TEMPLATE.format(
            unique_id=unique_id,
            parameters_str=parameters_str,
            color_str=color_str,
            content=content,
        )

    def _convert_simple_card_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict, content_field: str
    ) -> str:
        """指定されたフィールドを内容とする単純なカードノードをPUMLに変換する。"""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        
        raw_content = node_attrs.get(content_field, "")
        # コンテンツをエスケープ
        content = self._escape_puml(raw_content, keep_newline=True)
        
        return self._create_card_puml(
            node_attrs["unique_id"], content, parameters_str, color_str
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
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        node_attrs = node[1]
        node_type = node_attrs["type"]
        
        converter = self.req_node_converters.get(node_type)
        if converter:
            return converter(
                node_attrs, node_type, parameters_str, detail=parameters_dict.get("detail", True)
            )
        else:
             raise ValueError(
                f"Requirement Diagram: No convert rule defined for type: {node_type}"
            )

    def _convert_req_diagram_usecase_node(
        self,
        data: Dict[str, Any],
        node_type: str,
        parameters_str: str,
        detail: bool = True,
    ) -> str:
        """Convert usecase node for Requirement Diagram to PlantUML code.

        Args:
            data (Dict[str, Any]): Usecase node attributes.
            parameters_str (str): Parameter string for link.

        Returns:
            str: PlantUML code
        """
        # For PlantUML, the "usecase" entity cannot used on class diagram
        title = data["title"]
        # タイトルをエスケープ
        escaped_title = self._escape_puml(title)
        
        # ID+タイトル文字列の生成もエスケープ済みタイトルを使用するよう _get_title_string を調整するか、
        # ここで組み立てる
        full_title = self._get_title_string(data['id'], escaped_title)
        
        color_str = self._get_puml_color(data)
        return REQ_USECASE_TEMPLATE.format(
            full_title=full_title,
            unique_id=data['unique_id'],
            parameters=parameters_str,
            color_str=color_str,
        )

    def _convert_req_diagram_requirement_node(
        self, data: Dict[str, Any], node_type: str, parameters_str: str, detail: bool = True
    ) -> str:
        """Convert requirement node for Requirement Diagram to PlantUML code.

        Args:
            data (Dict[str, Any]): Requirement information
            node_type (str): Type of requirement
            parameters_str (str): Parameter string for link

        Returns:
            str: PlantUML code
        """
        title = data["title"]
        text = data["text"]
        
        # エスケープ
        escaped_title = self._escape_puml(title)
        escaped_text = self._escape_puml(text)
        
        color_str = self._get_puml_color(data)

        # Ignore () as method using {field}
        if detail:
            puml_code = REQ_NODE_DETAIL_TEMPLATE.format(
                title=escaped_title,
                unique_id=data['unique_id'],
                type=node_type,
                parameters=parameters_str,
                color_str=color_str,
                field="{field}",
                id=data['id'],
                text=escaped_text,
            )
        else:
            puml_code = REQ_NODE_SIMPLE_TEMPLATE.format(
                title=escaped_title,
                unique_id=data['unique_id'],
                type=node_type,
                parameters=parameters_str,
                color_str=color_str,
            )
        return puml_code

    def _convert_req_diagram_block_node(
        self,
        data: Dict[str, Any],
        node_type: str,
        parameters_str: str,
        detail: bool = True,
    ) -> str:
        """Convert block/testCase node for Requirement Diagram to PlantUML code.

        Args:
            data (Dict[str, Any]): Block information
            node_type (str): Type information
            parameters_str (str): Parameter string for link

        Returns:
            str: PlantUML code
        """
        title = data["title"]
        escaped_title = self._escape_puml(title)
        full_title = self._get_title_string(data['id'], escaped_title)
        
        color_str = self._get_puml_color(data)
        return f"class \"{full_title}\" as {data['unique_id']} <<{node_type}>> {parameters_str} {color_str}"

    def _convert_req_diagram_note_node(
        self,
        data: Dict[str, Any],
        node_type: str,
        parameters_str: str,
        detail: bool = True,
    ) -> str:
        """Convert rationale/problem (note-like) node for Requirement Diagram to PlantUML code.

        Args:
            data (Dict[str, Any]): Node attributes for rationale or problem.
            parameters_str (str): Parameter string for link.


        Returns:
            str: PlantUML string for note
        """
        # Display longer string from title and text
        if len(data["title"]) >= len(data["text"]):
            display_text = data["title"]
        else:
            display_text = data["text"]

        color_str = self._get_puml_color(data)
        # Requirement Diagramのノートはリンク形式の変更が不要
        # リンクはノートのコンテンツの末尾に配置されるように変更
        # コンテンツのエスケープは _create_note_puml 内で行われる
        return self._create_note_puml(
            data["unique_id"],
            display_text,  # content_text
            parameters_str,  # parameters_for_link
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
        # titleは呼び出し元ですでにエスケープされていることを想定
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

        # テキストをエスケープ
        escaped_text = self._escape_puml(note_data['text'])

        note_puml = "\nnote on link\n"
        if note_data.get("type") and note_data["type"] != "None":
            note_puml += f"<<{note_data['type']}>>\n"
        note_puml += f"{escaped_text}\n"
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
        # label_textはテンプレートから生成される固定文字列(<<type>>)が多いため、
        # ここではエスケープ対象としないが、動的な内容が含まれる場合は注意が必要。
        # 今回の要件図の仕様では label_text は固定フォーマットのみ。
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
        relation_type = data[2]["type"]
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

        config = edge_configs.get(relation_type)
        if not config:
            raise ValueError(f"No implement exist for relation type: {relation_type}")

        puml_node1, puml_node2, puml_line_style, label_template = config
        label_text = label_template.format(type=relation_type) if label_template else ""
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
        # コンテンツをエスケープ
        node_id = node_attrs.get("id", "")
        necessary_assumption = self._escape_puml(node_attrs.get("necessary_assumption", ""), keep_newline=True)
        strategy = self._escape_puml(node_attrs.get("strategy", ""), keep_newline=True)
        parallel_assumption = self._escape_puml(node_attrs.get("parallel_assumption", ""), keep_newline=True)
        tactics = self._escape_puml(node_attrs.get("tactics", ""), keep_newline=True)
        sufficient_assumption = self._escape_puml(node_attrs.get("sufficient_assumption", ""), keep_newline=True)
        
        if not detail:
            content = ST_CONTENT_SIMPLE.format(
                node_id=node_id,
                strategy=strategy,
                tactics=tactics,
            )
        else:
            content = ST_CONTENT_DETAIL.format(
                node_id=node_id,
                necessary_assumption=necessary_assumption,
                strategy=strategy,
                parallel_assumption=parallel_assumption,
                tactics=tactics,
                sufficient_assumption=sufficient_assumption,
            )
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
        # コメントをエスケープ
        escaped_comment = self._escape_puml(comment_text)

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
            puml_node1, puml_node2, line_style, escaped_comment
        )



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
                graph,
                parameters_dict,
                lambda n, p: self._dispatch_conversion(
                    n, p, self.crt_node_converters, self.crt_node_converters["note"]
                ),
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
                graph,
                parameters_dict,
                lambda n, p: self._dispatch_conversion(
                    n, p, self.pfd_node_converters, self.pfd_node_converters["note"]
                ),
            )
        )
        puml_parts.extend(
            self._convert_edges_to_puml(
                graph, self._convert_card_edge, use_src_arrow_dst_style=True
            )
        )

        return "\n".join(puml_parts)





    def _convert_pfd_element(
        self, node: Tuple[str, Dict], parameters_dict: Dict, puml_type: str
    ) -> str:
        """Convert generic element (usecase, cloud) for PFD."""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        
        id_val = node_attrs.get("id", "")
        # エスケープ処理 (改行は保持して \n に変換)
        escaped_id_val = self._escape_puml(id_val, keep_newline=True)
        
        return f'{puml_type} "{escaped_id_val}" as {node_attrs["unique_id"]} {parameters_str} {color_str}\n'

    def _get_puml_color(self, node_attrs: Dict) -> str:
        color_key = node_attrs.get("color", Color.NONE)
        if color_key == Color.NONE or color_key is None:
            return ""
        # アーキメイト色の変換
        return self._color_to_archimate.get(color_key, f"#{color_key}")

    def _escape_puml(self, text: str, keep_newline: bool = False) -> str:
        if not text:
            return ""
        # ダブルクォートをエスケープ
        escaped = text.replace('"', '\\"')
        if keep_newline:
            # 改行をPlantUMLの改行コードに置換
            escaped = escaped.replace('\n', '\\n')
        else:
             # 通常も改行は \n に置換するのが安全
             escaped = escaped.replace('\n', '\\n')
        return escaped


