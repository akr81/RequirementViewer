import base64
from typing import Dict, List, Tuple, Any

# Base64エンコードされたチェックマーク画像 (16x16)
CHECKBOX_IMG_PUML = "<img:data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAiUlEQVR4nGNgoBAwInNEG2z/E6vxdcNhsF4WZM28roqkWP4fZAgjmZrB4PPu+wxMpGi4a7UQQ4yJVM3ohjAxkAiUj8WTbsBdLE7Ha8BdJA3IbHTbUaKRkF+xacbqAmUsCnFpxmoAIQ3ogAmXBMwQQobhjQViXAI2AJSmQcmSFABSD88LMEBObgQATcY1I+vCAPQAAAAASUVORK5CYII=>"
# オレンジ色の走る人画像 (16x16)
RUNNING_IMG_PUML = "<img:data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAASElEQVR4nGNgGBLgfw/DfxDGJsdEjGZsbKINGHgvEAKM+CSRbWUsYWCE8UFsBkoDjyTwH48BTAy0Bv+httMsFhiIsR0Xf3AAABkIJw4Wy34oAAAAAElFTkSuQmCC>"
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
    """グラフデータをPlantUMLコードに変換するクラス。"""

    def _dispatch_conversion(
        self,
        node_data: Tuple[str, Dict],
        parameters_dict: Dict,
        converters: Dict,
        default_converter=None,
    ) -> str:
        """ノード変換用の汎用ディスパッチャ。"""
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
        """コンテンツとして特定フィールドを使用する汎用のNoteコンバータ。"""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        # 指定フィールドが空の場合は title → id の順にフォールバック（旧データ互換）
        raw_content = node_attrs.get(field, "") or node_attrs.get("title", "") or node_attrs.get("id", "")
        content = self._escape_puml(raw_content, keep_newline=True)

        return self._create_note_puml(
            node_attrs["unique_id"],
            content,
            parameters_str,
            color_str,
            apply_link_modification=True,
            keep_newline=True,
        )

    def __init__(self, config: Dict[str, Any]):
        """初期化。

        Args:
            config (Dict[str, Any]): 設定データ
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
            AppName.CCPM: self._convert_ccpm_network,
        }
        self.diagram_specific_settings = {
            AppName.REQUIREMENT: {"ortho": True, "sep": 0},
            AppName.STRATEGY_TACTICS: {"ortho": True, "sep": 0},
            AppName.CURRENT_REALITY: {"ortho": False, "sep": 20},
            AppName.PROCESS_FLOW: {"ortho": False, "sep": 20},
            AppName.EVAPORATING_CLOUD: {"ortho": False, "sep": 0},
            AppName.CCPM: {"ortho": False, "sep": 20},
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
        self.pfd_node_converters = {
            NodeType.PROCESS: lambda n, p: self._convert_pfd_element(n, p, NodeType.USECASE),
            NodeType.ENTITY: lambda n, p: self._convert_pfd_element(n, p, NodeType.USECASE),
            NodeType.CLOUD: lambda n, p: self._convert_pfd_element(n, p, NodeType.CLOUD),
            NodeType.CARD: lambda n, p: self._convert_simple_card_node(n, p, "title"),
            NodeType.DELIVERABLE: lambda n, p: self._convert_simple_card_node(n, p, "title"),
            NodeType.NOTE: lambda n, p: self._convert_note_using_field(n, p, "title", keep_newline=True),
        }

        # Current Reality Tree Node Converters
        self.crt_node_converters = {
            NodeType.AND: lambda n, p: f'usecase "AND{n[1]["unique_id"]}" as {n[1]["unique_id"]}',
            NodeType.ENTITY: lambda n, p: self._convert_simple_card_node(n, p, "text"),
            NodeType.NOTE: lambda n, p: self._convert_note_using_field(n, p, "text", keep_newline=True),
        }

        # Evaporating Cloud Node Converters
        self.ec_node_converters = {
            NodeType.NOTE: lambda n, p: self._convert_note_using_field(n, p, "text", keep_newline=True),
            NodeType.CARD: lambda n, p: self._convert_simple_card_node(n, p, "text"),
        }



    def convert_to_puml(
        self,
        page_title: str,
        graph: nx.DiGraph,
        title: str,
        parameters_dict: Dict,
        diagram_title: str = "",
    ) -> str:
        """要求仕様グラフをPlantUMLコード文字列に変換する。

        Args:
            page_title (str): アプリケーション名（ページタイトル）
            graph (nx.DiGraph): 要求のグラフ
            title (str): 図のタイトル
            parameters_dict (Dict): リンク処理などのパラメータ

        Returns:
            str: PlantUMLコード
        """
        specific_settings = self.diagram_specific_settings.get(
            page_title, {"ortho": True, "sep": 0}
        )  # Default if not found
        ortho = specific_settings.get("ortho", True)
        sep = specific_settings.get("sep", 0)
        scale = parameters_dict.get("scale", 1.0)
        landscape = parameters_dict.get("landscape", False)
        title_flag = parameters_dict.get("title", False)

        converter_method = self.diagram_converters.get(page_title)
        if not converter_method:
            raise ValueError(f"Invalid page_title specified: {page_title}")
            
        diagram_body = converter_method(graph, title, parameters_dict)

        puml_parts = [
            self._add_common_parameter_setting(
                scale,
                ortho,
                sep,
                landscape=landscape,
                title_flag=title_flag,
                diagram_title=diagram_title,
                diagram_body=diagram_body,
            ),
            diagram_body,
            "@enduml"
        ]
        
        # 冗長な改行を削除・圧縮
        final_puml = "\n".join(puml_parts)
        final_puml = re.sub(r'\n{3,}', '\n\n', final_puml)  # 3連続以上の改行を2連続（空行1つ）に圧縮
        final_puml = final_puml.strip() + "\n"              # 先頭と末尾の不要な空行を削除
        
        return final_puml

    def _add_common_parameter_setting(
        self,
        scale: float,
        ortho: bool = True,
        sep: int = 0,
        *,
        landscape: bool = False,
        title_flag: bool = False,
        diagram_title: str = "",
        diagram_body: str = "",
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

        possible_shapes = ["usecase", "card", "class", "cloud", "note"]
        used_shapes = [
            s for s in possible_shapes 
            if re.search(rf"(?m)^\s*{s}\b", diagram_body) or re.search(rf"(?m)^.*<<{s}>>", diagram_body)
        ]
        
        skinparam_template = "skinparam {shape} {{\nBackgroundColor White\nArrowColor Black\nBorderColor Black\nFontSize 12\n}}"
        skinparams = "\n".join(skinparam_template.format(shape=s) for s in used_shapes)

        return PUML_HEADER_TEMPLATE.format(
            ortho_str=ortho_str,
            sep_str=sep_str,
            landscape=landscape,
            skinparams=skinparams,
            scale=scale,
            diagram_title_str=diagram_title_str,
        )



    def _convert_nodes_to_puml(
        self, graph: nx.DiGraph, parameters_dict: Dict, node_converter_method
    ) -> List[str]:
        """特定のノードコンバータを使用して、グラフ内のすべてのノードをPUML文字列のリストに変換するヘルパーメソッド。"""
        puml_node_parts = []
        for node_data_tuple in graph.nodes(data=True):
            puml_node_parts.append(
                node_converter_method(node_data_tuple, parameters_dict)
            )
        return puml_node_parts

    def _convert_edges_to_puml(
        self, graph: nx.DiGraph, edge_converter_method, **kwargs
    ) -> List[str]:
        """特定のエッジコンバータを使用して、グラフ内のすべてのエッジをPUML文字列のリストに変換するヘルパーメソッド。"""
        puml_edge_parts = []
        for edge_data_tuple in graph.edges(data=True):
            puml_edge_parts.append(edge_converter_method(edge_data_tuple, **kwargs))
        return puml_edge_parts

    def _convert_requirement_diagram(
        self, graph: nx.DiGraph, title: str, parameters_dict: Dict
    ) -> str:
        """要求図(Requirement Diagram)のグラフをPlantUMLコードに変換する。

        Args:
            graph (nx.DiGraph): 要求のグラフ
            title (str): 図のタイトル
            parameters_dict (Dict): リンク処理などのパラメータ
        """
        # Draw package as frame
        target = parameters_dict.get("target", None)
        if not title:
            if target == None or target == "None" or target == "default":
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
        """パラメータの辞書をPlantUMLリンク文字列に変換する。

        Args:
            node (Tuple[str, Dict]): ノード情報 (unique_id は node[1]['unique_id'] に含まれる)
            parameters_dict (Dict): リンクベース用パラメータ

        Returns:
            str: PlantUMLリンク文字列 (例: "[[?param1=val1&selected=id]]")
        """
        query_items = []
        link_excluded_keys = {"project"}
        if parameters_dict:  # parameters_dictがNoneや空でないことを確認
            for key, value in parameters_dict.items():
                if key in link_excluded_keys:
                    continue
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
        if keep_newline:
            # 呼び出し元で既にクォート処理等は行われている前提、かつ改行は維持
            escaped_content = content_text
        else:
            escaped_content = self._escape_puml(content_text, keep_newline=False)
        
        body_content = stereotype_line + escaped_content
        # リンクが存在し、かつ空リンクでない場合にスペースを挟んで結合
        if link_for_content and link_for_content != "[[]]":
            body_content += " " + link_for_content

        return NOTE_TEMPLATE.format(
            unique_id=unique_id,
            color_str=color_str,
            body_content=body_content,
        )


    def _convert_dispatch_diagram(
        self, graph: nx.DiGraph, parameters_dict: Dict,
        node_converters: Dict, default_converter_key: str,
        edge_converter=None, edge_kwargs=None, extra_parts=None,
    ) -> str:
        """ディスパッチベースのダイアグラム変換の共通処理。"""
        puml_parts = list(self._convert_nodes_to_puml(
            graph, parameters_dict,
            lambda n, p: self._dispatch_conversion(
                n, p, node_converters, node_converters[default_converter_key]
            ),
        ))
        edge_conv = edge_converter or self._convert_card_edge
        puml_parts.extend(self._convert_edges_to_puml(graph, edge_conv, **(edge_kwargs or {})))
        if extra_parts:
            puml_parts.extend(extra_parts)
        return "\n".join(puml_parts)

    def _convert_evaporating_cloud(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        return self._convert_dispatch_diagram(
            graph, parameters_dict, self.ec_node_converters, NodeType.CARD,
            extra_parts=[EVAPORATING_CLOUD_LAYOUT],
        )

    def _create_card_puml(
        self, unique_id: str, content: str, parameters_str: str, color_str: str
    ) -> str:
        """カード要素のPlantUML文字列を生成する。"""
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
        raw_content = node_attrs.get(content_field, "") or node_attrs.get("title", "") or node_attrs.get("id", "")
        if node_attrs.get("finished", False):
            raw_content = CHECKBOX_IMG_PUML + " " + raw_content
        elif node_attrs.get("running", False):
            raw_content = RUNNING_IMG_PUML + " " + raw_content
            
        # カード要素は文字列の途中で改行が有効になるように \n を許可しておく
        content = self._escape_puml(raw_content, keep_newline=True)

        return self._create_card_puml(
            node_attrs["unique_id"], content, parameters_str, color_str
        )



    def _convert_requirement_node(
        self, node: Tuple[str, Dict], parameters_dict: Dict
    ) -> str:
        """要求ノードの情報をPlantUMLコードに変換する。

        Args:
            node (Tuple[str, Dict]): ノード情報
            parameters_dict (Dict): リンク処理などのパラメータ

        Returns:
            str: PlantUMLコード
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
        """要求図(Requirement Diagram)のユースケースノードをPlantUMLコードに変換する。

        Args:
            data (Dict[str, Any]): ユースケースノードの属性
            node_type (str): ノードのタイプ名(未使用、互換性のため)
            parameters_str (str): リンク用のパラメータ文字列
            detail (bool): 詳細表示するかどうか

        Returns:
            str: PlantUMLコード
        """
        # For PlantUML, the "usecase" entity cannot used on class diagram
        title = data.get("title", "")
        # タイトルをエスケープ
        escaped_title = self._escape_puml(title)
        
        # ID+タイトル文字列の生成もエスケープ済みタイトルを使用するよう _get_title_string を調整するか、
        # ここで組み立てる
        full_title = self._get_title_string(data.get('id', ''), escaped_title)
        
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
        """要求図(Requirement Diagram)の要求ノードをPlantUMLコードに変換する。

        Args:
            data (Dict[str, Any]): 要求ノードの情報
            node_type (str): 要求タイプ
            parameters_str (str): リンク用のパラメータ文字列
            detail (bool): 詳細表示するかどうか

        Returns:
            str: PlantUMLコード
        """
        title = data.get("title", "")
        text = data.get("text", "")
        
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
                id=data.get('id', ''),
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
        """要求図(Requirement Diagram)のブロック/テストケースノードをPlantUMLコードに変換する。

        Args:
            data (Dict[str, Any]): ブロックノードの情報
            node_type (str): ノードのタイプ
            parameters_str (str): リンク用のパラメータ文字列
            detail (bool): 詳細表示するかどうか

        Returns:
            str: PlantUMLコード
        """
        title = data.get("title", "")
        escaped_title = self._escape_puml(title)
        full_title = self._get_title_string(data.get('id', ''), escaped_title)
        
        color_str = self._get_puml_color(data)
        return f"class \"{full_title}\" as {data['unique_id']} <<{node_type}>> {parameters_str} {color_str}"

    def _convert_req_diagram_note_node(
        self,
        data: Dict[str, Any],
        node_type: str,
        parameters_str: str,
        detail: bool = True,
    ) -> str:
        """要求図(Requirement Diagram)の理由/問題(note相当)ノードをPlantUMLコードに変換する。

        Args:
            data (Dict[str, Any]): 理由または問題ノードの属性
            node_type (str): ノードのタイプ
            parameters_str (str): リンク用のパラメータ文字列
            detail (bool): 詳細表示するかどうか

        Returns:
            str: PlantUML文字列
        """
        # Display longer string from title and text
        title = data.get("title", "")
        text = data.get("text", "")
        if len(title) >= len(text):
            display_text = title
        else:
            display_text = text

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
        """IDとタイトルを結合した文字列を返す。

        Args:
            id (str): 要求のID
            title (str): 要求のタイトル

        Returns:
            str: タイトル文字列
        """
        # titleは呼び出し元ですでにエスケープされていることを想定
        if id != "":
            return f"{id}\\n{title}"
        else:
            return f"{title}"

    def _create_note_on_link_puml(self, note_data: Dict[str, Any]) -> str:
        """エッジ上のノート(note on link)のPlantUML文字列を生成する。

        Args:
            note_data (Dict[str, Any]): ノート情報(type, text)を含む辞書

        Returns:
            str: note on link のPlantUML文字列（テキストがない場合は空文字列）
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
        """エッジに対する汎用的なPlantUML文字列を生成する。"""
        # label_textはテンプレートから生成される固定文字列(<<type>>)が多いため、
        # ここではエスケープ対象としないが、動的な内容が含まれる場合は注意が必要。
        # 今回の要件図の仕様では label_text は固定フォーマットのみ。
        label_part = f" : {label_text}" if label_text else ""
        return f"{puml_node1} {line_style} {puml_node2}{label_part}{note_on_link_puml}"

    def _convert_requirement_edge(self, data: Dict[str, Any]):
        """関係性（エッジ）のPlantUML文字列を返す。

        Args:
            data (Dict[str, Any]): 関係性データ(src_id, dst_id, attributes)

        Returns:
            str: PlantUML文字列
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
        """S&Tツリー(Strategy and Tactics Tree)のグラフをPlantUMLコード文字列に変換する。

        Args:
            graph (nx.DiGraph): 要求のグラフ
            parameters_dict (Dict): リンク処理などのパラメータ

        Returns:
            str: PlantUMLコード
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
        """戦略・戦術ツリー(S&T)のノードをカードに変換する。"""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        detail = parameters_dict.get("detail", False)

        # 各フィールドをエスケープ
        node_id = node_attrs.get("id", "")
        necessary_assumption = self._escape_puml(node_attrs.get("necessary_assumption", ""), keep_newline=True)
        strategy = self._escape_puml(node_attrs.get("strategy", ""), keep_newline=True)
        parallel_assumption = self._escape_puml(node_attrs.get("parallel_assumption", ""), keep_newline=True)
        tactics = self._escape_puml(node_attrs.get("tactics", ""), keep_newline=True)
        sufficient_assumption = self._escape_puml(node_attrs.get("sufficient_assumption", ""), keep_newline=True)

        if not detail:
            content = ST_CONTENT_SIMPLE.format(
                node_id=node_id, strategy=strategy, tactics=tactics,
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
        """カード型エッジをPlantUMLコードに変換する。

        Args:
            data: エッジデータ (タプル: (src_id, dst_id, attributes_dict))
            use_src_arrow_dst_style:
                True の場合、矢印の向きはデフォルトで "src --> dst" となる (例: PFD)
                False (デフォルト) の場合、矢印の向きは "dst <-- src" となる (例: S&T, EC, CRT)

        Returns:
            str: エッジのPlantUML文字列
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
        """グラフを現状分析ツリー(CRT)のPlantUMLコード文字列に変換する。"""
        puml_parts = list(
            self._convert_nodes_to_puml(
                graph,
                parameters_dict,
                lambda n, p: self._dispatch_conversion(
                    n, p, self.crt_node_converters, self.crt_node_converters[NodeType.NOTE]
                ),
            )
        )

        seen_and_nodes, seen_edges_from_and = set(), set()

        for src, dst, attrs in graph.edges(data=True):
            and_id = attrs.get("and")

            if not and_id or and_id == "None":
                puml_parts.append(self._convert_card_edge((src, dst, attrs)))
                continue

            # ANDノードを経由するエッジ: src -> AND -> dst
            if and_id not in seen_and_nodes:
                puml_parts.append(f'usecase "AND{and_id}" as {and_id}')
                seen_and_nodes.add(and_id)

            # "and"キーを除いた属性をコピー
            clean_attrs = {k: v for k, v in attrs.items() if k != "and"}

            # src -> AND エッジ
            puml_parts.append(self._convert_card_edge((src, and_id, clean_attrs)))

            # AND -> dst エッジ (重複回避)
            if (and_id, dst) not in seen_edges_from_and:
                puml_parts.append(self._convert_card_edge((and_id, dst, clean_attrs)))
                seen_edges_from_and.add((and_id, dst))

        return "\n".join(puml_parts)


    def _convert_process_flow_diagram(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        """グラフをプロセスフロー図(PFD)のPlantUMLコード文字列に変換する。"""
        return self._convert_dispatch_diagram(
            graph, parameters_dict, self.pfd_node_converters, NodeType.NOTE,
            edge_kwargs={"use_src_arrow_dst_style": True},
        )

    def _convert_ccpm_network(
        self, graph: nx.DiGraph, _: str, parameters_dict: Dict
    ) -> str:
        """CCPM ネットワーク図を PFD と同じ形式で変換する。

        CP の矢印を黄色、CC の矢印を赤で着色する。
        CP==CC の場合はすべて赤で表示する。
        """
        from src.ccpm_engine import (
            get_in_out_edge_list,
            calculate_critical_path,
            calculate_critical_chain,
        )

        # ノード変換（完了タスクに ☑ プレフィックス、詳細なら日数と担当者を追加）
        import copy
        render_graph = copy.deepcopy(graph)
        
        # parameters_dict から詳細表示フラグを取得
        detail_flag = parameters_dict.get("detail", False)
        
        for node_id in render_graph.nodes:
            attrs = render_graph.nodes[node_id]
            title = attrs.get("title", "")
            # check / running アイコンは _convert_simple_card_node 等で付与される
            
            # 着手可能判定（全先行タスクが完了しているか）
            if not attrs.get("finished", False):
                actionable = True
                for p in graph.predecessors(node_id):
                    if not graph.nodes[p].get("finished", False):
                        actionable = False
                        break
                
                # 着手可能かつ開始日が設定されている場合は実行中アイコン対象
                if actionable and attrs.get("start", ""):
                    attrs["running"] = True
            
            # 詳細表示がオンで、days や resource が設定されている場合に追加
            if detail_flag:
                days = attrs.get("days")
                resource = attrs.get("resource")
                info = []
                if days is not None and str(days).strip():
                    info.append(f"{days}d")
                if resource and str(resource).strip():
                    info.append(str(resource))
                
                if info:
                    title += f"\n({', '.join(info)})"
            
            attrs["title"] = title

        puml_parts = list(self._convert_nodes_to_puml(
            render_graph, parameters_dict,
            lambda n, p: self._dispatch_conversion(
                n, p, self.pfd_node_converters,
                self.pfd_node_converters[NodeType.NOTE],
            ),
        ))

        # CP / CC 算出
        inputs, outputs = get_in_out_edge_list(graph)
        project = parameters_dict.get("project", {})
        cp_length, cp = calculate_critical_path(
            graph,
            inputs,
            outputs,
            project=project,
            duration_mode="display",
        )

        max_concurrency = parameters_dict.get("max_concurrency", 0)
        cc_length, cc, virtual_edges = calculate_critical_chain(
            graph,
            max_concurrency=max_concurrency,
            project=project,
            duration_mode="display",
        )

        # CP / CC のエッジペアセットを構築
        cp_edges = set()
        for i in range(len(cp) - 1):
            cp_edges.add((cp[i], cp[i + 1]))
        cc_edges = set()
        for i in range(len(cc) - 1):
            cc_edges.add((cc[i], cc[i + 1]))

        cp_changed = (cp != cc)

        # エッジ変換（色付き）
        # 仮想エッジのセットを作成（通常エッジとの区別用）
        virtual_edge_set = set((src, dst) for src, dst, _ in virtual_edges)

        for edge_data_tuple in graph.edges(data=True):
            src_id = edge_data_tuple[0]
            dst_id = edge_data_tuple[1]
            edge_attrs = edge_data_tuple[2]
            comment_text = edge_attrs.get("comment", "")
            escaped_comment = self._escape_puml(comment_text)

            edge_pair = (src_id, dst_id)
            if edge_pair in cc_edges:
                # CC 上のエッジは赤
                line_style = "-[#FF3333,bold]->"
            elif cp_changed and edge_pair in cp_edges:
                # CP と CC が異なる場合のみ、CP 固有のエッジを黄色表示
                line_style = "-[#FFB300,bold]->"
            else:
                line_style = "-->"

            puml_parts.append(
                self._create_generic_edge_puml(
                    src_id, dst_id, line_style, escaped_comment
                )
            )

        # 仮想エッジ（リソース競合による直列化）を点線赤矢印で表示
        for src, dst, resource in virtual_edges:
            line_style = "-[#FF3333,dashed]->"
            label = f"リソース競合: {resource}"
            puml_parts.append(
                self._create_generic_edge_puml(src, dst, line_style, label)
            )

        return "\n".join(puml_parts)

    def _convert_pfd_element(
        self, node: Tuple[str, Dict], parameters_dict: Dict, puml_type: str
    ) -> str:
        """PFD用の汎用要素(usecase, cloud等)を変換する。"""
        node_attrs = node[1]
        parameters_str = self._convert_parameters_dict(node, parameters_dict)
        color_str = self._get_puml_color(node_attrs)
        
        id_val = node_attrs.get("title", "")
        if node_attrs.get("finished", False):
            id_val = CHECKBOX_IMG_PUML + " " + id_val
        elif node_attrs.get("running", False):
            id_val = RUNNING_IMG_PUML + " " + id_val
            
        # エスケープ処理 (usecaseなどは\nに変換)
        escaped_id_val = self._escape_puml(id_val, keep_newline=False)
        
        return f'{puml_type} "{escaped_id_val}" as {node_attrs["unique_id"]} {parameters_str} {color_str}\n'

    def _get_puml_color(self, node_attrs: Dict) -> str:
        """ノード属性からPlantUML用の色指定文字列を取得する。"""
        color_key = node_attrs.get("color", Color.NONE)
        if color_key == Color.NONE or color_key is None:
            return ""
        return self._color_to_archimate.get(color_key, f"#{color_key}")

    def _escape_puml(self, text: str, keep_newline: bool = False) -> str:
        """PlantUML用にテキストをエスケープする。"""
        if not text:
            return ""
        escaped = text.replace('"', "'")
        if not keep_newline:
            escaped = escaped.replace('\n', '\\n')
        return escaped
