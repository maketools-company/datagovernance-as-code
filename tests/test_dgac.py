"""Tests of the dgac tool on a copy of the example repository.

Fast tests need only Python. Tests marked `dbt` run dbt on DuckDB (a few seconds each).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dgac import cli as dgac  # noqa: E402

DBT = Path(sys.executable).parent / "dbt"
DGAC = Path(sys.executable).parent / "dgac"
needs_dbt = pytest.mark.skipif(not DBT.exists(), reason="dbt is not installed")
ORDERS = "domains/sales/dataproducts/orders"
CUSTOMER = "domains/customer/dataproducts/customer_profile"


@pytest.fixture
def repo_copy(tmp_path) -> Path:
    ignore = shutil.ignore_patterns(".git", ".venv", "data", "build", "target", "logs", "docs", "__pycache__",
                                    ".pytest_cache", "dbt_packages")
    dest = tmp_path / "repo"
    shutil.copytree(ROOT, dest, ignore=ignore)
    return dest


def load(root: Path, path: str):
    return yaml.safe_load((root / path).read_text())


def save(root: Path, path: str, data) -> None:
    (root / path).write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def run(root: Path, *args: str) -> int:
    return dgac.main(["--hub", str(root), *args])


# ---------------------------------------------------------------- the example as shipped

def test_example_is_valid_without_warnings():
    problems = dgac.validate(dgac.Repo(ROOT))
    assert problems.errors == []
    assert problems.warnings == []


def test_generated_files_are_up_to_date():
    for path, text in dgac.generated_files(dgac.Repo(ROOT)).items():
        assert path.read_text(encoding="utf-8") == text, f"{path} is stale: run dgac generate"


def test_codeowners_follow_product_cards():
    text = (ROOT / ".github" / "CODEOWNERS").read_text()
    assert "/domains/sales/dataproducts/orders/  @lumen-retail/sales-data" in text
    assert "/governance/  @lumen-retail/data-governance" in text


def test_dbt_group_takes_owners_from_the_card():
    group = load(ROOT, f"{ORDERS}/_group.yml")["groups"][0]
    assert group["owner"] == {"name": "@lumen-retail/sales-data", "email": "julien.fabre@lumen.example"}
    assert group["config"]["meta"]["data_steward"] == "amelie.roche@lumen.example"


# ---------------------------------------------------------------- validation catches broken files

@pytest.mark.parametrize("break_it, message", [
    (lambda c: c["team"]["members"].pop(1), "card of customer_profile is not valid"),
    (lambda c: c["customProperties"][0].update(value="secret"), "not a level of governance/classification.yaml"),
    (lambda c: c.pop("status"), "card of customer_profile is not valid"),
    (lambda c: c["team"].update(name="customer-data"), "card of customer_profile is not valid"),
])
def test_validate_rejects_a_broken_card(repo_copy, break_it, message):
    path = f"{CUSTOMER}/_data_product.odps.yaml"
    card = load(repo_copy, path)
    break_it(card)
    save(repo_copy, path, card)
    errors = dgac.validate(dgac.Repo(repo_copy)).errors
    assert any(message in e for e in errors), errors


def test_validate_requires_a_card(repo_copy):
    (repo_copy / CUSTOMER / "_data_product.odps.yaml").unlink()
    errors = dgac.validate(dgac.Repo(repo_copy)).errors
    assert any("customer_profile has no product card" in e for e in errors)


def test_validate_checks_contract_version_and_owners(repo_copy):
    path = f"{CUSTOMER}/public/customers_v1.odcs.yaml"
    contract = load(repo_copy, path)
    contract["version"] = "2.0.0"
    contract["team"]["members"][0]["username"] = "someone.else@lumen.example"
    save(repo_copy, path, contract)
    errors = dgac.validate(dgac.Repo(repo_copy)).errors
    assert any("versions of customers and its contract do not match" in e for e in errors)
    assert any("owners in the contract of customers differ" in e for e in errors)


def test_validate_rejects_an_unknown_column_classification(repo_copy):
    path = f"{CUSTOMER}/public/customers_v1.odcs.yaml"
    contract = load(repo_copy, path)
    contract["schema"][0]["properties"][1]["classification"] = "personal"
    save(repo_copy, path, contract)
    errors = dgac.validate(dgac.Repo(repo_copy)).errors
    assert any("Column email of customers is classified 'personal'" in e for e in errors)


def test_validate_rejects_a_bad_target_level(repo_copy):
    gov = load(repo_copy, "domains/sales/governance.yml")
    gov["target_level"] = 4
    save(repo_copy, "domains/sales/governance.yml", gov)
    assert any("governance declaration is not valid" in e for e in dgac.validate(dgac.Repo(repo_copy)).errors)


def test_validate_warns_when_a_domain_pins_another_common_model(repo_copy):
    gov = load(repo_copy, "domains/sales/governance.yml")
    gov["common_semantic_model_version"] = "0.9.0"
    save(repo_copy, "domains/sales/governance.yml", gov)
    problems = dgac.validate(dgac.Repo(repo_copy))
    assert problems.errors == []
    assert any("uses version 0.9.0 of the common semantic model" in w for w in problems.warnings)


# ---------------------------------------------------------------- semantic assembly

def assembly(root: Path):
    repo = dgac.Repo(root)
    d = repo.domain("sales")
    return dgac.assemble_product(repo, d, d.product("orders"))


def test_assembled_model_is_plain_ossie_without_private_semantics():
    a = assembly(ROOT)
    model = a.published["semantic_model"][0]
    names = {m["name"] for m in model["metrics"]}
    assert names == {"revenue", "order_count", "revenue_france", "average_basket"}
    assert "order_margins" not in {ds["name"] for ds in model["datasets"]}
    problems = dgac.Problems()
    assert dgac.Schemas(ROOT / "schemas").check(problems, "x", a.published, "ossie/osi-schema-0.1.1.json", "model"), problems.errors


def test_derived_metric_reuses_the_common_formula():
    model = assembly(ROOT).published["semantic_model"][0]
    metric = next(m for m in model["metrics"] if m["name"] == "revenue_france")
    sql = metric["expression"]["dialects"][0]["expression"]
    assert sql == "SUM(orders.amount) FILTER (WHERE customers.country = 'France')"


def test_a_corrected_common_metric_reaches_its_derived_metrics(repo_copy):
    path = "governance/semantic/common.ossie.yaml"
    common = load(repo_copy, path)
    revenue = next(m for m in common["semantic_model"][0]["metrics"] if m["name"] == "revenue")
    revenue["expression"]["dialects"][0]["expression"] = "SUM(orders.net_amount)"
    common["semantic_model"][0]["datasets"][0]["fields"].append(
        {"name": "net_amount", "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "amount / 1.2"}]}})
    save(repo_copy, path, common)
    model = assembly(repo_copy).published["semantic_model"][0]
    metric = next(m for m in model["metrics"] if m["name"] == "revenue_france")
    assert metric["expression"]["dialects"][0]["expression"].startswith("SUM(orders.net_amount) FILTER")


@pytest.mark.parametrize("change, message", [
    (lambda e: e["metrics"].append({"name": "revenue", "expression": "SUM(orders.amount)"}), "GOV-316"),
    (lambda e: e["metrics"].append({"name": "france_revenue", "derived_from": "revenue",
                                    "filters": [{"field": "customers.country", "equals": "France"}]}), "GOV-318"),
    (lambda e: e["metrics"].append({"name": "average_basket_fr", "derived_from": "average_basket",
                                    "filters": [{"field": "customers.country", "equals": "France"}]}), "GOV-317"),
    (lambda e: e["metrics"].append({"name": "revenue_big", "derived_from": "revenue",
                                    "filters": [{"field": "orders.amount", "equals": 100}]}), "GOV-317"),
    (lambda e: e["metrics"].append({"name": "margin_rate", "expression": "SUM(order_margins.margin)"}), "GOV-315"),
    (lambda e: e["datasets"][0].pop("private"), "GOV-315"),
    (lambda e: e["datasets"].append({"name": "customers", "source": "customer.customers.v1"}), "GOV-316"),
])
def test_assembly_refuses_what_the_standard_forbids(repo_copy, change, message):
    path = f"{ORDERS}/orders.ossie.yaml"
    ext = load(repo_copy, path)
    change(ext)
    save(repo_copy, path, ext)
    with pytest.raises(dgac.AssemblyError, match=message):
        assembly(repo_copy)


def test_dbt_semantic_config_includes_private_metrics():
    config = yaml.safe_load(dgac.dbt_semantic_config(assembly(ROOT))[0])
    metrics = {m["name"]: m for m in config["metrics"]}
    assert "gross_margin" in metrics
    assert metrics["revenue_france"]["filter"] == "{{ Dimension('customers__country') }} = 'France'"
    customers = next(sm for sm in config["semantic_models"] if sm["name"] == "customers")
    assert customers["model"] == "ref('customer__customers')"   # read through the consumer zone


# ---------------------------------------------------------------- manifest

def test_manifest_derives_consumers_and_inputs(repo_copy):
    assert run(repo_copy, "manifest") == 0
    customer = json.loads((repo_copy / "build/customer/governance-manifest.json").read_text())
    sales = json.loads((repo_copy / "build/sales/governance-manifest.json").read_text())
    assert customer["products"][0]["consumers"] == [{"domain": "sales", "product": "orders"}]
    orders = sales["products"][0]
    assert orders["reads_from"][0]["contractId"] == "customer-customers-v1"
    assert orders["semantic"]["private_metrics"] == ["gross_margin"]
    odps_schema = json.loads((ROOT / "schemas/bitol/odps-json-schema-v1.1.0.json").read_text())
    problems = dgac.Problems()
    for product in (customer["products"][0], orders):
        assert dgac.Schemas(ROOT / "schemas").check(problems, "x", product["odps"],
                                                     "bitol/odps-json-schema-v1.1.0.json", "odps"), problems.errors
    assert odps_schema  # the exported card carries derived ports
    assert orders["odps"]["inputPorts"][0]["contractId"] == "customer-customers-v1"


# ---------------------------------------------------------------- scaffolding

def test_new_domain_and_product_are_valid_by_construction(repo_copy):
    assert run(repo_copy, "new-domain", "inventory", "--team", "@lumen-retail/inventory-data") == 0
    assert run(repo_copy, "new-product", "inventory", "daily_stock", "--team", "@lumen-retail/stock",
               "--owner", "nina.roux@lumen.example", "--steward", "omar.diallo@lumen.example") == 0
    assert run(repo_copy, "new-interface", "inventory", "daily_stock", "stock_levels") == 0
    repo = dgac.Repo(repo_copy)
    problems = dgac.validate(repo)
    assert problems.errors == []
    assert dgac.generate(repo, check=True) == 0
    assert (repo_copy / "governance/glossary/inventory.yaml").exists()
    assert "/domains/inventory/dataproducts/daily_stock/  @lumen-retail/stock" in \
           (repo_copy / ".github/CODEOWNERS").read_text()
    project = load(repo_copy, "domains/inventory/dbt_project.yml")
    assert project["models"]["inventory"]["daily_stock"]["+group"] == "daily_stock"


def test_new_product_refuses_bad_names(repo_copy):
    assert run(repo_copy, "new-product", "sales", "Daily-Stock", "--team", "@lumen-retail/x",
               "--owner", "a@lumen.example", "--steward", "b@lumen.example") == 1


def test_new_domain_repository(repo_copy, tmp_path):
    out = tmp_path / "repos"
    out.mkdir()
    assert run(repo_copy, "new-domain", "marketing", "--team", "@lumen-retail/marketing-data", "--repo", str(out)) == 0
    domain = out / "data-dbt-marketing"
    assert (domain / ".github/workflows/validate.yml").exists()
    assert (domain / ".github/CODEOWNERS").read_text().splitlines()[4] == "*  @lumen-retail/marketing-data"
    assert dgac.main(["--hub", str(repo_copy), "--domain", str(domain), "validate"]) == 0


# ---------------------------------------------------------------- with dbt

@needs_dbt
def test_new_domain_parses_in_dbt_without_warnings(repo_copy):
    run(repo_copy, "new-domain", "inventory", "--team", "@lumen-retail/inventory-data")
    run(repo_copy, "new-product", "inventory", "daily_stock", "--team", "@lumen-retail/stock",
        "--owner", "nina.roux@lumen.example", "--steward", "omar.diallo@lumen.example")
    result = subprocess.run([str(DBT), "parse", "--no-partial-parse"], cwd=repo_copy / "domains/inventory",
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "WARN" not in result.stdout, result.stdout


@needs_dbt
def test_build_then_compute_a_published_metric(repo_copy):
    assert run(repo_copy, "build") == 0
    assert run(repo_copy, "assemble") == 0
    doc = yaml.safe_load((repo_copy / "build/semantic/sales/orders.assembled.ossie.yaml").read_text())
    model = doc["semantic_model"][0]
    sources = {ds["name"]: ds["source"] for ds in model["datasets"]}
    assert sources == {"orders": "warehouse.sales.orders_v1", "customers": "warehouse.customer.customers_v1"}
    metric = next(m for m in model["metrics"] if m["name"] == "revenue_france")
    expression = metric["expression"]["dialects"][0]["expression"]
    import duckdb
    con = duckdb.connect(str(repo_copy / "build/warehouse.duckdb"), read_only=True)
    sql = (f"select {expression} from {sources['orders']} as orders "
           f"join {sources['customers']} as customers on orders.customer_id = customers.customer_id")
    assert float(con.execute(sql).fetchone()[0]) == pytest.approx(759.90)


# ---------------------------------------------------------------- dgac init and the installed command

def test_init_removes_the_example_and_sets_the_hub_up(repo_copy):
    assert run(repo_copy, "init", "--organisation", "Acme", "--central-team", "@acme/data-governance") == 0
    assert not (repo_copy / "domains/customer").exists()
    assert not (repo_copy / "governance/glossary/sales.yaml").exists()
    assert not (repo_copy / "governance/semantic/common.ossie.yaml").exists()
    hub = load(repo_copy, "governance/hub.yml")
    assert hub["organisation"] == "Acme" and hub["central_team"] == "@acme/data-governance"
    codeowners = (repo_copy / ".github/CODEOWNERS").read_text()
    assert "/governance/  @acme/data-governance" in codeowners and "lumen" not in codeowners
    repo = dgac.Repo(repo_copy)
    assert dgac.validate(repo).errors == []
    assert dgac.generate(repo, check=True) == 0
    # the company can start at once
    assert run(repo_copy, "new-domain", "finance", "--team", "@acme/finance-data") == 0
    assert dgac.validate(dgac.Repo(repo_copy)).errors == []


def test_init_refuses_a_repository_already_set_up(repo_copy):
    assert run(repo_copy, "init", "--organisation", "Acme", "--central-team", "@acme/data-governance") == 0
    assert run(repo_copy, "new-domain", "finance", "--team", "@acme/finance-data") == 0
    assert run(repo_copy, "init", "--organisation", "Other", "--central-team", "@other/gov") == 1
    assert (repo_copy / "domains/finance").exists()


def test_an_extension_needs_the_common_model(repo_copy):
    (repo_copy / "governance/semantic/common.ossie.yaml").unlink()
    with pytest.raises(dgac.AssemblyError, match="does not exist yet"):
        assembly(repo_copy)


def test_schemas_ship_with_the_package(repo_copy):
    shutil.rmtree(repo_copy / "schemas")          # a hub or domain repository without its own copy
    assert dgac.schemas_folder(repo_copy).exists()
    assert dgac.validate(dgac.Repo(repo_copy)).errors == []


@pytest.mark.skipif(not DGAC.exists(), reason="dgac is not installed (pip install -e .)")
def test_installed_command_finds_the_hub_from_a_subfolder():
    result = subprocess.run([str(DGAC), "validate"], cwd=ROOT / "domains/sales/dataproducts",
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 domains, 2 data products" in result.stdout
