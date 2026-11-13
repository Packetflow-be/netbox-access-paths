from django.conf import settings

DEFAULTS = {
    'export_credential_ref': False,
    'review_interval_days': 365,
    'scope_same_tenant': True,
}


def plugin_setting(name):
    return settings.PLUGINS_CONFIG.get('netbox_access_paths', {}).get(name, DEFAULTS[name])


def review_interval_days():
    """Days from a review to the next review date."""
    try:
        return max(1, int(plugin_setting('review_interval_days')))
    except (TypeError, ValueError):
        return DEFAULTS['review_interval_days']
