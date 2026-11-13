import django_filters
from django.db.models import Q
from django.utils.translation import gettext as _

from dcim.models import Device
from ipam.models import Prefix
from netbox.filtersets import PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from tenancy.models import Contact, ContactGroup, Tenant
from users.models import User
from utilities.filters import MultiValueContentTypeFilter, MultiValueNumberFilter
from utilities.filtersets import register_filterset
from virtualization.models import VirtualMachine
from vpn.models import Tunnel

from . import queries
from .choices import AccessMethodChoices, AccessPathStatusChoices, AuthenticationChoices, OriginChoices
from .models import AccessHop, AccessPath, AccessRoute

__all__ = ('AccessHopFilterSet', 'AccessPathFilterSet', 'AccessRouteFilterSet')


class HopFilterMixin(django_filters.FilterSet):
    """Runs through a device, VM or tunnel: on the route or on the path itself."""
    hop_device_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Device.objects.all(), method='filter_hop', label=_('Runs through device (ID)'),
    )
    hop_virtual_machine_id = django_filters.ModelMultipleChoiceFilter(
        queryset=VirtualMachine.objects.all(), method='filter_hop', label=_('Runs through virtual machine (ID)'),
    )
    hop_tunnel_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Tunnel.objects.all(), method='filter_hop', label=_('Runs through tunnel (ID)'),
    )
    hop_prefix = ''

    def filter_hop(self, queryset, name, value):
        if not value:
            return queryset
        field = name.removeprefix('hop_').removesuffix('_id')
        return queryset.filter(queries.through_q(field, value, prefix=self.hop_prefix)).distinct()


def _boolean(method, label):
    return django_filters.BooleanFilter(method=method, label=label)


@register_filterset
class AccessRouteFilterSet(PrimaryModelFilterSet, TenancyFilterSet):
    origin = django_filters.MultipleChoiceFilter(choices=OriginChoices, distinct=False)
    origin_prefix_id = django_filters.ModelMultipleChoiceFilter(
        field_name='origin_prefixes', queryset=Prefix.objects.all(), label=_('Origin prefix (ID)'),
    )
    hop_device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='hops__device', queryset=Device.objects.all(), label=_('Runs through device (ID)'),
    )
    hop_virtual_machine_id = django_filters.ModelMultipleChoiceFilter(
        field_name='hops__virtual_machine', queryset=VirtualMachine.objects.all(),
        label=_('Runs through virtual machine (ID)'),
    )
    hop_tunnel_id = django_filters.ModelMultipleChoiceFilter(
        field_name='hops__tunnel', queryset=Tunnel.objects.all(), label=_('Runs through tunnel (ID)'),
    )

    class Meta:
        model = AccessRoute
        fields = ('id', 'name', 'description')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(comments__icontains=value) |
            Q(hops__label__icontains=value)
        ).distinct()


