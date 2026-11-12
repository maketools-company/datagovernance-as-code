# Data Governance as Code

Your data governance rules, written as files in the repository where your data teams already work, and checked on every pull request.
Who owns each data product, what other domains may use, what is promised to them, what the shared metrics mean.

This repository is a template and the reference implementation of the [standard](STANDARD.md).
Its example is Lumen Retail, a fictional home-goods retailer with two data domains: **Customer** and **Sales**.
Sales reads Customer's public interface and derives `revenue_france` from the company's common definition of `revenue`.

## Try it

```bash
pip install -r requirements.txt
python tools/dgac.py validate      # every governance file against its schema
python tools/dgac.py build         # dbt builds each data product on its own, producers first (local DuckDB)
python tools/dgac.py assemble      # common semantic model + each product's extension → plain Ossie
python tools/dgac.py manifest      # build/<domain>/governance-manifest.json
```

Open `build/sales/governance-manifest.json`: owners, interfaces, contracts, what Sales reads from Customer, its shared and private metrics.

## What's inside

```
governance/                     the hub, kept by the central data governance team
  hub.yml                       central team, standard version, common semantic model version
  classification.yaml           sensitivity levels: public, internal, confidential, restricted
  glossary/{domain}.yaml        business terms, one file per domain
  semantic/common.ossie.yaml    metrics and dimensions the whole company shares (Apache Ossie)

domains/{domain}/               one dbt project per domain (or one repository: data-dbt-{domain})
  governance.yml                standard version, target level, domain team, pinned versions
  external/                     consumer zone: the only place another domain's data enters
  dataproducts/{product}/       producer zone: one folder = one data product = one dbt group
    _data_product.odps.yaml     product card (ODPS): owners, status, classification, personal data
    staging/ silver/ gold/      internal layers, private
    public/                     public interface: {interface}_v1.sql + its contract {interface}_v1.odcs.yaml
    {product}.ossie.yaml        semantic extension: the product's metrics, derived from the common ones

schemas/                        what CI validates (the standard's schemas, ODCS, ODPS, Ossie)
tools/dgac.py                   the standard's tool
STANDARD.md · RULES.md          the standard and its 37 rules
```

Files marked `Generated` in their first line come from the cards and extensions: `.github/CODEOWNERS`, `_group.yml`, `selectors.yml`, `_semantic.generated.yml`. Run `python tools/dgac.py generate` after an edit; CI fails if they are stale.

## For domain teams

**What the standard asks.** Each domain declares a target level in `governance.yml`. Level 1 rules always block a pull request; levels 2 and 3 block once you target them. The governance committee sets a floor and a deadline.

| Level | What it guarantees |
| --- | --- |
| 1. Identified | Every data product has a folder, a card, a Data Owner, a Steward and a tech owner |
| 2. Isolated | Other domains see only `public/`; everything from other domains enters through `external/` |
| 3. Under contract | Public interfaces are versioned, under an ODCS contract, described, classified and fresh |

The template declares level 1. Its two example products meet level 3.

**Add a data product.**

```bash
python tools/dgac.py new-product sales returns --team @lumen-retail/sales-data \
    --owner julien.fabre@lumen.example --steward amelie.roche@lumen.example
```

Fill in the purpose, classification and `containsPii` in the card, then write your models in `staging/`, `silver/` and `gold/`.
Shared macros and seeds carry the product's prefix: `returns__...`.

**Publish an interface.** `python tools/dgac.py new-interface sales returns refunds` creates `public/refunds_v1.sql`, `refunds.yml` and the contract `refunds_v1.odcs.yaml` (status `proposed`). The contract is the source of truth: the dbt columns follow it. A new public interface needs the Data Owner's approval (GOV-A01).

**Change an interface.** Adding a column or improving a description is a minor change: raise the contract's minor version. Removing, renaming or retyping a column breaks consumers:

1. add `{interface}_v2.sql` and `- v: 2` in the model's YAML, and a contract `{interface}_v2.odcs.yaml` at version `2.0.0`;
2. set the v1 contract to `status: deprecated` with an `endOfLife` at least 3 months later (`slaProperties`);
3. get the Data Owner's approval (GOV-A02) and tell the consuming domains (the manifest lists them);
4. delete v1 after its end of life, once no domain reads it.

**Read another domain.** Add a model in `external/{domain}/` that selects from `ref('{domain}', '{interface}', v=1)`, attach it to your product's group, and declare the producer's manifest in `dbt_loom.config.yml`. dbt refuses references to private models of another domain.

**Add metrics.** Write `{product}.ossie.yaml`. Derive from a common metric rather than copying its formula:

```yaml
metrics:
  - name: revenue_france          # starts with its parent's name
    derived_from: revenue
    filters: [{field: customers.country, equals: France}]
```

Metrics built on internal layers are `private: true`: the domain computes them, other domains never see them. Changing the common model needs the governance committee (GOV-A04).

## One repository per domain

The monorepo is the easiest way to start. A federated company keeps the hub in its own repository and gives each domain a repository with the same layout:

```bash
python tools/dgac.py new-domain marketing --team @lumen-retail/marketing-data --repo ../
# → ../data-dbt-marketing, with a CI that checks out the hub at the pinned version
```

## Built on standards

| For | We use |
| --- | --- |
| Product cards | [ODPS v1.1.0](https://bitol-io.github.io/open-data-product-standard/) (Bitol, Linux Foundation), with the standard's profile |
| Data contracts | [ODCS v3.2.0](https://bitol-io.github.io/open-data-contract-standard/) (Bitol, Linux Foundation) |
| Shared semantics | [Apache Ossie 0.1.1](https://github.com/apache/ossie) (incubating), formerly Open Semantic Interchange |
| Transformations, ownership, interfaces | dbt groups, model access, model versions and contracts; [dbt-loom](https://github.com/nicholasyager/dbt-loom) for cross-project references with dbt Core |
| Review | GitHub CODEOWNERS |


## License

[Apache 2.0](LICENSE)
