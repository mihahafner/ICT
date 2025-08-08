# === semantic_web_style_ontology.py ===
from owlready2 import *
from pyvis.network import Network

# -----------------------------
# 1) Build a tiny ontology
# -----------------------------
onto = get_ontology("http://example.org/fire_safety.owl")

with onto:
    # Classes (concepts)
    class Building(Thing): pass
    class Architecture(Thing): pass
    class Risk(Thing): pass
    class SafetyMeasure(Thing): pass
    class FireSafety(SafetyMeasure): pass
    class FixedFireFightingSystem(SafetyMeasure): pass
    class FireExtinguisher(SafetyMeasure): pass
    class EvacuationRoute(Thing): pass

    # Object properties (relationships)
    class hasArchitecture(Building >> Architecture): pass
    class hasSafetyMeasure(Building >> SafetyMeasure): pass
    class hasRisk(Building >> Risk): pass
    class mitigates(SafetyMeasure >> Risk): pass

    # Data properties (attributes)
    class hasFloors(Architecture >> int): pass
    class hasHeight(Building >> float): pass
    class hasWeight(FireExtinguisher >> float): pass
    class riskLevel(Risk >> int): pass

    # Instances
    bldgX = Building("Building_X")
    archX = Architecture("Architecture_X")
    fireRisk = Risk("Fire_Risk")
    extinguisher1 = FireExtinguisher("FireExtinguisher_1")
    ffs1 = FixedFireFightingSystem("Sprinkler_System_1")

    # Object property assertions
    bldgX.hasArchitecture.append(archX)
    bldgX.hasSafetyMeasure.extend([extinguisher1, ffs1])
    bldgX.hasRisk.append(fireRisk)
    ffs1.mitigates.append(fireRisk)

    # Data property assertions (literals)
    archX.hasFloors.append(8)         # e.g., 8 floors
    bldgX.hasHeight.append(25.0)      # meters
    extinguisher1.hasWeight.append(6.0)  # kg
    fireRisk.riskLevel.append(4)

onto.save(file="Tests/fire_safety.owl", format="rdfxml")
print("✅ Saved OWL as fire_safety.owl")

# -----------------------------
# 2) Visualize in semantic-web style
#    Blue = classes, Green = instances, Orange = properties, Gray = literals
#    Edges: subject → [property-node] → object
# -----------------------------
# --- RDF-style viz: predicates are EDGES, not nodes ---
def visualize_rdf_edge_style(onto, html_out="Tests/ontology_graph.html",
                             show_classes=True, show_instance_of=True, show_subclass=True):
    net = Network(directed=True, height="750px", width="100%", bgcolor="white", font_color="black")
    net.set_options("""{
      "physics": { "solver": "forceAtlas2Based", "stabilization": { "iterations": 350 } },
      "nodes": { "font": { "size": 18 }, "shape": "dot", "scaling": { "min": 10, "max": 24 } },
      "edges": { "font": { "size": 14, "align": "middle" },
                 "arrows": { "to": { "enabled": true, "scaleFactor": 0.7 } } }
    }""")

    added = set()
    def add_node(nid, label, color):
        if nid not in added:
            net.add_node(nid, label=label, color=color)
            added.add(nid)

    # nice labels for literals (units etc.)
    def lit_label(prop, val):
        if prop == "hasWeight": return f"{val} kg"
        if prop == "hasHeight": return f"{val} m"
        if prop == "hasFloors": return f"{val} floors"
        return str(val)

    # 1) Classes (blue) + optional subclass edges
    class_names = {c.name for c in onto.classes()}
    if show_classes:
        for c in onto.classes():
            add_node(c.name, c.name, "lightblue")
        if show_subclass:
            for c in onto.classes():
                for p in c.is_a:
                    if isinstance(p, ThingClass):
                        add_node(p.name, p.name, "lightblue")
                        net.add_edge(p.name, c.name, label="is_a", color="#8ec7ff")

    # 2) Instances (green) + optional instance_of edges
    inst_names = {i.name for i in onto.individuals()}
    for i in onto.individuals():
        add_node(i.name, i.name, "mediumseagreen")
        if show_classes and show_instance_of:
            for c in i.is_a:
                if isinstance(c, ThingClass):
                    add_node(c.name, c.name, "lightblue")
                    net.add_edge(i.name, c.name, label="rdf:type", color="#8ec7ff")

    # 3) Object-property assertions: instance → instance (edge label = predicate)
    for prop in onto.object_properties():
        pname = prop.name
        for s, o in prop.get_relations():
            add_node(s.name, s.name, "mediumseagreen")
            add_node(o.name, o.name, "mediumseagreen")
            net.add_edge(s.name, o.name, label=pname)

    # 4) Data-property assertions: instance → literal (edge label = predicate)
    for prop in onto.data_properties():
        pname = prop.name
        for s, val in prop.get_relations():
            add_node(s.name, s.name, "mediumseagreen")
            lit = lit_label(pname, val)
            lit_id = f"lit::{pname}::{s.name}::{lit}"
            add_node(lit_id, lit, "lightgray")
            net.add_edge(s.name, lit_id, label=pname)

    net.write_html(html_out)
    print(f"✅ Visualization (predicates as edges) saved to: {html_out}")

def visualize_tbox_abox(onto, html_out="Tests/ontology_graph_tbox_abox.html"):
    net = Network(height="750px", width="100%", directed=True)
    added_nodes = set()

    def add_node(node_id, label, color):
        if node_id not in added_nodes:
            net.add_node(node_id, label=label, color=color)
            added_nodes.add(node_id)

    # ---- TBox (Schema) ----
    for prop in onto.object_properties():
        for domain in prop.domain:
            for range_cls in prop.range:
                add_node(domain.name, domain.name, "dodgerblue")  # class
                add_node(range_cls.name, range_cls.name, "dodgerblue")  # class
                net.add_edge(domain.name, range_cls.name, label=prop.name, color="orange")

    for prop in onto.data_properties():
        for domain in prop.domain:
            add_node(domain.name, domain.name, "dodgerblue")
            lit_node_id = f"{prop.name}_value"
            add_node(lit_node_id, "Literal", "lightgray")
            net.add_edge(domain.name, lit_node_id, label=prop.name, color="orange")

    # ---- ABox (Instances) ----
    for prop in onto.object_properties():
        for s, o in prop.get_relations():
            add_node(s.name, s.name, "mediumseagreen")  # instance
            add_node(o.name, o.name, "mediumseagreen")  # instance
            net.add_edge(s.name, o.name, label=prop.name, color="#999999")

    for prop in onto.data_properties():
        for s, val in prop.get_relations():
            add_node(s.name, s.name, "mediumseagreen")
            lit_id = f"{prop.name}::{s.name}::{val}"
            add_node(lit_id, str(val), "lightgray")
            net.add_edge(s.name, lit_id, label=prop.name, color="#999999")

    net.write_html(html_out)
    print(f"✅ Visualization saved to {html_out}")



visualize_rdf_edge_style(onto)
visualize_tbox_abox(onto)