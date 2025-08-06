import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Paths to scripts
synonyms_script = BASE_DIR / "scripts" / "synonyms_terminology.py"
cooccurrence_script = BASE_DIR / "scripts" / "qa_QA_ner_graph.py"
relation_script = BASE_DIR / "scripts" / "relation_extraction_graph.py"

# Output files
process_dir = BASE_DIR / "process_data"
visuals_dir = BASE_DIR / "visuals"

NER_CSV = process_dir / "entities_edges_NER.csv"
REL_CSV = process_dir / "entities_edges_relation.csv"
NER_HTML = visuals_dir / "qa_entities_graph.html"
REL_HTML = visuals_dir / "relations_entities_graph.html"

if __name__ == "__main__":
    print("🔄 Step 1: Running synonym & terminology normalization...")
    subprocess.run(["python", str(synonyms_script)], check=True)

    print("📊 Step 2: Running co-occurrence entity graph (NER-based)...")
    subprocess.run(["python", str(cooccurrence_script)], check=True)

    print("🔍 Step 3: Running relationship extraction graph...")
    subprocess.run(["python", str(relation_script)], check=True)

    print("\n✅ Workflow complete! Outputs generated:\n")
    print(f"📄 NER CSV: {NER_CSV.resolve()}")
    print(f"📄 Relation CSV: {REL_CSV.resolve()}")
    print(f"🌐 NER HTML: {NER_HTML.resolve()}")
    print(f"🌐 Relation HTML: {REL_HTML.resolve()}")
    print("\n💡 Tip: Copy-paste the HTML file paths into your browser to view the graphs.")
