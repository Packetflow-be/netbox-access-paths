# Changelog

## 0.2.0 (2026-11-13)

- **Scope targets**: a path's target can be a prefix, VLAN, cluster, site or tenant, and then stands for
  everything in it. The device and VM tabs, the `device_id` / `virtual_machine_id` filters and the tab badges
  count such a path as a path into every device and VM it covers: an IP address inside the prefix (same VRF),
  the VLAN on an interface or on a containing prefix, the cluster, the site, the tenant. A prefix, VLAN,
  cluster or site path covers only devices and VMs of the path's tenant or of no tenant, unless
  `scope_same_tenant` is set to `False`. The questionnaire export writes "everything in ..."; the REST API has
  a read-only `scope` field; CSV import takes the new target types by name.
- **Review sign-off**: *Mark reviewed* on the path page, on the review queue's *Review due* rows and as a bulk
  action on the path list records `reviewed_on` (today) and `reviewed_by` (the user) and sets `review_by`
  `review_interval_days` (default 365) ahead. Both fields are in the table, the filters, the REST API,
  GraphQL and the questionnaire export ("Last reviewed").
- **Dashboard widget** *Access review*: the review queue's counts on the home screen, each linked to its list.
- The demo data has two scope paths (nine paths in all).
- Migration `0002`: two new columns on access paths; no data changes.

## 0.1.0 (2026-11-12)

First version, for NetBox 4.7 (4.7.0 and later; 4.8 allowed).

- Access route, access path and access hop models with UI views, bulk import/edit/delete, filters, search,
  REST API and GraphQL.
  - A route is the MSP side: an origin (office, ZTNA, home, customer site, internet), origin prefixes and
    ordered hops. Many paths share one route.
  - A path belongs to a customer (tenant) and a route, has its own customer-side hops, a target (device, VM,
    application service, IP address and/or URL), a method, holders (contacts and contact groups),
    authentication, a credential reference (never the secret), status (active, planned, break-glass,
    disabled), approval (by, on), a review date and an expiry date.
  - A hop is a device, VM, tunnel or a free label, at a position on a route or on a path.
- Tabs: Access paths on tenants (with the questionnaire export), devices and VMs (through this / into this),
  and contacts (directly or through a group and its parent groups).
- Review queue: expired, review due, without MFA, break-glass, target missing.
- Questionnaire export as CSV or Markdown for any path filter; the credential reference column only with
  `export_credential_ref`.
- A deleted target leaves its paths in place, marked "target missing".
- Choice sets can be replaced or extended with `FIELD_CHOICES`.
- `manage.py access_paths_demo` creates (and `--delete` removes) a fictional MSP to try the plugin.
