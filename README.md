# Data Governance as Code

Your data governance rules, written as files in the repository where your data teams already work, and checked on every pull request.
Who owns each data product, what other domains may use, what is promised to them, what the shared metrics mean.

This repository is a template and the reference implementation of the [standard](STANDARD.md).
Its example is Lumen Retail, a fictional home-goods retailer with two data domains: **Customer** and **Sales**.
Sales reads Customer's public interface and derives `revenue_france` from the company's common definition of `revenue`.

## Try it

```bash
pip install -e ".[dbt]"   # installs the `dgac` command, with dbt Core, DuckDB and dbt-loom
dgac validate             # every governance file against its schema
dgac build                # dbt builds each data product on its own, producers first (local DuckDB)
dgac assemble             # common semantic model + each product's extension → plain Ossie
dgac manifest             # build/<domain>/governance-manifest.json
```

Open `build/sales/governance-manifest.json`: owners, interfaces, contracts, what Sales reads from Customer, its shared and private metrics.
`dgac` works from any folder of the repository. `dgac --help` lists every command.

## Use it for your company

1. Click **Use this template** on GitHub, clone your new repository and install the tool as above.
2. Remove the example and set the hub up:

   ```bash
   dgac init --organisation "Acme" --central-team @acme/data-governance
   ```

   This deletes the Lumen Retail domains, their glossaries and the example's common semantic model, and regenerates CODEOWNERS.
3. Review the sensitivity levels in `governance/classification.yaml`.
4. Create your domains and data products (see [For domain teams](#for-domain-teams)). Start small: one domain, two products.
5. Protect `main` (see [Access and branch protection](#access-and-branch-protection)). Without it, nothing is enforced.

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
dgac/                           the standard's tool (Python package, `pip install`)
STANDARD.md · RULES.md          the standard and its 37 rules
```

Files marked `Generated` in their first line come from the cards and extensions: `.github/CODEOWNERS`, `_group.yml`, `selectors.yml`, `_semantic.generated.yml`. Run `dgac generate` after an edit; CI fails if they are stale.

## For domain teams

**What the standard asks.** Each domain declares a target level in `governance.yml`. Level 1 rules always block a pull request; levels 2 and 3 block once you target them. The governance committee sets a floor and a deadline.

| Level | What it guarantees |
| --- | --- |
| 1. Identified | Every data product has a folder, a card, a Data Owner, a Steward and a tech owner |
| 2. Isolated | Other domains see only `public/`; everything from other domains enters through `external/` |
| 3. Under contract | Public interfaces are versioned, under an ODCS contract, described, classified and fresh |

The template declares level 1. Its two example products meet level 3.

**Create a domain.** `dgac new-domain finance --team @acme/finance-data` creates `domains/finance/` (a dbt project) and `governance/glossary/finance.yaml`.

**Add a data product.**

```bash
dgac new-product sales returns --team @lumen-retail/sales-data \
    --owner julien.fabre@lumen.example --steward amelie.roche@lumen.example
```

Fill in the purpose, classification and `containsPii` in the card, then write your models in `staging/`, `silver/` and `gold/`.
Shared macros and seeds carry the product's prefix: `returns__...`.

**Publish an interface.** `dgac new-interface sales returns refunds` creates `public/refunds_v1.sql`, `refunds.yml` and the contract `refunds_v1.odcs.yaml` (status `proposed`). The contract is the source of truth: the dbt columns follow it. A new public interface needs the Data Owner's approval (GOV-A01).

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

## Access and branch protection

The standard's principle 6 says no change to a data product merges without its code owners. GitHub enforces it only once `main` is protected.

**1. Create the teams.** One GitHub team for the central data governance team, one per domain or product team, with the handles used in `hub.yml`, `governance.yml` and the product cards. Give each team **Write** access to the repository: GitHub ignores a CODEOWNERS entry for a team that cannot write. GitHub shows invalid entries when you open `.github/CODEOWNERS` in the browser.

**2. Protect `main`.** The rule set is ready in [.github/rulesets/protect-main.json](.github/rulesets/protect-main.json). Import it in **Settings → Rules → Rulesets → New ruleset → Import a ruleset**, or with the GitHub CLI:

```bash
gh api repos/{owner}/{repo}/rulesets -X POST --input .github/rulesets/protect-main.json
```

It requires a pull request, one approval from the code owners of every changed folder, a new approval after each push, and a green `validate` check. It forbids force pushes and deleting `main`. On a private repository, rulesets need a paid GitHub plan (Team or Enterprise).

**What this gives you.**

| Change | Who must approve |
| --- | --- |
| A data product's folder | Its tech owner (`team.name` in the card) |
| The rest of a domain folder (`governance.yml`, `external/`, dbt settings) | The domain team (`team` in `governance.yml`) |
| `governance/` (glossary, classification, common semantic model), `schemas/`, `dgac/` | The central data governance team |

**What it does not give you.** In a single repository every team can *read* every domain's code; GitHub cannot hide a folder. The Data Owner's and the committee's approvals (GOV-A01 to A04) are collected outside GitHub in V1. Access to the data itself (warehouse grants, masking) is out of the standard's scope.

## One repository per domain

The monorepo is the easiest way to start, and the standard accepts it. A federated company that wants each team to see and write only its own code splits it:

```
acme/data-governance-hub      governance/, schemas/, dgac/    Write: central team · Read: every data team
acme/data-dbt-finance         one domain, same layout         Write: @acme/finance-data
acme/data-dbt-sales           one domain, same layout         Write: @acme/sales-data
```

1. **The hub.** Create it from this template, run `dgac init`, and tag a release (`git tag hub-v1.0.0`). Domains pin a release, so a change to the hub reaches them when they choose.
2. **A domain.** From the hub, `dgac new-domain finance --team @acme/finance-data --repo ..` creates `../data-dbt-finance`, with its own CI, CODEOWNERS and README. Push it as a new repository, then:
   - in `.github/workflows/validate.yml`, set the hub repository and the release tag (the two `TODO` lines);
   - add a secret `HUB_READ_TOKEN`: a token that can read the hub (a fine-grained token, or a GitHub App), because the default CI token cannot read another private repository.
3. **Reading another domain.** dbt-loom needs the producer's `target/manifest.json`. The domain CI uploads it as an artifact; for daily use, copy it to a bucket that dbt-loom reads directly (S3, GCS, Azure, or dbt Cloud) and point `dbt_loom.config.yml` to it.
4. **Who reads whom.** In a monorepo, `dgac manifest` sees every domain and lists the consumers of each interface. Across repositories each manifest lists what its domain reads; collect the manifests in one place to know the consumers.

## Built on standards

| For | We use |
| --- | --- |
| Product cards | [ODPS v1.1.0](https://bitol-io.github.io/open-data-product-standard/) (Bitol, Linux Foundation), with the standard's profile |
| Data contracts | [ODCS v3.2.0](https://bitol-io.github.io/open-data-contract-standard/) (Bitol, Linux Foundation) |
| Shared semantics | [Apache Ossie 0.1.1](https://github.com/apache/ossie) (incubating), formerly Open Semantic Interchange |
| Transformations, ownership, interfaces | dbt groups, model access, model versions and contracts; [dbt-loom](https://github.com/nicholasyager/dbt-loom) for cross-project references with dbt Core |
| Review | GitHub CODEOWNERS and rulesets |

## License

[Apache 2.0](LICENSE)
