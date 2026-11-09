# Data Governance as Code

Your data governance in plain YAML files: domains, owners, glossary, data contracts, policies.
Changed by pull request, checked by CI, readable by people and AI agents.

**See the result first: [CATALOG.md](CATALOG.md)**, generated from the example company, Nova Bank.

## What's inside

```
governance/                  company-wide rules
  organization.yaml          the company and its CDO, DPO, head of governance
  roles.yaml                 data owner, steward... and what each one approves
  teams.yaml                 who builds and runs the data
  classification.yaml        public, internal, confidential, personal...
  policies.yaml              rules everyone follows
  committees.yaml            who decides together, and how often
  raci.yaml                  who does what

domains/
  payments/                  one folder per business domain
    domain.yaml              owner, steward, teams
    glossary.yaml            the domain's business terms
    products/
      deposits/              one folder per data product
        product.odps.yaml        the product (ODPS standard)
        payments-deposits.odcs.yaml  its data contract (ODCS standard)

CATALOG.md                   generated: everything above, as tables
.github/CODEOWNERS           generated: who approves which file
```

## How a change happens

1. Someone asks for it with an [issue form](.github/ISSUE_TEMPLATE): new owner, new term, new data product.
2. A data engineer, or an AI agent, turns the request into a pull request.
3. CI checks that every reference exists and every rule is met.
4. The right people approve: the domain's owner, or the DPO when personal data is involved. The team that wrote the change cannot approve it. Generated from `roles.yaml`.
5. Merge. The catalog is up to date.

## Use it

Click **Use this template** on GitHub, then:

```bash
pip install -r requirements.txt
python tools/dgac.py check       # what CI runs
python tools/dgac.py generate    # after an edit: refresh CATALOG.md and CODEOWNERS
python tools/dgac.py new-product payments daily-balances wallet   # start a new data product
```

Replace Nova Bank with your company: edit `governance/`, rename the folders in `domains/`, run `generate`.
For CODEOWNERS to work, people must be GitHub handles (`@jdoe`) or emails verified on GitHub.
Turn on "Require review from Code Owners" in the branch protection of `main`.
Start small: 3 domains and 5 data products are enough to be useful.

## What CI checks

- Every file matches its schema. Typos in field names fail.
- Every reference exists: teams, roles, domains, glossary terms, classification levels, contracts.
- Every domain has a holder for each required role.
- Every column of a contract is classified.
- Every RACI activity has exactly one person accountable.
- `CATALOG.md` and `CODEOWNERS` are up to date.

## Built on standards

| For | We use |
|---|---|
| Data contracts | [ODCS v3.2.0](https://bitol-io.github.io/open-data-contract-standard/) (Bitol, Linux Foundation) |
| Data products | [ODPS v1.1.0](https://bitol-io.github.io/open-data-product-standard/) (Bitol, Linux Foundation) |
| Personal data categories | [W3C Data Privacy Vocabulary](https://w3id.org/dpv) |
| Domains, roles, teams, glossary, policies | Simple YAML, schemas in [schemas/](schemas/): no open standard covers them yet |

## License

[Apache 2.0](LICENSE)
