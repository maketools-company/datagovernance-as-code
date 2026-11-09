"""Each test copies the repository, breaks one thing, and checks that dgac reports it."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def repo(tmp_path):
    for name in ["governance", "domains", "schemas", "tools", ".github", "CATALOG.md"]:
        src = ROOT / name
        (shutil.copytree if src.is_dir() else shutil.copy)(src, tmp_path / name)
    return tmp_path


def run(repo, command="check"):
    result = subprocess.run([sys.executable, str(repo / "tools" / "dgac.py"), command],
                            capture_output=True, text=True)
    return result.returncode, result.stdout


def edit(repo, path, old, new):
    file = repo / path
    text = file.read_text()
    assert old in text, f"{old!r} not in {path}"
    file.write_text(text.replace(old, new, 1))


def test_example_repository_is_valid(repo):
    code, out = run(repo)
    assert code == 0, out


@pytest.mark.parametrize("path, old, new, expected", [
    ("domains/payments/products/deposits/product.odps.yaml",
     "name: wallet", "name: walet", "unknown team (team.name) 'walet'"),
    ("domains/risk/domain.yaml",
     "  data-steward: paul.vidal@novabank.example\n", "", "required role 'data-steward' has no holder"),
    ("domains/risk/products/credit-score/risk-credit-scores.odcs.yaml",
     "glossary.yaml#credit-score", "glossary.yaml#score", "unknown glossary term 'risk/score'"),
    ("domains/risk/products/credit-score/product.odps.yaml",
     "contractId: payments-deposits", "contractId: payments-deposit", "unknown contract (inputPorts)"),
    ("domains/payments/products/deposits/payments-deposits.odcs.yaml",
     "classification: confidential", "classification: secret", "unknown classification level"),
    ("domains/payments/products/deposits/payments-deposits.odcs.yaml",
     "        classification: confidential\n", "", "column 'amount_eur' has no classification"),
    ("governance/raci.yaml",
     "data-steward: C, data-owner: A", "data-steward: A, data-owner: A", "needs exactly one A"),
    ("governance/policies.yaml",
     "approved_by: data-council", "approved_by: board", "unknown committee 'board'"),
    ("domains/customer/glossary.yaml",
     "related: [payments/transaction]", "related: [payments/transfer]", "unknown glossary term"),
    ("domains/customer/domain.yaml",
     "id: customer", "id: customers", "must match the folder name"),
    ("governance/teams.yaml",
     "lead: marc.dubois", "leader: marc.dubois", "Additional properties are not allowed"),
])
def test_broken_reference_is_reported(repo, path, old, new, expected):
    edit(repo, path, old, new)
    code, out = run(repo)
    assert code == 1
    assert expected in out, out


def test_stale_generated_files_are_reported(repo):
    edit(repo, "domains/payments/domain.yaml", "julien.fabre@", "julia.fabre@")
    code, out = run(repo)
    assert code == 1 and "Out of date" in out
    assert run(repo, "generate")[0] == 0
    assert "julia.fabre@" in (repo / ".github" / "CODEOWNERS").read_text()
    assert run(repo)[0] == 0


def test_active_product_cannot_read_a_proposed_contract(repo):
    edit(repo, "domains/payments/products/deposits/payments-deposits.odcs.yaml",
         "status: active", "status: proposed")
    code, out = run(repo)
    assert code == 1 and "an active product cannot read 'payments-deposits'" in out


def test_new_product_skeleton_passes_checks(repo):
    result = subprocess.run([sys.executable, str(repo / "tools" / "dgac.py"),
                             "new-product", "payments", "daily-balances", "wallet"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert (repo / "domains/payments/products/daily-balances/payments-daily-balances.odcs.yaml").exists()
    assert run(repo, "generate")[0] == 0
    code, out = run(repo)
    assert code == 0, out
