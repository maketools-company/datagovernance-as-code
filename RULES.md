# Rule catalogue

Part of the [standard](STANDARD.md), with the amendments of the V1 template applied (file and field names of GOV-101 to GOV-110 and GOV-301).

**In V1, these rules are checked by hand**, in pull request review. What the template's CI already guarantees:
`dgac validate` checks every file against its schema (GOV-102, GOV-110, GOV-111, GOV-302, GOV-314);
`dgac generate` writes CODEOWNERS, dbt groups and selectors from the cards, so GOV-106 to GOV-108 and GOV-205 hold by construction;
dbt itself refuses references to another product's or another domain's private models (the protection GOV-201 and GOV-203 aim at) and, with `contract: enforced`, fails a build whose columns differ from the dbt contract (GOV-303);
`dgac assemble` refuses semantic extensions that break GOV-315 to GOV-318.

The standard has 37 automated rules over 3 levels, 4 approvals and 3 human reviews. Each rule has a stable identifier, used by the checks, in reports and between teams.

A rule blocks a merge when its level is at or below the repository's target level; above it, the rule only warns. Level 1 rules always block. The message is written for a business reader, not in YAML terms.

## Level 1: Identified

| ID | What is checked | Message when it fails | Fixed by |
| --- | --- | --- | --- |
| GOV-101 | Every `dataproducts/{product}/` folder contains `_data_product.odps.yaml` | "{product} has no product card." | Domain team |
| GOV-102 | The card is valid against ODPS v1.1.0 and the standard's profile | "The card of {product} is incomplete: {field} is missing." | Domain team; Steward for business fields |
| GOV-103 | The card's `id` equals the folder name | "The declared name of {product} does not match its folder." | Domain team |
| GOV-104 | A `team.members` entry has `role: data-owner` | "{product} has no Data Owner." | Governance committee (appointment) |
| GOV-105 | A `team.members` entry has `role: data-steward` | "{product} has no Steward: nobody can stand in for the Data Owner." | Data Owner |
| GOV-106 | A `CODEOWNERS` entry covers the product folder | "No team approves the code of {product}." | Domain team |
| GOV-107 | The card's `team.name` matches the `CODEOWNERS` entry | "The team declared for {product} is not the one approving its code." | Domain team |
| GOV-108 | One dbt group per product, named like its folder | "{product} is not declared as a data product in dbt." | Domain team |
| GOV-109 | Every model belongs to a group | "{n} models belong to no data product." | Domain team |
| GOV-110 | The `classification` and `containsPii` custom properties are set in the card | "The sensitivity of {product}'s data is not declared." | Steward, validated by the DPO |
| GOV-111 | `governance.yml` is present and declares a valid `standard_version`, `target_level`, common semantic model version and Ossie version | "Domain {domain} does not declare its target level." | Domain team |

## Level 2: Isolated

| ID | What is checked | Message when it fails | Fixed by |
| --- | --- | --- | --- |
| GOV-201 | Only models in `public/` have `access: public` | "{model} is visible to other domains without being a public interface." | Domain team |
| GOV-202 | No reference to another domain outside `external/` | "{product} uses data from {domain} without going through the consumer zone." | Domain team |
| GOV-203 | A source pointing to another domain targets only its public tables | "{product} reads an internal table of {domain}, which may change without notice." | Domain team |
| GOV-204 | Macros and seeds carry their product's prefix | "{n} shared items are not attached to any product." | Domain team |
| GOV-205 | One selector per product | "{product} cannot be deployed on its own." | Domain team |
| GOV-206 | `staging/` models are ephemeral or views | "{product} stores raw copies of its sources." | Domain team |

## Level 3: Under contract

