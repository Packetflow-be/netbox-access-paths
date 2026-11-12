# netbox-access-paths

**Document how your team reaches every customer system, in NetBox.**

Every MSP has the same tribal knowledge: *to get into customer X, connect to the
office VPN, RDP to the jump host, then open the firewall portal.* It lives in a
wiki page, a password manager note, or one engineer's head. That's fine until:

- a customer's NIS2 supplier questionnaire asks *how exactly do you access our systems?*
- a technician leaves and you need to know everything they could reach,
- your jump host or RMM is compromised and you need to know which customers sit behind it,
- a new hire needs a map of how to get into customer infrastructure.

`netbox-access-paths` turns that knowledge into data. An **access path** is who can reach
which customer system, from where, through which hops, with which method, approved by
whom, and when it's due for review.

```
 Support team ──► Office LAN ──► NetBird ──► jump01 (VM) ──► RDP ──► customer-dc01
   (who)          (origin)       └────── shared route ─────┘  (method)  (target, tenant "Acme")
```

## What you get

- **Routes**: the MSP-side chain you reuse for every customer (office → VPN/ZTNA → jump host).
  Define it once; dozens of paths share it.
- **Paths**: route + customer-side hops + target (device, VM, service or URL) + method
  (RDP, SSH, web portal, RMM, vendor remote tool, ...), who may use it, MFA, and where the
  credential lives (a reference, never the secret).
- **Approval and review**: approved by, review date, expiry for temporary or vendor access,
  break-glass paths flagged.
- **Answers, not just records**:
  - *Customer tab*: every way into this tenant, ready to paste into a questionnaire (CSV/Markdown export).
  - *Device/VM tab*: every path that runs **through** this box (blast radius) or **into** it.
  - *Contact tab*: everything this person can reach (offboarding).
  - *Review queue*: paths past review date, expired, or without MFA.

Built on NetBox objects you already have (tenants, contacts, devices, VMs, tunnels,
services, prefixes); REST API, GraphQL and CSV import included.

## What it is not

Not a password manager, not a PAM, and it doesn't open connections. It documents the
paths; your RDM/PAM/ZTNA tools keep doing the access.

## Status

Design stage, not on PyPI yet. Target: NetBox 4.7–4.8, Python 3.12+, Apache-2.0.
See [DESIGN.md](DESIGN.md) for the model sketch. Feedback from MSPs running NetBox is welcome.

Made by [Packetflow](https://packetflow.be), from the same team as
[netbox-iec62443](https://github.com/Packetflow-be/netbox-iec62443).
