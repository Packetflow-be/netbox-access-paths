# netbox-access-paths: design sketch (2026-11-12)

Why it looks the way it does:

- **Separate plugin**, not part of netbox-iec62443 (IT MSPs won't install Purdue/SL
  models to document jump hosts) and not an extension of netbox-data-flows.
- **Same pattern as netbox-iec62443's Flow/FlowHop, no dependency on it**: ordered hops with an
  exactly-one-of check; approval with approved_by/approved_on auto-dating, review_by, expires,
  `is_expired`/`is_review_due` properties.
- A community plugin that Packetflow uses itself. Kept small: **three models**, maintainable by one person.

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

## Added in 0.2 (2026-11-13)

- **Scope targets** are more target types on the same generic key (prefix, VLAN, cluster, site, tenant),
  not a fourth model. Membership is resolved when a device or VM asks "what leads into me" (`queries.scope_q`),
  so nothing is stored per member and nothing goes stale. Customers share RFC 1918 space, sites and hosting
  clusters, hence `scope_same_tenant`.
- **Review sign-off** is two fields and one POST view; the review history is NetBox's change log, not a model.
- **No notifications and no "last used" ingestion**: a dashboard widget shows the counts instead; session
  logs belong in the session manager or PAM.

## Out of scope for v0.1

- Storing secrets, launching connections, PAM features.
- Log ingestion (`last_used` from RDM/NetBird/jump host logs) → candidate for v0.2.
- Discovering paths automatically.
- Diagram libraries; the badge chain is enough.

## Open questions, and how v0.1 settled them (2026-11-12)

The sketch left three open: holders as M2M or NetBox contact assignments, whether a GFK to
`ipam.Service` (whose parent is itself generic since NetBox 4.3) works, and origin as choices or a model.

- **Holders**: explicit M2M to contacts and contact groups. NetBox 4.7's `ContactsMixin` assigns contacts
  only, not groups. A grant to a group covers its sub-groups (walked through `parent`, so it works whether
  contact groups are MPTT or ltree).
- **Service targets**: the GFK points at the `ipam.Service` itself; its generic parent doesn't matter. The device
  and VM tabs count paths into their services and IP addresses as paths into them.
- **Origin**: choices with `key`, so `FIELD_CHOICES['netbox_access_paths.AccessRoute.origin']` (or `...+`)
  replaces or extends them; the same for method, authentication and status.
- **Deleted target**: the path stays, target cleared, shown as "target missing" in the review queue.
- **Credential reference** is left out of the questionnaire export unless `export_credential_ref` is set.
- Added beyond the sketch: `manage.py access_paths_demo`, a `needs_review` filter (any reason), the export
  takes any path filter (`/plugins/access-paths/export/?holder_id=..`).
