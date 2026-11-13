from netbox.plugins import PluginConfig

__version__ = '0.2.0'


class AccessPathsConfig(PluginConfig):
    name = 'netbox_access_paths'
    verbose_name = 'Access paths'
    description = 'Document how your team reaches every customer system: routes, paths, hops, holders and reviews'
    version = __version__
    author = 'Packetflow'
    base_url = 'access-paths'
    # Tested in CI on 4.7.0, the newest 4.7 release and NetBox's development branch for the next release (weekly)
    min_version = '4.7.0'
    max_version = '4.8.99'
    default_settings = {
        # Include the credential reference column in the questionnaire export (CSV/Markdown for customers).
        'export_credential_ref': False,
        # Days between a review ("Mark reviewed") and the next review date.
        'review_interval_days': 365,
        # A path into a scope (prefix, VLAN, cluster, site) covers only the devices and VMs in it that belong to the
        # path's tenant or to no tenant. Set to False to cover everything in the scope whatever its tenant.
        'scope_same_tenant': True,
    }

    def ready(self):
        super().ready()
        from . import signals, widgets  # noqa: F401  (widgets registers the dashboard widget)
        signals.connect()


config = AccessPathsConfig
