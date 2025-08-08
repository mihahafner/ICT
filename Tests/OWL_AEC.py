# === aec_fire_safety_pipeline.py ===
import os
from owlready2 import *
from pyvis.network import Network
from rdflib import Graph, URIRef
from pyshacl import validate

# -----------------------------
# 0) Output folder
# -----------------------------
os.makedirs("Tests", exist_ok=True)

# -----------------------------
# 1) Create TBox (Ontology Schema)
# -----------------------------
onto = get_ontology("http://example.org/aec.owl")

with onto:
    # Root - Categories
    class AEC(Thing): pass
    class State(Thing): pass
    class Infrastructure(Thing): pass
    class Function(Thing): pass
    class Phase(AEC): pass

    # Phases  ✅ (fix: subclass Phase, not Function)
    class Design(Phase): pass
    class Construction(Phase): pass
    class Operation(Phase): pass
    class Refurbishment(Phase): pass
    class Removal(Phase): pass

    # Disciplines / infra
    class Architecture(Design): pass
    class Engineering(Design): pass
    class Construction(Design): pass

    class Traffic(Infrastructure): pass
    class Building(Infrastructure): pass

    class Normal(State): pass
    class Emergency(State): pass

    class Risk(Emergency): pass
    class Fire(Risk): pass
    class Accident(Risk): pass

    # Safety ✅ (fix: don’t subclass Phase)
    class SafetySystem(Risk): pass
    class SafetyEquipment(Risk): pass
    class SafetyFunction(Risk): pass
    class Evacuation(SafetyFunction): pass
    class EmergencyIntervention(SafetyFunction): pass
    class IncidentDetection(SafetyFunction): pass

    class FireExtinguisher(SafetyEquipment): pass
    class Hydrant(SafetyEquipment): pass
    class FireDetection(SafetyEquipment): pass

    # Object properties
    class is_a (Thing >> AEC): pass
    class isDivided(AEC >> Phase): pass
    class is_a (Phase >> Design): pass  
    class is_a (Phase >> Construction): pass
    class is_a (Phase >> Operation): pass
    class is_a (Phase >> Refurbishment): pass
    class is_a (Phase >> Removal): pass


    class hasFunction(Infrastructure >> Function): pass
    class hasSafetySystem(Infrastructure >> SafetySystem): pass
    class hasSafetyEquipment(Infrastructure >> SafetyEquipment): pass
    class usesEquipment(SafetySystem >> SafetyEquipment): pass
    class requiredFor(Infrastructure >> SafetyFunction): pass
    class requiredInPhase(SafetyFunction >> Phase): pass
    class supportsFunction(SafetySystem >> SafetyFunction): pass
    class mitigates(SafetySystem >> Function): pass

    """
    # Object properties
    class hasPart(Infrastructure >> Infrastructure): pass
    class inPhase(Infrastructure >> Phase): pass
    class hasFunction(Infrastructure >> Function): pass
    class hasSafetySystem(Infrastructure >> SafetySystem): pass
    class hasSafetyEquipment(Infrastructure >> SafetyEquipment): pass
    class usesEquipment(SafetySystem >> SafetyEquipment): pass
    class requiredFor(Infrastructure >> SafetyFunction): pass
    class requiredInPhase(SafetyFunction >> Phase): pass
    class supportsFunction(SafetySystem >> SafetyFunction): pass
    class mitigates(SafetySystem >> Function): pass
    """
    
    # Data properties
    class pathWidth(AEC >> float): pass
    class height(Infrastructure >> float): pass
    class numberOfFloors(Infrastructure >> int): pass
    class riskLevel(Function >> int): pass
    class hasWeight(SafetyEquipment >> float): pass

onto.save(file="Tests/fire_safety_aec.owl", format="rdfxml")
print("✅ TBox saved as Tests/fire_safety_aec.owl")

# -----------------------------
# 2) Create a tiny ABox file
# -----------------------------
abox_ttl = """@prefix ex: <http://example.org/aec#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:Building_X a ex:Building ;
    ex:height "25.0"^^xsd:float ;
    ex:numberOfFloors "8"^^xsd:int ;
    ex:hasSafetySystem ex:Sprinkler_System_1 ;
    ex:hasSafetyEquipment ex:Hydrant_1 ;
    ex:hasFunction ex:Evacuation_Function ;
    ex:inPhase ex:Operation .

ex:Sprinkler_System_1 a ex:SafetySystem ;
    ex:supportsFunction ex:Incident_Detection_Function ;
    ex:mitigates ex:Evacuation_Function .

ex:Hydrant_1 a ex:Hydrant ;
    ex:hasWeight "6.0"^^xsd:float .

ex:Evacuation_Function a ex:Evacuation ;
    ex:requiredInPhase ex:Emergency .

ex:Incident_Detection_Function a ex:IncidentDetection .

ex:Operation a ex:Operation .
ex:Emergency a ex:Emergency .
"""
with open("Tests/fire_safety_aec_data.ttl", "w") as f:
    f.write(abox_ttl)
print("✅ ABox saved as Tests/fire_safety_aec_data.ttl")

