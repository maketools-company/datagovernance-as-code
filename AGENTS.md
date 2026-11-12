# Instructions for AI agents

This repository follows the Data Governance as Code standard ([STANDARD.md](STANDARD.md), rules in [RULES.md](RULES.md)).
Read the files directly. After a build, `build/<domain>/governance-manifest.json` summarises each domain.

## Answering questions

- Who owns a data product: its card, `domains/<domain>/dataproducts/<product>/_data_product.odps.yaml`,
  `team.members` (`data-owner`, `data-steward`) and `team.name` (tech owner, a GitHub team).
- What a column contains and how sensitive it is: the contract `public/<interface>_v<n>.odcs.yaml`, field `classification`.
  Levels are defined in `governance/classification.yaml`.
- What a business term means: `governance/glossary/<domain>.yaml`. Only `approved` terms are official.
- What a metric means: the common model `governance/semantic/common.ossie.yaml`, or the product's
  `<product>.ossie.yaml`. Metrics marked `private: true` are for the owning domain only.
- Who reads an interface: the `consumers` of the product in the governance manifest, derived from dbt references.

## Making a change

1. Use the tool to create things: `dgac new-domain`, `new-product`, `new-interface` (install with `pip install -e ".[dbt]"`).
   Otherwise follow the closest existing example; do not invent fields.
2. Run `dgac generate`, then `dgac validate`. Fix every error.
3. If you changed dbt models, run `dgac build`.
4. Open a pull request. Never merge it yourself. Say in its description when it needs the Data Owner
   (new public interface, new major version, change of classification) or the governance committee
   (common semantic model).

## Rules you must not break

- Never edit a file whose first line says `Generated`. Edit the card or the extension and run `generate`.
- Never change a public interface in a breaking way: publish `<interface>_v<n+1>` with its own contract,
  and deprecate the old one with an `endOfLife` at least 3 months away.
- Read another domain only from `external/`, with `ref('<domain>', '<interface>', v=<n>)`.
- Shared macros and seeds start with the product id and two underscores: `orders__margin`.
- Never give an extension metric or dataset the name of a common one. A derived metric starts with
  its parent's name and only adds filters.
- People are work emails, teams are GitHub teams (`@org/team`). Ids are snake_case.
- When unsure whether a column is personal data, classify it `restricted` and ask in the pull request.
  The DPO decides.
