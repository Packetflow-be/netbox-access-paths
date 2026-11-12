from itertools import groupby

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.views.generic import View

from dcim.models import Device
from extras.ui.panels import CustomFieldsPanel, TagsPanel
from netbox.ui import actions, attrs, layout, panels
from netbox.views import generic
from tenancy.models import Contact, Tenant
from utilities.query import count_related
from utilities.views import ContentTypePermissionRequiredMixin, ViewTab, register_model_view
from virtualization.models import VirtualMachine

from . import export, filtersets, forms, queries, tables
from .models import AccessHop, AccessPath, AccessRoute

HOP_RELATED = ('hops__device', 'hops__virtual_machine', 'hops__tunnel')
ROUTE_HOP_RELATED = tuple(f'route__{h}' for h in HOP_RELATED)


def path_queryset(queryset=None):
    """Paths with everything the tables, chains and exports show, without a query per row."""
    queryset = AccessPath.objects.all() if queryset is None else queryset
    return queryset.select_related('tenant', 'route', 'approved_by', 'target_type').prefetch_related(
        'target', 'holders', 'holder_groups', *HOP_RELATED, *ROUTE_HOP_RELATED,
    )


#
# Panels
#

class ChainPanel(panels.Panel):
    """The path drawn left to right: origin, route hops, the path's own hops, method, target."""
    template_name = 'netbox_access_paths/inc/chain.html'
    title = _('Path')

    def get_context(self, context):
        obj = context['object']
        if isinstance(obj, AccessRoute):
            route, path = obj, None
        else:
            route, path = obj.route, obj
        return {
            **super().get_context(context),
            'route': route,
            'route_hops': list(route.hops.all()),
            'path': path,
            'path_hops': list(path.hops.all()) if path else [],
            'path_count': route.paths.count() if path is None else None,
        }


class AccessRoutePanel(panels.ObjectAttributesPanel):
    name = attrs.TextAttr('name')
    origin = attrs.ChoiceAttr('origin')
    origin_prefixes = attrs.RelatedObjectListAttr('origin_prefixes', linkify=True, label=_('Origin prefixes'))
    tenant = attrs.RelatedObjectAttr('tenant', linkify=True, grouped_by='group')
    description = attrs.TextAttr('description')


class AccessPathPanel(panels.ObjectAttributesPanel):
    name = attrs.TextAttr('name')
    tenant = attrs.RelatedObjectAttr('tenant', linkify=True, label=_('Customer'))
    route = attrs.RelatedObjectAttr('route', linkify=True)
    # Accessor pk: a URL-only or missing target must still render the template, not the empty placeholder
    target = attrs.TemplatedAttr('pk', label=_('Target'), template_name='netbox_access_paths/inc/target_attr.html')
    method = attrs.ChoiceAttr('method')
    status = attrs.TemplatedAttr('status', label=_('Status'), template_name='netbox_access_paths/inc/status_attr.html')
    description = attrs.TextAttr('description')


class AccessPathWhoPanel(panels.ObjectAttributesPanel):
    holders = attrs.RelatedObjectListAttr('holders', linkify=True, label=_('Holders'))
    holder_groups = attrs.RelatedObjectListAttr('holder_groups', linkify=True, label=_('Holder groups'))
    authentication = attrs.TemplatedAttr(
        'authentication', label=_('Authentication'), template_name='netbox_access_paths/inc/authentication_attr.html',
    )
    credential_ref = attrs.TextAttr('credential_ref', label=_('Credential reference'), style='font-monospace')


class AccessPathApprovalPanel(panels.ObjectAttributesPanel):
    approved_by = attrs.RelatedObjectAttr('approved_by', linkify=True, label=_('Approved by'))
    approved_on = attrs.DateTimeAttr('approved_on', spec='date', label=_('Approved on'))
    review_by = attrs.DateTimeAttr('review_by', spec='date', label=_('Review by'))
    expires = attrs.DateTimeAttr('expires', spec='date', label=_('Expires'))


