# Contributing

Thanks for looking. This plugin is kept small on purpose (three models, one maintainer), so the most
useful contributions are:

- **How you document access today.** If a field, a target type or an export column is missing for your
  MSP, say so in [Discussions](https://github.com/Packetflow-be/netbox-access-paths/discussions) or open
  a feature request. A real example (anonymised) beats a general wish.
- **Bug reports** with the NetBox and plugin version and the steps to get there.
- **Pull requests** for bugs, and for features once an issue agrees on the shape.

## Working on the code

[docs/development.md](docs/development.md) has the setup (netbox-docker or a plain NetBox checkout).
Before opening a pull request:

```bash
ruff check .
python manage.py test netbox_access_paths --keepdb
python manage.py makemigrations netbox_access_paths --check --dry-run
```

CI runs the same on NetBox 4.7.0, the newest 4.7 release and NetBox's development branch.

- Migrations must depend on NetBox 4.7.0's migrations (the oldest supported release); see the development notes.
- New model fields come with a filter, an API field, a test and a line in `CHANGELOG.md`.
- The plugin never stores secrets and never opens connections. Requests in that direction will be declined.

## Security

Please don't report vulnerabilities in a public issue: see [SECURITY.md](SECURITY.md).
