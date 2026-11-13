# Security policy

## Supported versions

The latest release on [PyPI](https://pypi.org/project/netbox-access-paths/) gets security fixes.

## Reporting a vulnerability

Report it privately through GitHub:
[Report a vulnerability](https://github.com/Packetflow-be/netbox-access-paths/security/advisories/new).
Please don't open a public issue. You get an answer within five working days.

## What the plugin holds

Access paths describe how people reach customer systems, so the data itself is sensitive: protect it with
NetBox's object permissions as you would any other inventory. The plugin stores a *reference* to where a
credential lives, never the credential. If you find a secret in a credential reference field, that is a
data-entry mistake to clean up, not a plugin vulnerability.
