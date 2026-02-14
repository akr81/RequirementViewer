
# Common PlantUML Header Template
PUML_HEADER_TEMPLATE = """
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
{diagram_title_str}
"""

# Specific Layout Settings
ORTHO_SETTINGS = """
skinparam linetype polyline
skinparam linetype ortho
"""

SEP_SETTINGS = """
skinparam nodesep {sep}
skinparam ranksep {sep}
"""

# Evaporating Cloud Layout
EVAPORATING_CLOUD_LAYOUT = """
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

# Card Templates
CARD_TEMPLATE = """card {unique_id} {parameters_str} {color_str} [
{content}
]
"""

# Note Templates
NOTE_TEMPLATE = """note as {unique_id} {color_str}
{body_content}
end note"""

# Requirement Diagram Nodes
REQ_NODE_DETAIL_TEMPLATE = """class "{title}" as {unique_id} <<{type}>> {parameters} {color_str} {{
{field}id="{id}"
{field}text="{text}"
}}
"""

REQ_NODE_SIMPLE_TEMPLATE = """class "{title}" as {unique_id} <<{type}>> {parameters} {color_str}"""

REQ_USECASE_TEMPLATE = """usecase "{full_title}" as {unique_id} <<usecase>> {parameters} {color_str}"""

# Strategy and Tactics Tree Content Templates
ST_CONTENT_SIMPLE = """{node_id}
---
{strategy}
---
{tactics}"""

ST_CONTENT_DETAIL = """{node_id}
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
