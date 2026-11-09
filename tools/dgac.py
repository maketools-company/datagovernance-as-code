#!/usr/bin/env python3
"""Data Governance as Code: check the repository and generate CODEOWNERS and CATALOG.md.

    python tools/dgac.py check      # validate everything, fail if generated files are stale (CI)
    python tools/dgac.py generate   # rewrite .github/CODEOWNERS and CATALOG.md
    python tools/dgac.py new-product <domain> <product-id> <team-id>   # create a product skeleton

Checks, in order:
  1. every YAML file matches its JSON Schema (ours in schemas/, Bitol's for ODCS and ODPS)
  2. every reference points to something that exists (roles, teams, domains, terms,
     classification levels, contracts, committees)
  3. governance rules: required roles are filled, each RACI activity has exactly one A
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import validators

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
GOVERNANCE_FILES = ["organization", "roles", "teams", "classification", "policies", "committees", "raci"]
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
CATALOG = ROOT / "CATALOG.md"


# ---------------------------------------------------------------- loading

class _Loader(yaml.SafeLoader):
    """Safe loader that keeps dates as strings, as JSON Schema expects."""


_Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.load(f, Loader=_Loader) or {}


@dataclass
class Product:
    domain: str
    folder: Path
    product: dict
    contracts: dict[str, dict] = field(default_factory=dict)  # contract id -> ODCS document


@dataclass
class Repo:
    gov: dict[str, dict] = field(default_factory=dict)
    domains: dict[str, dict] = field(default_factory=dict)
    glossaries: dict[str, list] = field(default_factory=dict)  # domain id -> terms
    products: list[Product] = field(default_factory=list)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


# ---------------------------------------------------------------- checker

class Checker:
    def __init__(self):
        self.errors: list[str] = []
        self.repo = Repo()
        self._validators: dict[str, object] = {}

    def error(self, where: Path | str, message: str) -> None:
        self.errors.append(f"{rel(where) if isinstance(where, Path) else where}: {message}")

    # 1. schemas ---------------------------------------------------------
    def _validator(self, schema_file: Path):
        key = str(schema_file)
        if key not in self._validators:
            schema = json.loads(schema_file.read_text(encoding="utf-8"))
            cls = validators.validator_for(schema)
            self._validators[key] = cls(schema, format_checker=cls.FORMAT_CHECKER)
        return self._validators[key]

    def validate(self, path: Path, schema_file: Path) -> dict | None:
        try:
            doc = load_yaml(path)
        except yaml.YAMLError as e:
            self.error(path, f"invalid YAML: {e}")
            return None
        for err in sorted(self._validator(schema_file).iter_errors(doc), key=lambda e: list(e.path)):
            location = "/".join(str(p) for p in err.path) or "(root)"
            self.error(path, f"{location}: {err.message}")
        return doc

    def load(self) -> None:
        for name in GOVERNANCE_FILES:
            path = ROOT / "governance" / f"{name}.yaml"
            if not path.exists():
                self.error(path, "missing file")
                self.repo.gov[name] = {}
                continue
            self.repo.gov[name] = self.validate(path, SCHEMAS / f"{name}.schema.json") or {}

        for folder in sorted(p for p in (ROOT / "domains").iterdir() if p.is_dir()):
            domain_file = folder / "domain.yaml"
            if not domain_file.exists():
                self.error(folder, "a domain folder needs a domain.yaml")
                continue
            domain = self.validate(domain_file, SCHEMAS / "domain.schema.json") or {}
            if domain.get("id") != folder.name:
                self.error(domain_file, f"id '{domain.get('id')}' must match the folder name '{folder.name}'")
            self.repo.domains[folder.name] = domain

            glossary_file = folder / "glossary.yaml"
            if glossary_file.exists():
                glossary = self.validate(glossary_file, SCHEMAS / "glossary.schema.json") or {}
                self.repo.glossaries[folder.name] = glossary.get("terms", [])

            for product_folder in sorted(p for p in (folder / "products").glob("*") if p.is_dir()):
                odps = product_folder / "product.odps.yaml"
                if not odps.exists():
                    self.error(product_folder, "a product folder needs a product.odps.yaml")
                    continue
                product = Product(folder.name, product_folder,
                                  self.validate(odps, SCHEMAS / "bitol" / "odps-json-schema-v1.1.0.json") or {})
                for odcs in sorted(product_folder.glob("*.odcs.yaml")):
                    contract = self.validate(odcs, SCHEMAS / "bitol" / "odcs-json-schema-v3.2.0.json") or {}
                    if contract.get("id") != odcs.name.removesuffix(".odcs.yaml"):
                        self.error(odcs, f"id '{contract.get('id')}' must match the file name")
                    product.contracts[contract.get("id")] = contract
                self.repo.products.append(product)

    # 2 and 3. references and rules -------------------------------------
    def references(self) -> None:
        g, r = self.repo.gov, self.repo
        roles = {x["id"]: x for x in g["roles"].get("roles", [])}
        org_roles = {k for k, v in roles.items() if v["scope"] == "organization"}
        domain_roles = {k for k, v in roles.items() if v["scope"] == "domain"}
        teams = {x["id"]: x for x in g["teams"].get("teams", [])}
        levels = {x["id"]: x for x in g["classification"].get("levels", [])}
        committees = {x["id"] for x in g["committees"].get("committees", [])}
        terms = {f"{d}/{t['id']}" for d, ts in r.glossaries.items() for t in ts}
        contracts = {cid: p for p in r.products for cid in p.contracts}
        gov = ROOT / "governance"

        def check_ids(items, what, path):
            seen = set()
            for item in items:
                if item["id"] in seen:
                    self.error(path, f"duplicate {what} id '{item['id']}'")
                seen.add(item["id"])

        def must_exist(value, known, what, path):
            if value not in known:
                self.error(path, f"unknown {what} '{value}'. Known: {', '.join(sorted(known)) or 'none'}")

        for name, key in [("roles", "roles"), ("teams", "teams"), ("classification", "levels"),
                          ("policies", "policies"), ("committees", "committees"), ("raci", "activities")]:
            check_ids(g[name].get(key, []), key.rstrip("s"), gov / f"{name}.yaml")

        # organization: every organization role is held by someone
        for role_id in g["organization"].get("roles", {}):
            must_exist(role_id, org_roles, "organization role", gov / "organization.yaml")
        for role_id in org_roles - set(g["organization"].get("roles", {})):
            self.error(gov / "organization.yaml", f"role '{role_id}' has no holder")

        for team in teams.values():
            if "parent" in team:
                must_exist(team["parent"], teams, "parent team", gov / "teams.yaml")
        for level in levels.values():
            for reviewer in level.get("reviewers", []):
                must_exist(reviewer, org_roles, "organization role", gov / "classification.yaml")
        for policy in g["policies"].get("policies", []):
            path = gov / "policies.yaml"
            must_exist(policy["owner"], roles, "role", path)
            for level in policy.get("applies_to", []):
                must_exist(level, levels, "classification level", path)
            if "approved_by" in policy:
                must_exist(policy["approved_by"], committees, "committee", path)
        for committee in g["committees"].get("committees", []):
            for role_id in [committee["chair"], *committee["members"]]:
                must_exist(role_id, roles, "role", gov / "committees.yaml")
        for activity in g["raci"].get("activities", []):
            path = gov / "raci.yaml"
            for role_id in activity["raci"]:
                must_exist(role_id, {*roles, "team"}, "role", path)
            accountable = [k for k, v in activity["raci"].items() if v == "A"]
            if len(accountable) != 1:
                self.error(path, f"activity '{activity['id']}' needs exactly one A, found {len(accountable)}")

        # domains
        for domain_id, domain in r.domains.items():
            path = ROOT / "domains" / domain_id / "domain.yaml"
            if "parent" in domain:
                must_exist(domain["parent"], r.domains, "parent domain", path)
            for team_id in domain.get("teams", []):
                must_exist(team_id, teams, "team", path)
            for role_id in domain.get("roles", {}):
                must_exist(role_id, domain_roles, "domain role", path)
            for role_id in sorted(domain_roles):
                if roles[role_id].get("required") and role_id not in domain.get("roles", {}):
                    self.error(path, f"required role '{role_id}' has no holder")

        # glossaries
        for domain_id, domain_terms in r.glossaries.items():
            path = ROOT / "domains" / domain_id / "glossary.yaml"
            check_ids(domain_terms, "term", path)
            for term in domain_terms:
                for link in term.get("related", []):
                    must_exist(link, terms, "glossary term", path)

        # products and contracts
        seen_products: set[str] = set()
        for p in r.products:
            odps = p.folder / "product.odps.yaml"
            if p.product.get("id") in seen_products:
                self.error(odps, f"duplicate product id '{p.product.get('id')}'")
            seen_products.add(p.product.get("id"))
            if p.product.get("id") != p.folder.name:
                self.error(odps, f"id '{p.product.get('id')}' must match the folder name '{p.folder.name}'")
            if p.product.get("domain") != p.domain:
                self.error(odps, f"domain must be '{p.domain}' (the folder it lives in)")
            must_exist(p.product.get("team", {}).get("name"), teams, "team (team.name)", odps)

            exposed = set()
            for port in p.product.get("outputPorts", []):
                cid = port.get("contractId")
                if cid not in p.contracts:
                    self.error(odps, f"output port '{port.get('name')}' points to '{cid}', "
                                     f"which is not a contract in {rel(p.folder)}/")
                exposed.add(cid)
            for port in p.product.get("inputPorts", []):
                cid = port.get("contractId")
                must_exist(cid, contracts, "contract (inputPorts)", odps)
                status = contracts[cid].contracts[cid].get("status") if cid in contracts else None
                if p.product.get("status") == "active" and status and status != "active":
                    self.error(odps, f"an active product cannot read '{cid}', whose contract is '{status}'. "
                                     f"Activate that contract first, or set this product to 'proposed'")

            for cid, contract in p.contracts.items():
                odcs = p.folder / f"{cid}.odcs.yaml"
                if cid not in exposed:
                    self.error(odcs, "no output port of product.odps.yaml exposes this contract")
                if contract.get("domain") != p.domain:
                    self.error(odcs, f"domain must be '{p.domain}' (the folder it lives in)")
                if "team" in contract:
                    must_exist(contract["team"].get("id"), teams, "team (team.id)", odcs)
                for element in walk(contract.get("schema", [])):
                    name = element.get("name", "?")
                    if "classification" in element:
                        must_exist(element["classification"], levels, f"classification level on '{name}'", odcs)
                    elif "logicalType" in element and element["logicalType"] != "object":
                        self.error(odcs, f"column '{name}' has no classification")
                    for definition in element.get("authoritativeDefinitions", []):
                        if definition.get("type") == "glossary":
                            must_exist(glossary_ref(definition.get("url", "")), terms, "glossary term", odcs)
        dupes = [cid for cid in contracts if sum(cid in p.contracts for p in r.products) > 1]
        for cid in dupes:
            self.error("domains/", f"contract id '{cid}' is used twice")

    def run(self) -> list[str]:
        self.load()
        if self.errors:  # references only make sense on well-formed files
            self.errors.append("(references are checked once these schema errors are fixed)")
        else:
            self.references()
        self.errors = list(dict.fromkeys(self.errors))  # drop duplicates, keep order
        return self.errors


def walk(elements):
    """Yield every schema object and property of an ODCS contract, nested ones included."""
    for element in elements or []:
        yield element
        yield from walk(element.get("properties"))
        if isinstance(element.get("items"), dict):
            yield from walk([element["items"]])


def glossary_ref(url: str) -> str:
    """'domains/payments/glossary.yaml#deposit' -> 'payments/deposit'."""
    path, _, term = url.partition("#")
    parts = path.split("/")
    if len(parts) == 3 and parts[0] == "domains" and parts[2] == "glossary.yaml" and term:
        return f"{parts[1]}/{term}"
    return url


# ---------------------------------------------------------------- generation

def products_needing_review(repo: Repo, levels: dict) -> dict[str, set[str]]:
    """Product folder -> organization roles that must review it, from classification reviewers."""
    out: dict[str, set[str]] = {}
    for p in repo.products:
        reviewers = set()
        for contract in p.contracts.values():
            for element in walk(contract.get("schema", [])):
                reviewers.update(levels.get(element.get("classification"), {}).get("reviewers", []))
        out[rel(p.folder)] = reviewers
    return out


def render_codeowners(repo: Repo) -> str:
    g = repo.gov
    roles = g["roles"]["roles"]
    org = g["organization"]
    levels = {lv["id"]: lv for lv in g["classification"]["levels"]}
    review = products_needing_review(repo, levels)

    def holders(domain: dict, scope_key: str) -> list[str]:
        people = []
        for role in roles:
            if scope_key in role.get("approves", []):
                person = (domain["roles"] if role["scope"] == "domain" else org["roles"]).get(role["id"])
                if person and person not in people:
                    people.append(person)
        return people

    lines = ["# Generated by tools/dgac.py from governance/ and domains/. Do not edit by hand.",
             "# Who must approve a pull request, per path. The last matching line wins.", ""]
    gov_owners = holders({"roles": {}}, "governance") + ([org["governance_team"]] if org.get("governance_team") else [])
    lines += [f"*  {' '.join(gov_owners)}", f"/governance/  {' '.join(gov_owners)}", ""]

    for domain_id, domain in repo.domains.items():
        base = f"/domains/{domain_id}"
        lines.append(f"{base}/  {' '.join(holders(domain, 'domain'))}")
        lines.append(f"{base}/glossary.yaml  {' '.join(holders(domain, 'glossary'))}")
        for p in [p for p in repo.products if p.domain == domain_id]:
            # The delivery team writes the change; it is not listed, so it cannot approve its own PR.
            owners = holders(domain, "products")
            owners += [org["roles"][r] for r in sorted(review[rel(p.folder)]) if r in org["roles"]]
            lines.append(f"/{rel(p.folder)}/  {' '.join(dict.fromkeys(owners))}")
        lines.append("")
    return "\n".join(lines)


def render_catalog(repo: Repo) -> str:
    g = repo.gov
    org = g["organization"]
    roles = {r["id"]: r for r in g["roles"]["roles"]}
    teams = {t["id"]: t for t in g["teams"]["teams"]}
    levels = {lv["id"]: lv for lv in g["classification"]["levels"]}
    order = list(levels)
    contracts = {cid: p for p in repo.products for cid in p.contracts}

    def cell(text) -> str:
        return " ".join(str(text).split()).replace("|", "\\|")

    out = [f"# {org['name']}: data governance catalog", "",
           "_Generated by `python tools/dgac.py generate`. Do not edit by hand: edit the YAML files._", "",
           "## Who decides", "", "| Role | Holder |", "|---|---|"]
    out += [f"| {roles[r]['name']} | {p} |" for r, p in org["roles"].items()]

    out += ["", "## Domains", "", "| Domain | Description | Owner | Steward | Teams |", "|---|---|---|---|---|"]
    for d_id, d in repo.domains.items():
        out.append(f"| [{d['name']}](domains/{d_id}/domain.yaml) | {cell(d['description'])} | "
                   f"{d['roles'].get('data-owner', '')} | {d['roles'].get('data-steward', '')} | "
                   f"{', '.join(teams[t]['name'] for t in d.get('teams', []) if t in teams)} |")

    out += ["", "## Data products", "",
            "| Product | Domain | Team | Contracts | Reads from | Most sensitive data |", "|---|---|---|---|---|---|"]
    for p in repo.products:
        found = {e.get("classification") for c in p.contracts.values() for e in walk(c.get("schema", []))}
        top = max((lv for lv in found if lv in levels), key=order.index, default="")
        inputs = [f"{contracts[i['contractId']].product['name']}" for i in p.product.get("inputPorts", [])
                  if i.get("contractId") in contracts]
        out.append(f"| [{p.product['name']}]({rel(p.folder)}/product.odps.yaml) | {repo.domains[p.domain]['name']} | "
                   f"{teams.get(p.product['team']['name'], {}).get('name', '')} | "
                   f"{', '.join(f'[{c}]({rel(p.folder)}/{c}.odcs.yaml)' for c in p.contracts)} | "
                   f"{', '.join(inputs)} | {levels[top]['name'] if top else ''} |")

    out += ["", "## Glossary", "", "| Term | Domain | Definition | Status |", "|---|---|---|---|"]
    for d_id, terms in repo.glossaries.items():
        for t in terms:
            out.append(f"| {t['name']} | {repo.domains[d_id]['name']} | {cell(t['definition'])} | {t['status']} |")

    out += ["", "## Policies", "", "| Policy | Applies to | Owner |", "|---|---|---|"]
    for pol in g["policies"]["policies"]:
        out.append(f"| **{pol['title']}**. {cell(pol['statement'])} | "
                   f"{', '.join(levels[x]['name'] for x in pol.get('applies_to', []))} | {roles[pol['owner']]['name']} |")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- scaffolding

PRODUCT_TEMPLATE = """\
apiVersion: v1.1.0
kind: DataProduct
id: {product}
name: {name}
version: 0.1.0
status: proposed          # becomes active once the domain owner approves
domain: {domain}
type: sourceAligned       # or aggregate, consumerAligned
team:
  name: {team}

