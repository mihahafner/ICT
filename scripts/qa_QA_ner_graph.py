import re
import spacy
import docx
import pandas as pd
from itertools import combinations
from pyvis.network import Network
from pathlib import Path
import networkx as nx
import random
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
CSV_FILE = PROCESS_DIR / "entities_edges_NER.csv"
HTML_FILE = VISUALS_DIR / "qa_entities_graph.html"

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

def extract_entities(text):
    doc = nlp(text)
    ents = {ent for ent in doc.ents if ent.label_ in ["ORG", "PRODUCT", "GPE", "LAW", "EVENT", "TECHNOLOGY"]}
    for match in custom_pattern.findall(text):
        match_doc = nlp(match.strip())
        if match_doc.ents:
            ents.add(match_doc.ents[0])
    return list(ents)

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

def build_graph(qa_list):
    G = nx.Graph()
    all_entities = set()

    for idx, (q, a) in enumerate(qa_list, start=1):
        doc = nlp(f"{q} {a}")
        ents = extract_entities(f"{q} {a}")
        ents = list({ent.text.strip(): ent for ent in ents}.values())

        ents_norm = [normalize_entity(ent.text) for ent in ents]
        for ent in ents_norm:
            all_entities.add(ent)

        for i in range(len(ents_norm)):
            for j in range(i + 1, len(ents_norm)):
                if ents[i].sent == ents[j].sent:
                    dist = dependency_distance(ents[i].root, ents[j].root)
                    if dist is not None and dist <= MAX_DEP_DISTANCE:
                        G.add_edge(ents_norm[i], ents_norm[j], title=f"Strong: Dep-path ≤{MAX_DEP_DISTANCE} in Q{idx}")
                else:
                    G.add_edge(ents_norm[i], ents_norm[j], title=f"Weak: Co-occurs in Q{idx}")

    for entity in all_entities:
        if entity not in G.nodes():
            G.add_node(entity)

    components = list(nx.connected_components(G))
    cluster_colors = {}
    for comp in components:
        color = f"#{random.randint(0, 0xFFFFFF):06x}"
        for node in comp:
            cluster_colors[node] = color

    net = Network(height="750px", width="100%", bgcolor="white", font_color="black")
    for node in G.nodes():
        net.add_node(node, label=node, color=cluster_colors[node])
    for e1, e2, data in G.edges(data=True):
        net.add_edge(e1, e2, title=data.get("title", ""))

    return net, list(G.edges())

if __name__ == "__main__":
    if not QA_FILE.exists():
        print(f"❌ Cleaned Q&A file not found: {QA_FILE}")
        exit(1)
    qa_list = load_qa_from_docx(QA_FILE)
    print(f"📄 Loaded {len(qa_list)} Q&A pairs from cleaned document.")
    net, edges = build_graph(qa_list)
    pd.DataFrame(edges, columns=["Entity1", "Entity2"]).to_csv(CSV_FILE, index=False)
    net.save_graph(str(HTML_FILE))
    print(f"✅ NER Graph saved to {HTML_FILE}")
    print(f"✅ Edges saved to {CSV_FILE}")