@register_filterset
class AccessPathFilterSet(HopFilterMixin, PrimaryModelFilterSet, TenancyFilterSet):
    route_id = django_filters.ModelMultipleChoiceFilter(
        queryset=AccessRoute.objects.all(), distinct=False, label=_('Route (ID)'),
    )
    route = django_filters.ModelMultipleChoiceFilter(
        field_name='route__name', queryset=AccessRoute.objects.all(), to_field_name='name', distinct=False,
        label=_('Route (name)'),
    )
    origin = django_filters.MultipleChoiceFilter(
        field_name='route__origin', choices=OriginChoices, distinct=False, label=_('Origin'),
    )
    target_type = MultiValueContentTypeFilter()
    target_id = MultiValueNumberFilter()
    device_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Device.objects.all(), method='filter_into', label=_('Into device, its services, IPs or scopes (ID)'),
    )
    virtual_machine_id = django_filters.ModelMultipleChoiceFilter(
        queryset=VirtualMachine.objects.all(), method='filter_into',
        label=_('Into virtual machine, its services, IPs or scopes (ID)'),
    )
    method = django_filters.MultipleChoiceFilter(choices=AccessMethodChoices, distinct=False)
    authentication = django_filters.MultipleChoiceFilter(choices=AuthenticationChoices, distinct=False)
    status = django_filters.MultipleChoiceFilter(choices=AccessPathStatusChoices, distinct=False)
    holder_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Contact.objects.all(), method='filter_holder', label=_('Holder, directly or through a group (ID)'),
    )
    holder_group_id = django_filters.ModelMultipleChoiceFilter(
        field_name='holder_groups', queryset=ContactGroup.objects.all(), label=_('Holder group (ID)'),
    )
    approved_by_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Contact.objects.all(), distinct=False, label=_('Approved by (ID)'),
    )
    reviewed_by_id = django_filters.ModelMultipleChoiceFilter(
        queryset=User.objects.all(), distinct=False, label=_('Reviewed by (ID)'),
    )
    expired = _boolean('filter_flag', _('Expired'))
    review_due = _boolean('filter_flag', _('Review due'))
    lacks_mfa = _boolean('filter_flag', _('Without MFA'))
    break_glass = _boolean('filter_flag', _('Break-glass'))
    target_missing = _boolean('filter_flag', _('Target missing'))
    needs_review = _boolean('filter_flag', _('Needs review (any reason)'))

    FLAGS = {
        'expired': queries.expired_q,
        'review_due': queries.review_due_q,
        'lacks_mfa': queries.lacks_mfa_q,
        'break_glass': queries.break_glass_q,
        'target_missing': queries.target_missing_q,
        'needs_review': queries.needs_review_q,
    }

    class Meta:
        model = AccessPath
        fields = (
            'id', 'name', 'target_url', 'credential_ref', 'approved_on', 'reviewed_on', 'review_by', 'expires',
            'description',
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(target_url__icontains=value) |
            Q(credential_ref__icontains=value) |
            Q(description__icontains=value) |
            Q(comments__icontains=value) |
            Q(route__name__icontains=value) |
            Q(tenant__name__icontains=value)
        )

    def filter_into(self, queryset, name, value):
        if not value:
            return queryset
        if name == 'device_id':
            return queryset.filter(queries.into_q(devices=value))
        return queryset.filter(queries.into_q(virtual_machines=value))

    def filter_holder(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(queries.held_by_q(value)).distinct()

    def filter_flag(self, queryset, name, value):
        if value is None:
            return queryset
        q = self.FLAGS[name]()
        return queryset.filter(q) if value else queryset.exclude(q)


@register_filterset
class AccessHopFilterSet(PrimaryModelFilterSet):
    route_id = django_filters.ModelMultipleChoiceFilter(
        queryset=AccessRoute.objects.all(), distinct=False, label=_('Route (ID)'),
    )
    path_id = django_filters.ModelMultipleChoiceFilter(
        queryset=AccessPath.objects.all(), distinct=False, label=_('Path (ID)'),
    )
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        field_name='path__tenant', queryset=Tenant.objects.all(), distinct=False, label=_('Path tenant (ID)'),
    )
    on_route = django_filters.BooleanFilter(
        field_name='route', lookup_expr='isnull', exclude=True, label=_('On a route (MSP side)'),
    )
    device_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Device.objects.all(), distinct=False, label=_('Device (ID)'),
    )
    virtual_machine_id = django_filters.ModelMultipleChoiceFilter(
        queryset=VirtualMachine.objects.all(), distinct=False, label=_('Virtual machine (ID)'),
    )
    tunnel_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Tunnel.objects.all(), distinct=False, label=_('Tunnel (ID)'),
    )

    class Meta:
        model = AccessHop
        fields = ('id', 'position', 'label', 'description')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(label__icontains=value) |
            Q(route__name__icontains=value) |
            Q(path__name__icontains=value) |
            Q(device__name__icontains=value) |
            Q(virtual_machine__name__icontains=value) |
            Q(tunnel__name__icontains=value) |
            Q(description__icontains=value)
        )
