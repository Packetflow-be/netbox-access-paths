from django.utils.translation import gettext_lazy as _

from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem


def _buttons(model):
    return (
        PluginMenuButton(
            link=f'plugins:netbox_access_paths:{model}_add', title=_('Add'), icon_class='mdi mdi-plus-thick',
            permissions=[f'netbox_access_paths.add_{model}'],
        ),
        PluginMenuButton(
            link=f'plugins:netbox_access_paths:{model}_bulk_import', title=_('Import'), icon_class='mdi mdi-upload',
            permissions=[f'netbox_access_paths.add_{model}'],
        ),
    )


menu = PluginMenu(
    label=_('Access paths'),
    icon_class='mdi mdi-key-chain-variant',
    groups=(
        (_('Access'), (
            PluginMenuItem(
                link='plugins:netbox_access_paths:accesspath_list', link_text=_('Paths'),
                permissions=['netbox_access_paths.view_accesspath'], buttons=_buttons('accesspath'),
            ),
            PluginMenuItem(
                link='plugins:netbox_access_paths:accessroute_list', link_text=_('Routes'),
                permissions=['netbox_access_paths.view_accessroute'], buttons=_buttons('accessroute'),
            ),
            PluginMenuItem(
                link='plugins:netbox_access_paths:accesshop_list', link_text=_('Hops'),
                permissions=['netbox_access_paths.view_accesshop'], buttons=_buttons('accesshop'),
            ),
        )),
        (_('Review'), (
            PluginMenuItem(
                link='plugins:netbox_access_paths:review', link_text=_('Review queue'),
                permissions=['netbox_access_paths.view_accesspath'],
            ),
        )),
    ),
)
