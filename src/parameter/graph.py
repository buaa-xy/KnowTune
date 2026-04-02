from py2neo import Graph, Node, Relationship
import json

# -------------------------------
# Connect to Neo4j database
# -------------------------------
graph = Graph('bolt://localhost:7687', auth=('', ''))

# Optionally clear the database
# graph.delete_all()

# -------------------------------
# Load JSON file containing MySQL parameters
# -------------------------------
with open("xxx.json", "r", encoding="utf-8") as f:
    params = json.load(f)

# -------------------------------
# Dictionary to cache nodes
# -------------------------------
param_nodes = {}

# -------------------------------
# Create nodes for each parameter
# -------------------------------
for param in params:
    name = param["name"]
    info = param["info"]

    # Convert all properties to string
    node = Node(
        "Parameter_mysql",
        name=str(name),
        desc=str(info.get("desc", "")),
        needrestart=str(info.get("needrestart", "")),
        type=str(info.get("type", "")),
        min_value=str(info.get("min_value", "")),
        max_value=str(info.get("max_value", "")),
        default_value=str(info.get("default_value", "")),
        dtype=str(info.get("dtype", "")),
        version=str(info.get("version", "")),
        options=json.dumps(info.get("options", []), ensure_ascii=False) if info.get("options") else ""
    )

    # Merge node into the graph based on "name" uniqueness
    graph.merge(node, "Parameter_mysql", "name")
    param_nodes[name] = node

# -------------------------------
# Create relationships between parameters
# -------------------------------
for param in params:

    name = param["name"]
    info = param["info"]
    node = param_nodes[name]

    # Strong related parameters
    for related in info.get("strong_related_param", []):
        if related in param_nodes:
            rel = Relationship(node, "STRONG_RELATED_TO_mysql", param_nodes[related])
            graph.merge(rel)
        else:
            print(f"[Warning] Node not found for strong_related_param: {related} of {name}")

    # Weak related parameters
    for related in info.get("weak_related_param", []):
        if related in param_nodes:
            rel = Relationship(node, "WEAK_RELATED_TO_mysql", param_nodes[related])
            graph.merge(rel)

print("✅ All parameters have been saved as strings in Neo4j!")