class AccessHopPanel(panels.ObjectAttributesPanel):
    route = attrs.RelatedObjectAttr('route', linkify=True)
    path = attrs.RelatedObjectAttr('path', linkify=True)
    position = attrs.TextAttr('position')
    device = attrs.RelatedObjectAttr('device', linkify=True)
    virtual_machine = attrs.RelatedObjectAttr('virtual_machine', linkify=True, label=_('Virtual machine'))
    tunnel = attrs.RelatedObjectAttr('tunnel', linkify=True)
    label = attrs.TextAttr('label')
    description = attrs.TextAttr('description')


def _hops_panel(field, title):
    return panels.ObjectsTablePanel(
        'netbox_access_paths.accesshop',
        filters={f'{field}_id': lambda ctx: ctx['object'].pk},
        exclude_columns=['parent', 'route', 'path'],
        title=title,
        actions=[
            actions.AddObject('netbox_access_paths.accesshop', label=_('Add hop'),
                              url_params={field: lambda ctx: ctx['object'].pk}),
        ],
    )


#
# Routes
#

@register_model_view(AccessRoute, 'list', path='', detail=False)
class AccessRouteListView(generic.ObjectListView):
    queryset = AccessRoute.objects.annotate(path_count=count_related(AccessPath, 'route')).select_related(
        'tenant').prefetch_related('origin_prefixes', *HOP_RELATED)
    filterset = filtersets.AccessRouteFilterSet
    filterset_form = forms.AccessRouteFilterForm
    table = tables.AccessRouteTable


@register_model_view(AccessRoute)
class AccessRouteView(generic.ObjectView):
    queryset = AccessRoute.objects.all()
    template_name = 'generic/object.html'
    layout = layout.SimpleLayout(
        left_panels=[AccessRoutePanel(), TagsPanel()],
        right_panels=[ChainPanel(title=_('Route')), CustomFieldsPanel(), panels.CommentsPanel()],
        bottom_panels=[
            _hops_panel('route', _('Hops (MSP side, in order)')),
            panels.ObjectsTablePanel(
                'netbox_access_paths.accesspath',
                filters={'route_id': lambda ctx: ctx['object'].pk},
                exclude_columns=['route'],
                title=_('Paths on this route'),
                actions=[
                    actions.AddObject('netbox_access_paths.accesspath', label=_('Add path'),
                                      url_params={'route': lambda ctx: ctx['object'].pk}),
                ],
            ),
        ],
    )


@register_model_view(AccessRoute, 'add', detail=False)
@register_model_view(AccessRoute, 'edit')
class AccessRouteEditView(generic.ObjectEditView):
    queryset = AccessRoute.objects.all()
    form = forms.AccessRouteForm


@register_model_view(AccessRoute, 'delete')
class AccessRouteDeleteView(generic.ObjectDeleteView):
    queryset = AccessRoute.objects.all()


@register_model_view(AccessRoute, 'bulk_import', path='import', detail=False)
class AccessRouteBulkImportView(generic.BulkImportView):
    queryset = AccessRoute.objects.all()
    model_form = forms.AccessRouteImportForm


@register_model_view(AccessRoute, 'bulk_edit', path='edit', detail=False)
class AccessRouteBulkEditView(generic.BulkEditView):
    queryset = AccessRoute.objects.all()
    filterset = filtersets.AccessRouteFilterSet
    table = tables.AccessRouteTable
    form = forms.AccessRouteBulkEditForm


@register_model_view(AccessRoute, 'bulk_delete', path='delete', detail=False)
class AccessRouteBulkDeleteView(generic.BulkDeleteView):
    queryset = AccessRoute.objects.all()
    filterset = filtersets.AccessRouteFilterSet
    table = tables.AccessRouteTable


#
# Paths
#

