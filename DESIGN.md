# netbox-access-paths: design sketch (2026-11-12)

Hand-off for the session that builds v0.1. Decisions taken with Louis on 2026-11-12:

- **Separate plugin**, not part of netbox-iec62443 (IT MSPs won't install Purdue/SL
  models to document jump hosts) and **not** a contribution to netbox-data-flows.
- **Copy the Flow/FlowHop pattern from netbox-iec62443, don't depend on it.** Source:
  `~/packetflow/netbox-iec62443/netbox_iec62443/models.py` (`Flow` ~L283, `FlowHop` ~L478):
  ordered hops with an exactly-one-of check; verdict with decided_by/decided_on auto-dating,
  review_by, expires, `is_expired`/`is_review_due` properties.
- Goal is giving back to the community and using it at Packetflow (maybe e-BO, if they run
  NetBox: unknown). Keep it small: **three models**, maintainable by one person.

## Packaging

| | |
|---|---|
| PyPI / repo name | `netbox-access-paths` (PyPI name free on 2026-11-12) |
| Python package | `netbox_access_paths` |
| `base_url` | `access-paths` |
| NetBox | `min_version = '4.7.0'`, `max_version = '4.8.99'` (same as iec62443) |
| Python | `>=3.12` |
| License | Apache-2.0 |
| Scaffolding | copy from iec62443: pyproject layout, `.github/workflows/ci.yml`, CHANGELOG, release = tag + approve `pypi` environment |

## Models

### 1. `AccessRoute`: the reusable MSP-side chain

"How we get out of our own network." Shared by many paths; a route with zero hops is
legal (e.g. *Anywhere (internet)* for customer-provided TeamViewer IDs).

| field | type | notes |
|---|---|---|
| `name` | Char(100), unique | e.g. "Office → NetBird → jump01" |
| `origin` | Char choices `OriginChoices` | `office`, `ztna` (any device on the ZTNA), `home`, `customer_site`, `internet` |
| `origin_prefixes` | M2M `ipam.Prefix`, blank | where sessions start, e.g. office VLAN |
| `tenant` | FK `tenancy.Tenant`, null | normally the MSP's own tenant |
| `description`, `comments`, tags | from `PrimaryModel` | |

### 2. `AccessPath`: one way into one customer system

| field | type | notes |
|---|---|---|
| `name` | Char(100), blank → generated from target + method (as iec62443 `default_name`) | |
| `tenant` | FK `tenancy.Tenant`, **required**, PROTECT | the customer |
| `route` | FK `AccessRoute`, **required**, PROTECT | every path starts somewhere; reuse is the point |
| `target_type` / `target_id` / `target` | GenericForeignKey limited to `dcim.Device`, `virtualization.VirtualMachine`, `ipam.Service`, `ipam.IPAddress` | null allowed when `target_url` is set |
| `target_url` | URLField, blank | web portals and SaaS consoles (M365 admin, firewall cloud) |
| `method` | Char choices `AccessMethodChoices` | `rdp`, `ssh`, `web`, `rmm`, `vendor_remote` (TeamViewer, AnyDesk, ...), `vpn_network` (full network), `console`, `api`, `other` |
| `holders` | M2M `tenancy.Contact`, blank | who may use it |
| `holder_groups` | M2M `tenancy.ContactGroup`, blank | e.g. "Support", "Vendor X" |
| `authentication` | Char choices | `sso_mfa`, `mfa`, `password`, `key`, `shared_account`, `unknown` |
| `credential_ref` | Char(200), blank | **pointer only** ("RDM: Acme/dc01 admin"), help text says never paste secrets |
| `status` | Char choices | `active`, `planned`, `break_glass`, `disabled` |
| `approved_by` | FK `tenancy.Contact`, null | same auto-dating as iec62443 `decided_by`/`decided_on` |
| `approved_on` | Date, null | |
| `review_by` | Date, null | |
| `expires` | Date, null | temporary or vendor access |
| `comments`, tags | `PrimaryModel` | |

Validation (`clean`): at least one of `target` / `target_url`; target content type within the
allowed set. A target whose own tenant differs from `tenant` is **not** rejected (NetBox
has no form warnings); show a mismatch badge on the detail page instead.

Properties: `is_expired`, `is_review_due` (copy from iec62443), `lacks_mfa`
(`authentication in {password, shared_account, unknown}`), `all_hops` (route hops then path hops).

### 3. `AccessHop`: one step, on a route or on a path

| field | type | notes |
|---|---|---|
| `route` | FK `AccessRoute`, null, CASCADE | exactly one of route / path |
| `path` | FK `AccessPath`, null, CASCADE | customer-side hops (customer firewall, customer jump host) |
| `position` | PositiveSmallInt | unique per route and per path (two conditional `UniqueConstraint`s) |
| `device` / `virtual_machine` / `tunnel` | FK, null, CASCADE | as iec62443 `FlowHop` |
| `label` | Char(100), blank | for hops not in NetBox (NetBird cloud, TeamViewer relay) |

`clean`: exactly one of route/path; exactly one of device / virtual_machine / tunnel / label.
`related_name`s prefixed `access_paths_...` to avoid clashes with iec62443 when both are installed.

## Views (the reason people install it)

1. **Tenant tab "Access paths"**: table of all paths into the customer + **Export** (CSV and
   Markdown) shaped for NIS2/supplier questionnaires: target, method, route summary, who,
   authentication, approved by/on, review date.
2. **Device/VM tab "Access paths"**, two sections: *through this* (it's a hop on a route or
   path; for a route hop list every path using that route, grouped by tenant = blast radius)
   and *into this* (it's the target).
3. **Contact tab**: paths where the contact is a holder directly or through a group (offboarding).
4. **Review queue** (menu item): filters `review_due`, `expired`, `lacks_mfa`, `status=break_glass`.
5. **Path detail**: horizontal chain origin → route hops → path hops → method → target, as plain
   HTML/CSS badges (no JS library), with route hops visually grouped.

Plus the standard set: list/detail/edit/bulk/CSV import, filtersets (tenant, method, status,
holder, hop device/VM, review_due, expired, lacks_mfa), REST API, GraphQL, search indexes.

## Out of scope for v0.1

- Storing secrets, launching connections, PAM features.
- Log ingestion (`last_used` from RDM/NetBird/jump host logs) → candidate for v0.2.
- Discovering paths automatically.
- Diagram libraries; the badge chain is enough.

## Open questions for the implementing session

- `holders` as explicit M2M vs NetBox contact assignments (`ContactsMixin`) with a role.
  Leaning M2M because assignments go to contacts, not contact groups, and the Contact
  tab query stays simple. Check what NetBox 4.7 offers before deciding.
- `ipam.Service` parent is generic since NetBox 4.3: confirm the GFK limit works with it.
- Whether `origin` choices should be a model instead (MSPs may want their own list). Start
  with choices + `FIELD_CHOICES` override support, like NetBox core.

## First steps

1. Ask Louis to create `Packetflow-be/netbox-access-paths` (public) or confirm you may.
2. Scaffold from iec62443, models + migrations + tests (aim for the same test style).
3. Dogfood: enter Packetflow's own paths in the **demo branch on nbx01**
   (header `X-NetBox-Branch`) or on tst02, not prod main. Example route: office → NetBird → aut01.
4. Screenshot the tenant tab and path detail (desktop + phone) before showing Louis.
5. Near release: propose a CHG-PACK record in the vault (see `~/packetflow/CLAUDE.md`).
