"""Metadata inventory after the recorded G0_PASS. No sequence search."""
import csv
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote
from urllib.error import HTTPError
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
out = root / "data/external/nto/cp1_20261015/metadata"
out.mkdir(parents=True, exist_ok=True)
import sys
sys.path.insert(0, str(root / "src"))
from zeaguard.nb04_resources import verify_g0
verify_g0(root)
def get(name, url):
    target = out / (name + ".json")
    receipt = target.with_suffix(".receipt.json")
    if target.exists():
        data = target.read_bytes()
        assert json.loads(receipt.read_text())["sha256"] == hashlib.sha256(data).hexdigest()
        return json.loads(data)
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "ZeaGuard-NB04-CP1/1.0"}), timeout=45) as r:
                data = r.read()
                headers = dict(r.headers)
            parsed = json.loads(data)
            target.write_bytes(data)
            receipt.write_text(json.dumps({"url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(), "sha256": hashlib.sha256(data).hexdigest(), "headers": headers}, indent=2, sort_keys=True) + "\n")
            time.sleep(.36)
            return parsed
        except Exception as exc:
            if attempt == 2:
                print(name, "ERROR", str(exc), flush=True)
                return {"retrieval_error": str(exc), "url": url}
            time.sleep(1 + attempt)

panel = list(csv.DictReader((root / "config/nb04_nto_panel.tsv").open(), delimiter="\t"))
inventory = []
for row in panel:
    oid, name = row["organism_id"], row["scientific_name"]
    taxonomy = get(oid + "_taxonomy", "https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/" + quote(name, safe="") + "/dataset_report")
    exact = [r["taxonomy"] for r in taxonomy.get("reports", []) if r.get("taxonomy", {}).get("current_scientific_name", {}).get("name") == name and r["taxonomy"].get("rank") == "SPECIES"]
    entry = {"organism_id": oid, "scientific_name": name, "ecological_panel_tier": row["ecological_panel_tier"], "preliminary_assessability": row["preliminary_computational_assessability"] or None,
             "taxonomy_status": "EXACT_SPECIES_RESOLVED" if len(exact) == 1 else "UNRESOLVED", "taxid": exact[0]["tax_id"] if len(exact) == 1 else None,
             "taxonomy_report": taxonomy, "assembly_reports": [], "counts": {}}
    if row["taxid"] and entry["taxid"] and int(row["taxid"]) != entry["taxid"]:
        entry["taxonomy_status"] = "INCOMPATIBLE_WITH_PANEL_TAXID"
        raise ValueError(entry)
    if entry["taxid"]:
        token = None
        page = 0
        while True:
            args = {"page_size": 100}
            if token:
                args["page_token"] = token
            response = get(oid + f"_assemblies_{page}", f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{entry['taxid']}/dataset_report?" + urlencode(args))
            if "retrieval_error" in response:
                entry["assembly_inventory_status"] = "RETRIEVAL_FAILED"
                break
            entry["assembly_reports"].extend(response.get("reports", []))
            token = response.get("next_page_token")
            if not token:
                entry["assembly_inventory_status"] = "COMPLETE_QUERIED_NCBI_DATASETS_SNAPSHOT"
                break
            page += 1
        for kind, clause in [("mrna", "biomol_mrna[PROP]"), ("tsa_master", "tsa_master[PROP]")]:
            response = get(oid + "_" + kind, "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urlencode({"db": "nuccore", "term": f"txid{entry['taxid']}[Organism:exp] AND {clause}", "retmode": "json", "retmax": 100}))
            entry["counts"][kind] = response.get("esearchresult")
            if kind == "tsa_master" and response.get("esearchresult", {}).get("idlist"):
                ids = response["esearchresult"]["idlist"]
                entry["tsa_summaries"] = get(oid + "_tsa_summaries", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urlencode({"db": "nuccore", "id": ",".join(ids), "retmode": "json"}))
    inventory.append(entry)
    summary = {"organism_id": oid, "taxid": entry["taxid"], "taxonomy_status": entry["taxonomy_status"], "assemblies": len(entry["assembly_reports"]), "annotated": [a["accession"] for a in entry["assembly_reports"] if a.get("annotation_info")], "counts": {k: v.get("count") if v else None for k, v in entry["counts"].items()}}
    print(json.dumps(summary), flush=True)
    (out / "inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
print("COMPLETE", len(inventory), flush=True)
