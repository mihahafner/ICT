import os
import re
import csv
import requests
from dotenv import load_dotenv
import openai
import spacy
from rdflib import Graph, Namespace, URIRef, Literal
from pyvis.network import Network
from docx import Document

def load_paragraph_from_docx(filepath):
    doc = Document(filepath)
    full_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    return full_text.strip()

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Load API key from .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found")

client = openai.OpenAI(api_key=api_key)

# Step 1: Split long paragraph into sentences
def split_sentences(text):
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents]

# Step 2: Resolve coreferences using GPT
def resolve_coreferences(text):
    prompt = f"""
Resolve all coreferences in this paragraph. 

➡️ Replace **all pronouns** (e.g., "he", "she", "it", "they", "his", "her", "their") and **vague references** (e.g., "this", "that", "these", "those", "this event") with the **explicit full entity** they refer to.

Be precise. Do **not leave any reference unresolved**. The result must be suitable for RDF triple extraction — so use unambiguous, full noun phrases for each reference.

Text:
{text}
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# Step 3: Simplify sentence using GPT
def simplify_sentence(text):
    prompt = f"Simplify this sentence into short, clear factual statements suitable for RDF triple extraction. Clarify any implied relationships (e.g. link requirements to infrastructure).\n\nText:\n{text}"
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# Step 4: Extract triples using GPT
def extract_triples(text):
    prompt = f"Extract RDF-style triples from this sentence. Output format: (subject, predicate, object). Ensure all key entities are connected and no orphaned terms remain.\n\nText:\n{text}"
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


THESAURUS = {

}


def canonicalize_entity(label):
    norm = label.lower().strip()
    return THESAURUS.get(norm, label)


def normalize_label(label):
    label = label.strip()
    label = re.sub(r'^the\s+', '', label, flags=re.IGNORECASE)
    label = canonicalize_entity(label)  # 🔄 Apply thesaurus
    label = label[0].upper() + label[1:] if label else label
    return label

# Pre-clean GPT lines
def clean_gpt_output(output):
    lines = output.strip().splitlines()
    cleaned = [re.sub(r'^\d+\.\s*', '', line).strip() for line in lines if line.strip()]
    return cleaned

# Step 5: Parse triples
def parse_triples(gpt_output):
    triples = []
    for line in clean_gpt_output(gpt_output):
        match = re.match(r"\(?\"?([^,\"]+)\"?,\s*\"?([^,\"]+)\"?,\s*\"?([^\"\)]+)\"?\)?", line)
        if match:
            subj, pred, obj = match.groups()
            subj = normalize_label(subj)
            obj = normalize_label(obj)
            triples.append((subj.strip(), pred.strip(), obj.strip()))
        else:
            print(f"⚠️ Could not parse line: {line}")
    print("🔍 Extracted (parsed):", triples)
    return triples

def wikidata_lookup(label):
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "search": label
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = data.get("search", [])
        return results[0]['id'] if results else None
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Wikidata request failed: {e}")
    except ValueError:
        print(f"⚠️ Wikidata returned non-JSON for: {label}")
    return None

# Step 7: Build RDF graph and export CSVs
def build_rdf_graph(triples):
    g = Graph()
    EX = Namespace("http://example.org/")
    WD = Namespace("http://www.wikidata.org/entity/")
    g.bind("ex", EX)
    g.bind("wd", WD)

    rdf_rows = []
    nodes_set = set()

    for s, p, o in triples:
        s_uri = URIRef(EX[s.replace(" ", "_")])
        p_uri = URIRef(EX[p.replace(" ", "_")])
        if " " in o:
            o_val = Literal(o)
        else:
            o_wikidata = wikidata_lookup(o)
            o_val = URIRef(WD[o_wikidata]) if o_wikidata else Literal(o)

        g.add((s_uri, p_uri, o_val))
        rdf_rows.append((s, p, o))
        nodes_set.update([s, o])

    g.serialize(destination="output.ttl", format="turtle")
    print("✅ RDF graph saved as: output.ttl")

    with open("output_triples.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Subject", "Predicate", "Object"])
        writer.writerows(rdf_rows)
    print("✅ RDF triples saved as: output_triples.csv")

    with open("output_nodes.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Entity"])
        for node in sorted(nodes_set):
            writer.writerow([node])
    print("✅ RDF nodes saved as: output_nodes.csv")

    print("🔍 All RDF triples:")
    for stmt in g:
        print(stmt)

    return g

# Step 8: Visualize graph including orphans
def visualize_graph(triples, output_file="graph.html"):
    net = Network(directed=True, height='600px', width='100%')
    all_nodes = set()

    for s, p, o in triples:
        all_nodes.update([s, o])
        net.add_node(s, label=s)
        net.add_node(o, label=o)
        net.add_edge(s, o, label=p)

    for node in all_nodes:
        if not any(e for e in net.edges if node in (e['from'], e['to'])):
            net.add_node(node, label=node, color='gray')

    net.write_html(output_file)
    print(f"✅ Graph visualization saved to: {output_file}")

# MAIN
if __name__ == "__main__":
    docx_path = "Tests/Building_X_Risk_Analysis.docx"  # Change this to match your file location
    paragraph = load_paragraph_from_docx(docx_path)
    #paragraph = "The dog is a domesticated descendant of the gray wolf. Also called the domestic dog, it was selectively bred from a population of wolves during the Late Pleistocene by hunter-gatherers. The dog was the first species to be domesticated by humans, over 14,000 years ago and before the development of agriculture. Due to their long association with humans, dogs have gained the ability to thrive on a starch-rich diet that would be inadequate for other canids."
    all_triples = []
    # First resolve coreferences across the whole paragraph
    resolved_paragraph = resolve_coreferences(paragraph)
    print("🧠 Resolved paragraph:\n", resolved_paragraph)

    # Then split and process each sentence
    for sentence in split_sentences(resolved_paragraph):
        simplified = simplify_sentence(sentence)
        extracted = extract_triples(simplified)
        triples = parse_triples(extracted)
        all_triples.extend(triples)

    build_rdf_graph(all_triples)
    visualize_graph(all_triples, output_file="Tests/graph.html")
