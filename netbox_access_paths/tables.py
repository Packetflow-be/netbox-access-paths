import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import PrimaryModelTable, columns
from tenancy.tables import TenancyColumnsMixin

from .models import AccessHop, AccessPath, AccessRoute

__all__ = ('AccessHopTable', 'AccessPathTable', 'AccessRouteTable')

HOP = "{% include 'netbox_access_paths/inc/hop.html' %}"
ROUTE_HOPS = """
{% for hop in record.hops.all %}""" + HOP + """{% if not forloop.last %} &rarr; {% endif %}
{% empty %}{{ ''|placeholder }}{% endfor %}
"""
# Route hops, then the path's own hops in bold, then the method
PATH_HOPS = """
{% for hop in record.route.hops.all %}""" + HOP + """ &rarr; {% endfor %}
{% for hop in record.hops.all %}<strong>""" + HOP + """</strong> &rarr; {% endfor %}
{% badge record.get_method_display bg_color=record.get_method_color %}
"""
TARGET = "{% include 'netbox_access_paths/inc/target.html' with object=record %}"
HOLDERS = "{% include 'netbox_access_paths/inc/holders.html' with path=record %}"
AUTHENTICATION = """{% load i18n %}
{% badge record.get_authentication_display bg_color=record.get_authentication_color %}
"""
STATUS = """{% load i18n %}
{% badge record.get_status_display bg_color=record.get_status_color %}
{% if record.is_expired %}<span class="badge text-bg-danger">{% trans "expired" %}</span>{% endif %}
{% if record.is_review_due %}<span class="badge text-bg-warning">{% trans "review due" %}</span>{% endif %}
"""


class AccessRouteTable(TenancyColumnsMixin, PrimaryModelTable):
    name = tables.Column(verbose_name=_('Name'), linkify=True)
    origin = columns.ChoiceFieldColumn(verbose_name=_('Origin'))
    origin_prefixes = columns.ManyToManyColumn(verbose_name=_('Origin prefixes'), linkify_item=True)
    hops = columns.TemplateColumn(verbose_name=_('Hops'), template_code=ROUTE_HOPS, orderable=False)
    path_count = columns.LinkedCountColumn(
        verbose_name=_('Paths'), viewname='plugins:netbox_access_paths:accesspath_list',
        url_params={'route_id': 'pk'},
    )
    tags = columns.TagColumn(url_name='plugins:netbox_access_paths:accessroute_list')

    class Meta(PrimaryModelTable.Meta):
        model = AccessRoute
        fields = (
            'pk', 'id', 'name', 'origin', 'origin_prefixes', 'hops', 'path_count', 'tenant', 'tenant_group',
            'description', 'comments', 'tags', 'created', 'last_updated',
        )
        default_columns = ('pk', 'name', 'origin', 'hops', 'path_count', 'description')


class AccessPathTable(PrimaryModelTable):
    name = tables.Column(verbose_name=_('Name'), linkify=True)
    tenant = tables.Column(verbose_name=_('Customer'), linkify=True)
    route = tables.Column(verbose_name=_('Route'), linkify=True)
    origin = columns.ChoiceFieldColumn(verbose_name=_('Origin'), accessor=tables.A('route__origin'),
                                       color=lambda record: record.route.get_origin_color(), orderable=False)
    target = columns.TemplateColumn(verbose_name=_('Target'), template_code=TARGET, orderable=False)
    chain = columns.TemplateColumn(verbose_name=_('Through'), template_code=PATH_HOPS, orderable=False)
    method = columns.ChoiceFieldColumn(verbose_name=_('Method'))
    holders = columns.TemplateColumn(verbose_name=_('Who'), template_code=HOLDERS, orderable=False)
    authentication = columns.TemplateColumn(verbose_name=_('Authentication'), template_code=AUTHENTICATION,
                                            order_by=('authentication',))
    credential_ref = tables.Column(verbose_name=_('Credential reference'))
    status = columns.TemplateColumn(verbose_name=_('Status'), template_code=STATUS, order_by=('status',))
    approved_by = tables.Column(verbose_name=_('Approved by'), linkify=True)
    approved_on = columns.DateColumn(verbose_name=_('Approved on'))
    reviewed_on = columns.DateColumn(verbose_name=_('Last reviewed'))
    reviewed_by = tables.Column(verbose_name=_('Reviewed by'))
    review_by = columns.DateColumn(verbose_name=_('Review by'))
    expires = columns.DateColumn(verbose_name=_('Expires'))
    tags = columns.TagColumn(url_name='plugins:netbox_access_paths:accesspath_list')

    class Meta(PrimaryModelTable.Meta):
        model = AccessPath
        fields = (
            'pk', 'id', 'name', 'tenant', 'route', 'origin', 'target', 'target_url', 'chain', 'method', 'holders',
            'authentication', 'credential_ref', 'status', 'approved_by', 'approved_on', 'reviewed_on', 'reviewed_by',
            'review_by', 'expires',
            'description', 'comments', 'tags', 'created', 'last_updated',
        )
        default_columns = (
            'pk', 'name', 'tenant', 'target', 'chain', 'holders', 'authentication', 'status', 'review_by',
        )


class AccessHopTable(PrimaryModelTable):
    parent = tables.Column(verbose_name=_('Route or path'), linkify=True, orderable=False)
    position = tables.Column(verbose_name=_('Position'), linkify=True)
    hop = columns.TemplateColumn(
        verbose_name=_('Runs through'), orderable=False,
        template_code='{% if record.label %}{{ record.label }}{% else %}{{ record.hop|linkify }}{% endif %}',
    )
    route = tables.Column(verbose_name=_('Route'), linkify=True)
    path = tables.Column(verbose_name=_('Path'), linkify=True)
    tags = columns.TagColumn(url_name='plugins:netbox_access_paths:accesshop_list')

    class Meta(PrimaryModelTable.Meta):
        model = AccessHop
        fields = (
            'pk', 'id', 'parent', 'route', 'path', 'position', 'hop', 'label', 'description', 'comments', 'tags',
            'created', 'last_updated',
        )
        default_columns = ('pk', 'parent', 'position', 'hop', 'description')