description:
  purpose: TODO what this product is for.

# inputPorts:             # products this one reads from
#   - name: deposits
#     version: 2.0.0      # the version of that contract
#     contractId: payments-deposits

outputPorts:
  - name: {product}
    version: 0.1.0
    contractId: {contract}
"""

CONTRACT_TEMPLATE = """\
apiVersion: v3.2.0
kind: DataContract
id: {contract}
name: {name}
version: 0.1.0
status: proposed
domain: {domain}
team:
  id: {team}

description:
  purpose: TODO what consumers can do with this data.

schema:
  - name: {table}
    physicalType: table
    description: TODO one row per ...
    properties:
      - name: TODO_id
        logicalType: string     # string, number, integer, boolean, date, timestamp
        primaryKey: true
        required: true
        classification: internal   # a level from governance/classification.yaml
"""


def new_product(domain: str, product: str, team: str) -> int:
    folder = ROOT / "domains" / domain / "products" / product
    if not (ROOT / "domains" / domain / "domain.yaml").exists():
        print(f"Unknown domain '{domain}'. Create domains/{domain}/domain.yaml first.")
        return 1
    if folder.exists():
        print(f"{rel(folder)} already exists.")
        return 1
    values = {"domain": domain, "product": product, "team": team, "contract": f"{domain}-{product}",
              "name": product.replace("-", " ").capitalize(), "table": product.replace("-", "_")}
    folder.mkdir(parents=True)
    (folder / "product.odps.yaml").write_text(PRODUCT_TEMPLATE.format(**values), encoding="utf-8")
    (folder / f"{values['contract']}.odcs.yaml").write_text(CONTRACT_TEMPLATE.format(**values), encoding="utf-8")
    print(f"Created {rel(folder)}/ with product.odps.yaml and {values['contract']}.odcs.yaml.\n"
          f"Fill in the TODOs, then run: python tools/dgac.py generate && python tools/dgac.py check")
    return 0


# ---------------------------------------------------------------- CLI

def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "check"
    if command == "new-product" and len(argv) == 5:
        return new_product(*argv[2:5])
    if command not in ("check", "generate"):
        print(__doc__)
        return 2
    checker = Checker()
    errors = checker.run()
    if errors:
        print(f"{len(errors)} problem(s) found:\n")
        print("\n".join(f"  - {e}" for e in errors))
        return 1

    generated = {CODEOWNERS: render_codeowners(checker.repo), CATALOG: render_catalog(checker.repo)}
    if command == "generate":
        for path, content in generated.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"wrote {rel(path)}")
        return 0

    stale = [rel(p) for p, c in generated.items() if not p.exists() or p.read_text(encoding="utf-8") != c]
    if stale:
        print(f"Out of date: {', '.join(stale)}. Run: python tools/dgac.py generate")
        return 1
    print(f"OK: {len(checker.repo.domains)} domains, {len(checker.repo.products)} data products, "
          f"{sum(len(p.contracts) for p in checker.repo.products)} contracts.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
