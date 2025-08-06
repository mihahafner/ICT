import re
import spacy
import docx
import pandas as pd
from pathlib import Path
from pyvis.network import Network
import networkx as nx
import random
from itertools import combinations
from synonyms_terminology import synonym_map

def normalize_entity(ent_text):
    ent_clean = ent_text.strip()
    if ent_clean.lower().startswith("the "):
        ent_clean = ent_clean[4:]  # remove leading 'the '
    return synonym_map.get(ent_clean.lower(), ent_clean)

# ===== Paths =====
BASE_DIR = Path(__file__).resolve().parent.parent
PROCESS_DIR = BASE_DIR / "process_data"
VISUALS_DIR = BASE_DIR / "visuals"

QA_FILE = PROCESS_DIR / "ICT_toppics_expresions_edit.docx"
CSV_FILE = PROCESS_DIR / "entities_edges_relation.csv"
HTML_FILE = VISUALS_DIR / "relations_entities_graph.html"

PROCESS_DIR.mkdir(exist_ok=True)
VISUALS_DIR.mkdir(exist_ok=True)

MAX_DEP_DISTANCE = 3

# ===== Load spaCy model =====
nlp = spacy.load("en_core_web_lg")

custom_terms = [
    "GDPR", "TCP/IP", "HTTP", "HTTPS", "5G", "AI", "Artificial Intelligence",
    "Machine Learning", "Deep Learning", "Kubernetes", "Docker", "Neo4j",
    "Data Lake", "Data Warehouse", "ETL", "ELT", "MLOps", "IoT",
    "Cloud Computing", "AWS", "Azure", "Google Cloud"
]
custom_pattern = re.compile(r"\b(" + "|".join(re.escape(t) for t in custom_terms) + r")\b", re.IGNORECASE)

RELATION_PATTERNS = {
    "is_a": {"be", "is", "are", "was", "were", "constitute", "represent"},
    "regulates": {"regulate", "govern", "control", "oversee", "enforce", "dictate", "manage"},
    "uses": {"use", "utilize", "apply", "employ", "leverage"},
    "based_on": {"base", "build", "derive", "depend", "develop"},
    "part_of": {"part", "component", "element", "segment", "member", "belong"}
}

def load_qa_from_docx(file_path):
    doc = docx.Document(file_path)
    qa_list = []
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    has_labels = any(p.lower().startswith("q:") or p.lower().startswith("question") for p in paras)
    if has_labels:
        current_q, current_a = None, None
        for text in paras:
            if text.lower().startswith("q:") or text.lower().startswith("question"):
                current_q = text
            elif text.lower().startswith("a:") or text.lower().startswith("answer"):
                current_a = text
                if current_q:
                    qa_list.append((current_q, current_a))
                    current_q, current_a = None, None
    else:
        for i in range(0, len(paras), 2):
            if i + 1 < len(paras):
                qa_list.append((paras[i], paras[i+1]))
    return qa_list

def dependency_distance(token1, token2):
    try:
        visited = set()
        queue = [(token1, 0)]
        while queue:
            node, dist = queue.pop(0)
            if node == token2:
                return dist
            visited.add(node)
            neighbors = list(node.children) + ([node.head] if node.head != node else [])
            for n in neighbors:
                if n not in visited:
                    queue.append((n, dist + 1))
        return None
    except Exception:
        return None

def extract_entities(text):
    doc = nlp(text)
    ents = {ent for ent in doc.ents if ent.label_ in ["ORG", "PRODUCT", "GPE", "LAW", "EVENT", "TECHNOLOGY"]}
    for match in custom_pattern.findall(text):
        match_doc = nlp(match.strip())
        if match_doc.ents:
            ents.add(match_doc.ents[0])
    return list(ents)

def extract_relations_in_sentence(sent):
    relations = []
    ents_in_sent = [ent for ent in sent.ents]
    if len(ents_in_sent) < 2:
        return relations
    for token in sent:
        for rel_label, verbs in RELATION_PATTERNS.items():
            if token.lemma_.lower() in verbs:
                for e1, e2 in combinations(ents_in_sent, 2):
                    dist = dependency_distance(e1.root, e2.root)
                    if dist is not None and dist <= MAX_DEP_DISTANCE:
                        relations.append((e1.text, rel_label, e2.text))
    return relations

def build_graph_with_relations(qa_list):
    G = nx.DiGraph()
    all_entities = set()

    for idx, (q, a) in enumerate(qa_list, start=1):
        text_block = f"{q} {a}"
        doc = nlp(text_block)

        ents_all = extract_entities(text_block)
        ents_all = list({ent.text.strip(): ent for ent in ents_all}.values())
        ents_norm = [normalize_entity(ent.text) for ent in ents_all]

        for ent in ents_norm:
            all_entities.add(ent)

        # Strong edges: same sentence + dep distance + verb pattern
        for sent in doc.sents:
            for e1, rel, e2 in extract_relations_in_sentence(sent):
                G.add_edge(normalize_entity(e1), normalize_entity(e2), label=rel)

        # Weak edges: different sentences in same Q&A
        for i in range(len(ents_norm)):
            for j in range(i + 1, len(ents_norm)):
                if ents_all[i].sent != ents_all[j].sent:
                    if not G.has_edge(ents_norm[i], ents_norm[j]):
                        G.add_edge(ents_norm[i], ents_norm[j], label="co_occurs")

    for entity in all_entities:
        if entity not in G.nodes():
            G.add_node(entity)

    components = list(nx.weakly_connected_components(G))
    cluster_colors = {}
    for comp in components:
        color = f"#{random.randint(0, 0xFFFFFF):06x}"
        for node in comp:
            cluster_colors[node] = color

    net = Network(height="750px", width="100%", bgcolor="white", font_color="black", directed=True)
    for node in G.nodes():
        net.add_node(node, label=node, color=cluster_colors[node])
    for e1, e2, data in G.edges(data=True):
        net.add_edge(e1, e2, title=data.get("label", ""), label=data.get("label", ""))

    return net, [(e1, data["label"], e2) for e1, e2, data in G.edges(data=True)]

if __name__ == "__main__":
    if not QA_FILE.exists():
        print(f"❌ Cleaned Q&A file not found: {QA_FILE}")
        exit(1)
    qa_list = load_qa_from_docx(QA_FILE)
    print(f"📄 Loaded {len(qa_list)} Q&A pairs from cleaned document.")
    net, relations = build_graph_with_relations(qa_list)
    pd.DataFrame(relations, columns=["Entity1", "Relation", "Entity2"]).to_csv(CSV_FILE, index=False)
    net.save_graph(str(HTML_FILE))
    print(f"✅ Relationship Graph saved to {HTML_FILE}")
    print(f"✅ Relations CSV saved to {CSV_FILE}")