# -----------------------------
# 3) SHACL Shapes (optional but useful)
# -----------------------------
shapes_ttl = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/aec#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:BuildingSafetyShape
  a sh:NodeShape ;
  sh:targetClass ex:Building ;
  sh:property [
    sh:path ex:hasSafetySystem ;
    sh:minCount 1 ;
    sh:message "Every building must have at least one Safety System" ;
  ] .

ex:ExtinguisherWeightShape
  a sh:NodeShape ;
  sh:targetClass ex:FireExtinguisher ;
  sh:property [
    sh:path ex:hasWeight ;
    sh:minInclusive 5.0 ;
    sh:maxInclusive 12.0 ;
    sh:datatype xsd:float ;
    sh:message "Fire extinguishers must weigh between 5 and 12 kg" ;
  ] .
"""
with open("Tests/fire_safety_shapes.ttl", "w") as f:
    f.write(shapes_ttl)
print("✅ SHACL shapes saved as Tests/fire_safety_shapes.ttl")

# -----------------------------
# 4) Run SHACL Validation
# -----------------------------
print("🔍 Running SHACL validation...")
data_graph = Graph()
data_graph.parse("Tests/fire_safety_aec_data.ttl", format="turtle")
shapes_graph = Graph()
shapes_graph.parse("Tests/fire_safety_shapes.ttl", format="turtle")

conforms, results_graph, results_text = validate(
    data_graph,
    shacl_graph=shapes_graph,
    inference='rdfs',
    abort_on_first=False,
    meta_shacl=False,
    debug=False
)
print("✅ Conforms:", conforms)
print(results_text)

# -----------------------------
# 5) Visualize ABox (predicates as edges)
# -----------------------------
def visualize_abox_rdf(abox_file, html_out):
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

    g = Graph()
    g.parse(abox_file, format="turtle")

    for s, p, o in g:
        s_lbl = s.split("#")[-1]
        p_lbl = p.split("#")[-1]
        if isinstance(o, URIRef):
            o_lbl = o.split("#")[-1]
            add_node(s_lbl, s_lbl, "mediumseagreen")
            add_node(o_lbl, o_lbl, "mediumseagreen")
            net.add_edge(s_lbl, o_lbl, label=p_lbl)
        else:
            lit = str(o)
            lit_id = f"lit::{s_lbl}::{p_lbl}::{lit}"
            add_node(s_lbl, s_lbl, "mediumseagreen")
            add_node(lit_id, lit, "lightgray")
            net.add_edge(s_lbl, lit_id, label=p_lbl)

    net.write_html(html_out)
    print(f"✅ ABox visualization saved to: {html_out}")

# -----------------------------
# 6) Visualize TBox (domain/range) + ABox overlay
# -----------------------------
def visualize_tbox_abox(onto, abox_file, html_out):
    net = Network(height="750px", width="100%", directed=True)
    added = set()

    def add_node(nid, label, color):
        if nid not in added:
            net.add_node(nid, label=label, color=color)
            added.add(nid)

    # TBox schema: class→class edges (orange labels)
    for prop in onto.object_properties():
        for domain in prop.domain:
            for rng in prop.range:
                add_node(domain.name, domain.name, "dodgerblue")
                add_node(rng.name, rng.name, "dodgerblue")
                net.add_edge(domain.name, rng.name, label=prop.name, color="orange")

    for prop in onto.data_properties():
        for domain in prop.domain:
            add_node(domain.name, domain.name, "dodgerblue")
            lit_node_id = f"{prop.name}_Literal"
            add_node(lit_node_id, "Literal", "lightgray")
            net.add_edge(domain.name, lit_node_id, label=prop.name, color="orange")

    # ABox overlay
    g = Graph()
    g.parse(abox_file, format="turtle")
    for s, p, o in g:
        s_lbl = s.split("#")[-1]
        p_lbl = p.split("#")[-1]
        if isinstance(o, URIRef):
            o_lbl = o.split("#")[-1]
            add_node(s_lbl, s_lbl, "mediumseagreen")
            add_node(o_lbl, o_lbl, "mediumseagreen")
            net.add_edge(s_lbl, o_lbl, label=p_lbl, color="#999999")
        else:
            lit = str(o)
            lit_id = f"lit::{s_lbl}::{p_lbl}::{lit}"
            add_node(s_lbl, s_lbl, "mediumseagreen")
            add_node(lit_id, lit, "lightgray")
            net.add_edge(s_lbl, lit_id, label=p_lbl, color="#999999")

    net.write_html(html_out)
    print(f"✅ TBox+ABox visualization saved to: {html_out}")

# -----------------------------
# 7) Run both visualizations
# -----------------------------
visualize_abox_rdf("Tests/fire_safety_aec_data.ttl", "Tests/ontology_graph_abox.html")
visualize_tbox_abox(onto, "Tests/fire_safety_aec_data.ttl", "Tests/ontology_graph_tbox_abox.html")

print("Open:")
print(" - Tests/ontology_graph_abox.html")
print(" - Tests/ontology_graph_tbox_abox.html")