| ID | What is checked | Message when it fails | Fixed by |
| --- | --- | --- | --- |
| GOV-301 | Every version of a model in `public/` has its `{interface}_v{n}.odcs.yaml` contract | "Interface {model} has no contract." | Domain team + Steward |
| GOV-302 | The contract is valid against the ODCS v3.2.0 JSON Schema | "The contract of {model} is malformed." | Domain team |
| GOV-303 | `contract: enforced` on every public model | "The contract of {model} is not checked at each build." | Domain team |
| GOV-304 | dbt columns match the ODCS schema | "{model} does not deliver the columns its contract promises." | Domain team |
| GOV-305 | The public model is versioned; contract major version = dbt version | "The versions of {model} and its contract do not match." | Domain team |
| GOV-306 | No column removed, renamed or retyped without a new major version | "This change breaks interface {model}: a new version is needed." | Domain team |
| GOV-307 | Every public column has a description | "{n} columns of {model} have no definition." | Steward |
| GOV-308 | Every public column has a classification | "{n} columns of {model} are not classified." | Steward, validated by the DPO |
| GOV-309 | A `latency` SLA is declared and a freshness test goes with it | "The freshness of {model} is neither promised nor monitored." | Steward sets the value; domain team writes the test |
| GOV-310 | A primary key is declared, with uniqueness and not-null rules | "{model} has no reliable key." | Domain team |
| GOV-311 | A `deprecated` version has an `endOfLife` at least 3 months after the next version's release | "Consumers of {model} v{n} do not have time to migrate." | Domain team |
| GOV-312 | A version is removed only when no domain references it | "{model} v{n} is still used by {domains}." | Domain team |
| GOV-313 | Other domains are consumed through cross-project references | "{product} reads {domain} without a contract check." | Domain team |
| GOV-314 | The assembled semantic model is valid against the pinned Ossie JSON Schema | "The business definitions of {product} cannot be read by other tools." | Domain team |
| GOV-315 | Shared semantics point only to public interfaces (own, or other domains' through the consumer zone); semantics on internal layers are marked private, left out of the published model, and used by no other domain | "Metric {metric} is shared but built on internal data that may change without notice." | Domain team |
| GOV-316 | No metric or dimension in an extension has the name of a common one | "{product} redefines {metric}, which already has a common definition." | Domain team + Steward |
| GOV-317 | A derived metric references a common metric and only adds filters or breakdowns on dimensions present in the model | "{metric} copies or changes the formula of {parent} instead of deriving from it." | Domain team + Steward |
| GOV-318 | A derived metric's name starts with its parent's name | "The name of {metric} does not show which common metric it comes from." | Steward |
| GOV-319 | The dbt semantic configuration matches the one generated from the assembled model | "The metrics computed by {product} differ from their published definitions." | Domain team |
| GOV-320 | A changed definition of a shared metric comes with a new major version of the model; the previous version stays available for at least 3 months | "The meaning of {metric} changes without notice to the domains that use it." | Domain team, or central data governance team for the common model |

## Approvals

These apply whatever the level, as soon as the change appears in a pull request. Without an answer within 5 working days, the Steward may approve, unless the Steward made the request.

| ID | Change detected | Message | Approver |
| --- | --- | --- | --- |
| GOV-A01 | A new model appears in `public/` | "New interface {model} proposed by {domain}: approval needed." | Data Owner |
| GOV-A02 | A contract moves to a new major version | "{model} v{n} replaces v{n-1}: {k} domains will have to migrate." | Data Owner |
| GOV-A03 | The classification of a column or of the product changes | "{column} moves from {before} to {after}." | Data Owner, after DPO validation |
| GOV-A04 | The common semantic model changes | "The common definition of {metric} is changing: {k} domains are affected." | Governance committee |

## Human reviews

What no script can check.

| ID | Review | Who | Frequency |
| --- | --- | --- | --- |
| GOV-H01 | Confirm the role and the list of owned products | Data Owner | Yearly |
| GOV-H02 | Review classifications and the presence of personal data | DPO | Yearly |
| GOV-H03 | Review the definitions of public columns | Steward | Yearly |
