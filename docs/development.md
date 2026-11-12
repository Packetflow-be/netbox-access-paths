# Development

## With netbox-docker

The plugin source is mounted read-only into the NetBox container and put on `PYTHONPATH`.

`docker-compose.override.yml`:

```yaml
services:
  netbox:
    ports:
      - "8080:8080"
    volumes:
      - /path/to/netbox-access-paths:/opt/netbox-plugins/netbox-access-paths:ro
    environment:
      PYTHONPATH: /opt/netbox-plugins/netbox-access-paths
```

`configuration/plugins.py`:

```python
PLUGINS = ["netbox_access_paths"]
PLUGINS_CONFIG = {"netbox_access_paths": {}}
```

Then `docker compose up -d netbox`; the entrypoint applies the migrations. After code changes,
`docker restart <netbox container>`. If you also run `netbox-worker`, give it the same volume and
environment.

Run the tests in a throwaway container (uses a separate `test_netbox` database):

```
docker compose run --rm --no-deps -T netbox \
  /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py test netbox_access_paths --keepdb --noinput
```

New migrations need developer mode and a writable checkout:

```
docker compose run --rm --no-deps -T -e DEVELOPER=True netbox \
  /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py makemigrations netbox_access_paths --dry-run -v 3
```

(`--dry-run -v 3` prints the migration file, which also works with the read-only mount.)

Migrations depend on NetBox 4.7.0's migrations, the oldest supported release. `makemigrations` on a newer
NetBox writes that release's latest migration names into `dependencies`; set them back to the 4.7.0 names
(see `0001_initial.py`) or the plugin won't install on 4.7.0 to 4.7.3.

Demo data in a running instance:

```
docker exec <netbox container> /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py access_paths_demo
```

## Without Docker

Any NetBox source checkout works, with PostgreSQL and Redis running locally:

```bash
git clone --depth 1 --branch v4.7.4 https://github.com/netbox-community/netbox.git
python3.12 -m venv venv && venv/bin/pip install -r netbox/requirements.txt
venv/bin/pip install -e /path/to/netbox-access-paths
# netbox/netbox/netbox/configuration.py: DATABASES, REDIS, SECRET_KEY, API_TOKEN_PEPPERS and
#   PLUGINS = ["netbox_access_paths"]   (.github/ci/configuration.py is a complete example)
cd netbox/netbox
../../venv/bin/python manage.py migrate
../../venv/bin/python manage.py test netbox_access_paths --keepdb --parallel 4
../../venv/bin/python manage.py access_paths_demo  # a fictional MSP to look at
```

With `--parallel`, Django reuses cloned test databases (`test_netbox_1`, ...) when `--keepdb` is given. After
a new migration, drop the clones (`dropdb test_netbox_1` ...) or they stay at the old schema and the run fails
with "cannot pickle 'traceback' object" (a failure in a worker that cannot be reported).

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request and push, and weekly:

- `ruff check .`;
- the test suite and a migration check (`makemigrations --check`) on NetBox 4.7.0, the newest 4.7 release and
  NetBox's `feature` branch. The `feature` run may fail without failing the workflow: it is the early warning
  for the next NetBox release. Query counts are asserted only on the newest 4.7 release; the other versions
  record them;
- a package build with `twine check` and a check that the wheel holds the templates and migrations.

## Releasing

1. Set `__version__` in `netbox_access_paths/__init__.py` and move the changelog entries under the new version.
2. Merge to `main`, then tag: `git tag v0.1.0 && git push origin v0.1.0`.
3. The `publish` job builds the package and uploads it to PyPI once lint, tests and build pass, and only if the
   tag matches `__version__`.

Publishing uses PyPI trusted publishing, so no token is stored in GitHub. Once, before the first release:
on PyPI, add a trusted publisher for the project `netbox-access-paths` (owner `Packetflow-be`, repository
`netbox-access-paths`, workflow `ci.yml`, environment `pypi`), and in the GitHub repository create the environment
`pypi` (Settings > Environments), optionally with required reviewers.