@register_model_view(AccessPath, 'list', path='', detail=False)
class AccessPathListView(generic.ObjectListView):
    queryset = path_queryset()
    filterset = filtersets.AccessPathFilterSet
    filterset_form = forms.AccessPathFilterForm
    table = tables.AccessPathTable
    template_name = 'netbox_access_paths/accesspath_list.html'


@register_model_view(AccessPath)
class AccessPathView(generic.ObjectView):
    queryset = AccessPath.objects.select_related('tenant', 'route', 'approved_by')
    template_name = 'generic/object.html'
    layout = layout.Layout(
        layout.Row(layout.Column(ChainPanel())),
        layout.Row(
            layout.Column(
                AccessPathPanel(),
                AccessPathWhoPanel(title=_('Who and how')),
                TagsPanel(),
                panels.PluginContentPanel('left_page'),
            ),
            layout.Column(
                AccessPathApprovalPanel(title=_('Approval and review')),
                CustomFieldsPanel(),
                panels.CommentsPanel(),
                panels.PluginContentPanel('right_page'),
            ),
        ),
        layout.Row(layout.Column(
            _hops_panel('path', _('Customer-side hops (after the route, in order)')),
            panels.PluginContentPanel('full_width_page'),
        )),
    )


@register_model_view(AccessPath, 'add', detail=False)
@register_model_view(AccessPath, 'edit')
class AccessPathEditView(generic.ObjectEditView):
    queryset = AccessPath.objects.all()
    form = forms.AccessPathForm


@register_model_view(AccessPath, 'delete')
class AccessPathDeleteView(generic.ObjectDeleteView):
    queryset = AccessPath.objects.all()


@register_model_view(AccessPath, 'bulk_import', path='import', detail=False)
class AccessPathBulkImportView(generic.BulkImportView):
    queryset = AccessPath.objects.all()
    model_form = forms.AccessPathImportForm


@register_model_view(AccessPath, 'bulk_edit', path='edit', detail=False)
class AccessPathBulkEditView(generic.BulkEditView):
    queryset = path_queryset()
    filterset = filtersets.AccessPathFilterSet
    table = tables.AccessPathTable
    form = forms.AccessPathBulkEditForm


@register_model_view(AccessPath, 'bulk_delete', path='delete', detail=False)
class AccessPathBulkDeleteView(generic.BulkDeleteView):
    queryset = path_queryset()
    filterset = filtersets.AccessPathFilterSet
    table = tables.AccessPathTable


#
# Hops
#

@register_model_view(AccessHop, 'list', path='', detail=False)
class AccessHopListView(generic.ObjectListView):
    queryset = AccessHop.objects.select_related('route', 'path', 'device', 'virtual_machine', 'tunnel')
    filterset = filtersets.AccessHopFilterSet
    filterset_form = forms.AccessHopFilterForm
    table = tables.AccessHopTable


@register_model_view(AccessHop)
class AccessHopView(generic.ObjectView):
    queryset = AccessHop.objects.all()
    template_name = 'generic/object.html'
    layout = layout.SimpleLayout(
        left_panels=[AccessHopPanel(), TagsPanel()],
        right_panels=[CustomFieldsPanel(), panels.CommentsPanel()],
    )


@register_model_view(AccessHop, 'add', detail=False)
@register_model_view(AccessHop, 'edit')
class AccessHopEditView(generic.ObjectEditView):
    queryset = AccessHop.objects.all()
    form = forms.AccessHopForm


@register_model_view(AccessHop, 'delete')
class AccessHopDeleteView(generic.ObjectDeleteView):
    queryset = AccessHop.objects.all()


@register_model_view(AccessHop, 'bulk_import', path='import', detail=False)
class AccessHopBulkImportView(generic.BulkImportView):
    queryset = AccessHop.objects.all()
    model_form = forms.AccessHopImportForm


@register_model_view(AccessHop, 'bulk_edit', path='edit', detail=False)
class AccessHopBulkEditView(generic.BulkEditView):
    queryset = AccessHop.objects.all()
    filterset = filtersets.AccessHopFilterSet
    table = tables.AccessHopTable
    form = forms.AccessHopBulkEditForm


