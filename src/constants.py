class AppName:
    REQUIREMENT = "Requirement Diagram Viewer"
    PROCESS_FLOW = "Process Flow Diagram Viewer"
    CURRENT_REALITY = "Current Reality Tree Viewer"
    EVAPORATING_CLOUD = "Evaporating Cloud Viewer"
    STRATEGY_TACTICS = "Strategy and Tactics Tree Viewer"


class NodeType:
    REQUIREMENT = "requirement"
    USECASE = "usecase"
    PROCESS = "process"
    CLOUD = "cloud"
    CARD = "card"
    NOTE = "note"
    ENTITY = "entity"
    AND = "and"
    DELIVERABLE = "deliverable"
    INTERFACE = "interface"
    FUNCTIONAL_REQUIREMENT = "functionalRequirement"
    INTERFACE_REQUIREMENT = "interfaceRequirement"
    PERFORMANCE_REQUIREMENT = "performanceRequirement"
    PHYSICAL_REQUIREMENT = "physicalRequirement"
    DESIGN_CONSTRAINT = "designConstraint"
    BLOCK = "block"
    TEST_CASE = "testCase"
    RATIONALE = "rationale"
    PROBLEM = "problem"


class EdgeType:
    ARROW = "arrow"
    FLAT = "flat"
    FLAT_LONG = "flat_long"
    DERIVE_KEY = "deriveReqt"
    SATISFY = "satisfy"
    VERIFY = "verify"
    REFINE = "refine"
    TRACE = "trace"
    COPY = "copy"
    CONTAINS = "contains"
    AGGREGATION = "aggregation"


class Color:
    NONE = "None"
