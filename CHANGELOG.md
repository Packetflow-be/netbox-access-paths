# Changelog

## Unreleased (0.1.0)

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