@register_model_view(AccessHop, 'bulk_delete', path='delete', detail=False)
class AccessHopBulkDeleteView(generic.BulkDeleteView):
    queryset = AccessHop.objects.all()
    filterset = filtersets.AccessHopFilterSet
    table = tables.AccessHopTable


#
# Tabs on tenants and contacts
#

@register_model_view(Tenant, name='access_paths', path='access-paths')
class TenantAccessPathsView(generic.ObjectChildrenView):
    """Every way into this customer, with the questionnaire export."""
    queryset = Tenant.objects.all()
    child_model = AccessPath
    table = tables.AccessPathTable
    filterset = filtersets.AccessPathFilterSet
    template_name = 'netbox_access_paths/tenant_paths.html'
    tab = ViewTab(
        label=_('Access paths'),
        badge=lambda tenant: AccessPath.objects.filter(tenant=tenant).count(),
        permission='netbox_access_paths.view_accesspath',
        weight=2200,
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return path_queryset(AccessPath.objects.restrict(request.user, 'view').filter(tenant=parent))


def _held_by(contact):
    return AccessPath.objects.filter(queries.held_by_q([contact])).distinct()


@register_model_view(Contact, name='access_paths', path='access-paths')
class ContactAccessPathsView(generic.ObjectChildrenView):
    """Everything this person can reach, directly or through a group: the offboarding list."""
    queryset = Contact.objects.all()
    child_model = AccessPath
    table = tables.AccessPathTable
    filterset = filtersets.AccessPathFilterSet
    template_name = 'netbox_access_paths/contact_paths.html'
    tab = ViewTab(
        label=_('Access paths'),
        badge=lambda contact: _held_by(contact).count(),
        permission='netbox_access_paths.view_accesspath',
        weight=2200,
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        visible = AccessPath.objects.restrict(request.user, 'view')
        return path_queryset(visible.filter(pk__in=_held_by(parent).values('pk')))


#
# Tabs on devices and virtual machines: what runs through it, what leads into it
#

def _asset_field(obj):
    return 'device' if isinstance(obj, Device) else 'virtual_machine'


def _into(obj):
    if isinstance(obj, Device):
        return queries.into_q(devices=[obj])
    return queries.into_q(virtual_machines=[obj])


def asset_badge(obj):
    q = queries.through_q(_asset_field(obj), [obj]) | _into(obj)
    return AccessPath.objects.filter(q).distinct().count()


class AssetAccessPathsView(generic.ObjectView):
    template_name = 'netbox_access_paths/asset_paths.html'

    def get_extra_context(self, request, instance):
        field = _asset_field(instance)
        visible = AccessPath.objects.restrict(request.user, 'view')
        routes = AccessRoute.objects.restrict(request.user, 'view').filter(**{f'hops__{field}': instance}) \
            .distinct().prefetch_related(*HOP_RELATED)
        through = path_queryset(visible.filter(queries.through_q(field, [instance])).distinct()) \
            .order_by('tenant__name', 'name')
        into = path_queryset(visible.filter(_into(instance))).order_by('tenant__name', 'name')
        through = list(through)
        return {
            'routes': routes,
            'through_by_tenant': [(tenant, list(paths)) for tenant, paths in groupby(through, key=lambda p: p.tenant)],
            'through_count': len(through),
            'into': into,
            'today': timezone.localdate(),
        }


@register_model_view(Device, name='access_paths', path='access-paths')
class DeviceAccessPathsView(AssetAccessPathsView):
    queryset = Device.objects.all()
    tab = ViewTab(
        label=_('Access paths'),
        badge=asset_badge,
        permission='netbox_access_paths.view_accesspath',
        weight=2200,
        hide_if_empty=True,
    )


@register_model_view(VirtualMachine, name='access_paths', path='access-paths')
class VirtualMachineAccessPathsView(AssetAccessPathsView):
    queryset = VirtualMachine.objects.all()
    tab = ViewTab(
        label=_('Access paths'),
        badge=asset_badge,
        permission='netbox_access_paths.view_accesspath',
        weight=2200,
        hide_if_empty=True,
    )


#
# Review queue and the questionnaire export
#

REVIEW_SECTIONS = (
    ('expired', _('Expired'), queries.expired_q, 'expires',
     _('Past their expiry date but not disabled: remove the access, or extend it and record who approved that.')),
    ('review_due', _('Review due'), queries.review_due_q, 'review_by',
     _('Review date reached: confirm the path is still needed, then set the next review date.')),
    ('lacks_mfa', _('Without MFA'), queries.lacks_mfa_q, None,
     _('Password-only, shared account or unknown authentication.')),
    ('break_glass', _('Break-glass'), queries.break_glass_q, None,
     _('Emergency-only paths: check they are still sealed and who can open them.')),
    ('target_missing', _('Target missing'), queries.target_missing_q, None,
     _('The target was deleted from NetBox: point the path at its new target or disable it.')),
)
REVIEW_LIMIT = 50


class ReviewView(ContentTypePermissionRequiredMixin, View):
    """Paths that need a person: expired, review due, no MFA, break-glass, target gone."""

    def get_required_permission(self):
        return 'netbox_access_paths.view_accesspath'

    def get(self, request):
        visible = AccessPath.objects.restrict(request.user, 'view')
        form = forms.ReviewFilterForm(request.GET or None)
        tenant = None
        if form.is_valid() and (tenant := form.cleaned_data.get('tenant_id')):
            if not Tenant.objects.restrict(request.user, 'view').filter(pk=tenant.pk).exists():
                tenant = None
                visible = visible.none()
            else:
                visible = visible.filter(tenant=tenant)
        sections = []
        for key, title, q, date_field, help_text in REVIEW_SECTIONS:
            matching = visible.filter(q())
            if date_field:
                matching = matching.order_by(date_field, 'tenant__name', 'name')
            else:
                matching = matching.order_by('tenant__name', 'name')
            sections.append({
                'key': key,
                'title': title,
                'help_text': help_text,
                'date_field': date_field,
                'count': matching.count(),
                'paths': path_queryset(matching)[:REVIEW_LIMIT],
            })
        return render(request, 'netbox_access_paths/review.html', {
            'form': form,
            'sections': sections,
            'tenant': tenant,
            'total': visible.filter(queries.needs_review_q()).count(),
            'limit': REVIEW_LIMIT,
        })


class ExportView(ContentTypePermissionRequiredMixin, View):
    """
    The questionnaire export (CSV or Markdown) of the paths matching the usual filters, e.g. ?tenant_id=4.
    """

    def get_required_permission(self):
        return 'netbox_access_paths.view_accesspath'

    def get(self, request):
        fmt = request.GET.get('format', 'csv')
        if fmt not in export.FORMATS:
            return HttpResponse(_('Unknown format; use csv or markdown.'), status=400, content_type='text/plain')
        params = request.GET.copy()
        params.pop('format', None)
        visible = AccessPath.objects.restrict(request.user, 'view')
        paths = filtersets.AccessPathFilterSet(params, visible, request=request).qs
        paths = path_queryset(paths).order_by('tenant__name', 'name')
        tenants = {p.tenant for p in paths}
        scope = next(iter(tenants)).name if len(tenants) == 1 else _('all customers')
        credential_ref = export.include_credential_ref()
        rows = export.build_rows(paths)
        filename = f'access-paths-{slugify(scope)}-{timezone.localdate().isoformat()}'
        if fmt == 'markdown':
            body = export.to_markdown(rows, _('Access paths: {scope}').format(scope=scope), credential_ref)
            response = HttpResponse(body, content_type='text/markdown; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}.md"'
        else:
            response = HttpResponse(export.to_csv(rows, credential_ref), content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        return response
