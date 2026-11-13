from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, Site
from ipam.models import VLAN, IPAddress, Prefix, Service
from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
    PrimaryModelImportForm,
)
from tenancy.forms import TenancyFilterForm, TenancyForm
from tenancy.models import Contact, ContactGroup, Tenant
from utilities.forms import GenericObjectFormMixin, add_blank_choice
from utilities.forms.constants import BOOLEAN_WITH_BLANK_CHOICES
from utilities.forms.fields import (
    ContentTypeChoiceField,
    CSVChoiceField,
    CSVContentTypeField,
    CSVModelChoiceField,
    CSVModelMultipleChoiceField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    GenericObjectChoiceField,
    TagFilterField,
)
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import DatePicker
from virtualization.models import Cluster, VirtualMachine
from vpn.models import Tunnel

from .choices import AccessMethodChoices, AccessPathStatusChoices, AuthenticationChoices, OriginChoices
from .models import TARGET_MODELS, AccessHop, AccessPath, AccessRoute

__all__ = (
    'AccessHopBulkEditForm',
    'AccessHopFilterForm',
    'AccessHopForm',
    'AccessHopImportForm',
    'AccessPathBulkEditForm',
    'AccessPathFilterForm',
    'AccessPathForm',
    'AccessPathImportForm',
    'AccessRouteBulkEditForm',
    'AccessRouteFilterForm',
    'AccessRouteForm',
    'AccessRouteImportForm',
    'ReviewFilterForm',
)


def _yes_no(label):
    return forms.NullBooleanField(label=label, required=False, widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES))


#
# Routes
#

class AccessRouteForm(TenancyForm, PrimaryModelForm):
    origin_prefixes = DynamicModelMultipleChoiceField(
        label=_('Origin prefixes'), queryset=Prefix.objects.all(), required=False,
    )

    fieldsets = (
        FieldSet('name', 'origin', 'origin_prefixes', 'description', 'tags', name=_('Route')),
        FieldSet('tenant_group', 'tenant', name=_('Tenancy')),
    )

    class Meta:
        model = AccessRoute
        fields = ('name', 'origin', 'origin_prefixes', 'tenant_group', 'tenant', 'description', 'owner', 'comments',
                  'tags')


class AccessRouteBulkEditForm(PrimaryModelBulkEditForm):
    origin = forms.ChoiceField(label=_('Origin'), choices=add_blank_choice(OriginChoices), required=False)
    tenant = DynamicModelChoiceField(label=_('Tenant'), queryset=Tenant.objects.all(), required=False)

    model = AccessRoute
    fieldsets = (
        FieldSet('origin', 'tenant', 'description'),
    )
    nullable_fields = ('tenant', 'description', 'comments')


class AccessRouteImportForm(PrimaryModelImportForm):
    origin = CSVChoiceField(label=_('Origin'), choices=OriginChoices)
    origin_prefixes = CSVModelMultipleChoiceField(
        label=_('Origin prefixes'), queryset=Prefix.objects.all(), required=False, to_field_name='prefix',
        help_text=_('Comma-separated prefixes in double quotes, e.g. "10.0.10.0/24,10.0.20.0/24"'),
    )
    tenant = CSVModelChoiceField(label=_('Tenant'), queryset=Tenant.objects.all(), required=False,
                                 to_field_name='name')

    class Meta:
        model = AccessRoute
        fields = ('name', 'origin', 'origin_prefixes', 'tenant', 'description', 'owner', 'comments', 'tags')


class AccessRouteFilterForm(TenancyFilterForm, PrimaryModelFilterSetForm):
    model = AccessRoute
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('origin', 'origin_prefix_id', name=_('Origin')),
        FieldSet('hop_device_id', 'hop_virtual_machine_id', 'hop_tunnel_id', name=_('Hops')),
        FieldSet('tenant_group_id', 'tenant_id', name=_('Tenancy')),
        FieldSet('owner_group_id', 'owner_id', name=_('Ownership')),
    )
    origin = forms.MultipleChoiceField(label=_('Origin'), choices=OriginChoices, required=False)
    origin_prefix_id = DynamicModelMultipleChoiceField(
        queryset=Prefix.objects.all(), required=False, label=_('Origin prefix'),
    )
    hop_device_id = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(), required=False, label=_('Runs through device'),
    )
    hop_virtual_machine_id = DynamicModelMultipleChoiceField(
        queryset=VirtualMachine.objects.all(), required=False, label=_('Runs through virtual machine'),
    )
    hop_tunnel_id = DynamicModelMultipleChoiceField(
        queryset=Tunnel.objects.all(), required=False, label=_('Runs through tunnel'),
    )
    tag = TagFilterField(model)


#
# Paths
#

class AccessPathForm(GenericObjectFormMixin, PrimaryModelForm):
    tenant = DynamicModelChoiceField(label=_('Customer (tenant)'), queryset=Tenant.objects.all())
    route = DynamicModelChoiceField(label=_('Route'), queryset=AccessRoute.objects.all())
    target = GenericObjectChoiceField(
        label=_('Target'),
        content_type_queryset=ContentType.objects.filter(TARGET_MODELS),
        required=False,
        selector=True,
        hx_target_id='target',
        help_text=_('One device, virtual machine, application service or IP address; or a scope that stands '
                    'for everything in it: a prefix, VLAN, cluster, site or tenant'),
    )
    method = forms.ChoiceField(label=_('Method'), choices=AccessMethodChoices)
    holders = DynamicModelMultipleChoiceField(label=_('Holders'), queryset=Contact.objects.all(), required=False)
    holder_groups = DynamicModelMultipleChoiceField(
        label=_('Holder groups'), queryset=ContactGroup.objects.all(), required=False,
    )
    approved_by = DynamicModelChoiceField(label=_('Approved by'), queryset=Contact.objects.all(), required=False)

    fieldsets = (
        FieldSet('name', 'tenant', 'route', 'status', 'description', 'tags', name=_('Access path')),
        FieldSet('target', 'target_url', 'method', name=_('Target'), html_id='target'),
        FieldSet('holders', 'holder_groups', 'authentication', 'credential_ref', name=_('Who and how')),
        FieldSet('approved_by', 'approved_on', 'reviewed_on', 'review_by', 'expires',
                 name=_('Approval and review')),
    )

    class Meta:
        model = AccessPath
        fields = (
            'name', 'tenant', 'route', 'target_url', 'method', 'holders', 'holder_groups', 'authentication',
            'credential_ref', 'status', 'approved_by', 'approved_on', 'reviewed_on', 'review_by', 'expires',
            'description', 'owner', 'comments', 'tags',
        )
        widgets = {
            'approved_on': DatePicker(),
            'reviewed_on': DatePicker(),
            'review_by': DatePicker(),
            'expires': DatePicker(),
        }


class AccessPathBulkEditForm(PrimaryModelBulkEditForm):
    tenant = DynamicModelChoiceField(label=_('Customer (tenant)'), queryset=Tenant.objects.all(), required=False)
    route = DynamicModelChoiceField(label=_('Route'), queryset=AccessRoute.objects.all(), required=False)
    method = forms.ChoiceField(label=_('Method'), choices=add_blank_choice(AccessMethodChoices), required=False)
    authentication = forms.ChoiceField(
        label=_('Authentication'), choices=add_blank_choice(AuthenticationChoices), required=False,
    )
    status = forms.ChoiceField(label=_('Status'), choices=add_blank_choice(AccessPathStatusChoices), required=False)
    approved_by = DynamicModelChoiceField(label=_('Approved by'), queryset=Contact.objects.all(), required=False)
    approved_on = forms.DateField(label=_('Approved on'), required=False, widget=DatePicker())
    review_by = forms.DateField(label=_('Review by'), required=False, widget=DatePicker())
    expires = forms.DateField(label=_('Expires'), required=False, widget=DatePicker())

    model = AccessPath
    fieldsets = (
        FieldSet('tenant', 'route', 'method', 'status', 'description', name=_('Access path')),
        FieldSet('authentication', name=_('Who and how')),
        FieldSet('approved_by', 'approved_on', 'review_by', 'expires', name=_('Approval and review')),
    )
    nullable_fields = ('approved_by', 'approved_on', 'review_by', 'expires', 'description', 'comments')


class AccessPathImportForm(PrimaryModelImportForm):
    tenant = CSVModelChoiceField(label=_('Customer (tenant)'), queryset=Tenant.objects.all(), to_field_name='name')
    route = CSVModelChoiceField(label=_('Route'), queryset=AccessRoute.objects.all(), to_field_name='name')
    target_type = CSVContentTypeField(
        label=_('Target type'), queryset=ContentType.objects.filter(TARGET_MODELS), required=False,
        help_text=_('dcim.device, virtualization.virtualmachine, ipam.service or ipam.ipaddress; or a scope: '
                    'ipam.prefix, ipam.vlan, virtualization.cluster, dcim.site or tenancy.tenant'),
    )
    target = forms.CharField(
        label=_('Target'), required=False,
        help_text=_('Name of the device, VM, VLAN, cluster, site or tenant, or the IP address or prefix with '
                    'its mask; or give target_id'),
    )
    method = CSVChoiceField(label=_('Method'), choices=AccessMethodChoices)
    authentication = CSVChoiceField(label=_('Authentication'), choices=AuthenticationChoices, required=False)
    status = CSVChoiceField(label=_('Status'), choices=AccessPathStatusChoices, required=False)
    holders = CSVModelMultipleChoiceField(
        label=_('Holders'), queryset=Contact.objects.all(), required=False, to_field_name='name',
        help_text=_('Comma-separated contact names in double quotes'),
    )
    holder_groups = CSVModelMultipleChoiceField(
        label=_('Holder groups'), queryset=ContactGroup.objects.all(), required=False, to_field_name='name',
        help_text=_('Comma-separated contact group names in double quotes'),
    )
    approved_by = CSVModelChoiceField(
        label=_('Approved by'), queryset=Contact.objects.all(), required=False, to_field_name='name',
    )

    class Meta:
        model = AccessPath
        fields = (
            'name', 'tenant', 'route', 'target_type', 'target_id', 'target_url', 'method', 'holders',
            'holder_groups', 'authentication', 'credential_ref', 'status', 'approved_by', 'approved_on',
            'reviewed_on', 'review_by', 'expires', 'description', 'owner', 'comments', 'tags',
        )

    # Natural key of each target type for the "target" column
    TARGET_LOOKUPS = {
        Device: 'name',
        VirtualMachine: 'name',
        IPAddress: 'address',
        Service: None,  # names repeat across parents: give target_id
        Prefix: 'prefix',
        VLAN: 'name',
        Cluster: 'name',
        Site: 'name',
        Tenant: 'name',
    }

    # An empty cell means the default, as when the column is left out
    def clean_authentication(self):
        return self.cleaned_data.get('authentication') or AuthenticationChoices.UNKNOWN

    def clean_status(self):
        return self.cleaned_data.get('status') or AccessPathStatusChoices.ACTIVE

    def clean(self):
        super().clean()
        target_type = self.cleaned_data.get('target_type')
        name = self.cleaned_data.get('target')
        if target_type and name:
            model = target_type.model_class()
            field = self.TARGET_LOOKUPS.get(model)
            if field is None:
                raise forms.ValidationError({'target': _('Give a service by its ID (target_id).')})
            matches = list(model.objects.filter(**{field: name})[:2])
            if len(matches) != 1:
                raise forms.ValidationError({
                    'target': _('{count} objects named "{name}" found; give target_id instead.').format(
                        count=len(matches), name=name),
                })
            self.instance.target_id = self.cleaned_data['target_id'] = matches[0].pk
        return self.cleaned_data


class AccessPathFilterForm(TenancyFilterForm, PrimaryModelFilterSetForm):
    model = AccessPath
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('tenant_group_id', 'tenant_id', 'route_id', 'origin', 'status', name=_('Path')),
        FieldSet('target_type', 'device_id', 'virtual_machine_id', 'method', name=_('Target')),
        FieldSet('holder_id', 'holder_group_id', 'authentication', name=_('Who and how')),
        FieldSet('hop_device_id', 'hop_virtual_machine_id', 'hop_tunnel_id', name=_('Runs through')),
        FieldSet('needs_review', 'expired', 'review_due', 'lacks_mfa', 'break_glass', 'target_missing',
                 'approved_by_id', name=_('Review')),
        FieldSet('owner_group_id', 'owner_id', name=_('Ownership')),
    )
    route_id = DynamicModelMultipleChoiceField(queryset=AccessRoute.objects.all(), required=False, label=_('Route'))
    origin = forms.MultipleChoiceField(label=_('Origin'), choices=OriginChoices, required=False)
    status = forms.MultipleChoiceField(label=_('Status'), choices=AccessPathStatusChoices, required=False)
    target_type = ContentTypeChoiceField(
        queryset=ContentType.objects.filter(TARGET_MODELS), required=False, label=_('Target type'),
    )
    device_id = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(), required=False, label=_('Into device'),
        help_text=_('Directly, or through a prefix, VLAN, cluster, site or tenant it sits in'),
    )
    virtual_machine_id = DynamicModelMultipleChoiceField(
        queryset=VirtualMachine.objects.all(), required=False, label=_('Into virtual machine'),
    )
    method = forms.MultipleChoiceField(label=_('Method'), choices=AccessMethodChoices, required=False)
    holder_id = DynamicModelMultipleChoiceField(queryset=Contact.objects.all(), required=False, label=_('Holder'))
    holder_group_id = DynamicModelMultipleChoiceField(
        queryset=ContactGroup.objects.all(), required=False, label=_('Holder group'),
    )
    authentication = forms.MultipleChoiceField(
        label=_('Authentication'), choices=AuthenticationChoices, required=False,
    )
    hop_device_id = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(), required=False, label=_('Device'),
    )
    hop_virtual_machine_id = DynamicModelMultipleChoiceField(
        queryset=VirtualMachine.objects.all(), required=False, label=_('Virtual machine'),
    )
    hop_tunnel_id = DynamicModelMultipleChoiceField(
        queryset=Tunnel.objects.all(), required=False, label=_('Tunnel'),
    )
    needs_review = _yes_no(_('Needs review (any reason)'))
    expired = _yes_no(_('Expired'))
    review_due = _yes_no(_('Review due'))
    lacks_mfa = _yes_no(_('Without MFA'))
    break_glass = _yes_no(_('Break-glass'))
    target_missing = _yes_no(_('Target missing'))
    approved_by_id = DynamicModelMultipleChoiceField(
        queryset=Contact.objects.all(), required=False, label=_('Approved by'),
    )
    tag = TagFilterField(model)


class ReviewFilterForm(forms.Form):
    tenant_id = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, label=_('Customer (tenant)'))


#
# Hops
#

class AccessHopForm(PrimaryModelForm):
    route = DynamicModelChoiceField(label=_('Route'), queryset=AccessRoute.objects.all(), required=False)
    path = DynamicModelChoiceField(label=_('Path'), queryset=AccessPath.objects.all(), required=False)
    device = DynamicModelChoiceField(label=_('Device'), queryset=Device.objects.all(), required=False)
    virtual_machine = DynamicModelChoiceField(
        label=_('Virtual machine'), queryset=VirtualMachine.objects.all(), required=False,
    )
    tunnel = DynamicModelChoiceField(label=_('Tunnel'), queryset=Tunnel.objects.all(), required=False)

    fieldsets = (
        FieldSet('route', 'path', 'position', 'description', 'tags', name=_('On (one of)')),
        FieldSet('device', 'virtual_machine', 'tunnel', 'label', name=_('Runs through (one of)')),
    )

    class Meta:
        model = AccessHop
        fields = ('route', 'path', 'position', 'device', 'virtual_machine', 'tunnel', 'label', 'description', 'owner',
                  'comments', 'tags')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A new hop goes after the last one of its route or path
        if self.instance.pk or self.initial.get('position'):
            return
        for field in ('route', 'path'):
            if parent_id := self.initial.get(field):
                last = AccessHop.objects.filter(**{f'{field}_id': parent_id}).order_by('-position') \
                    .values_list('position', flat=True).first()
                self.initial['position'] = (last or 0) + 1
                break


class AccessHopBulkEditForm(PrimaryModelBulkEditForm):
    label = forms.CharField(label=_('Label'), max_length=100, required=False)

    model = AccessHop
    fieldsets = (
        FieldSet('label', 'description'),
    )
    nullable_fields = ('description', 'comments')


class AccessHopImportForm(PrimaryModelImportForm):
    route = CSVModelChoiceField(label=_('Route'), queryset=AccessRoute.objects.all(), required=False,
                                to_field_name='name', help_text=_('Route name (or give path)'))
    path = CSVModelChoiceField(label=_('Path'), queryset=AccessPath.objects.all(), required=False,
                               to_field_name='pk', help_text=_('Path ID (or give route)'))
    device = CSVModelChoiceField(label=_('Device'), queryset=Device.objects.all(), required=False,
                                 to_field_name='name')
    virtual_machine = CSVModelChoiceField(label=_('Virtual machine'), queryset=VirtualMachine.objects.all(),
                                          required=False, to_field_name='name')
    tunnel = CSVModelChoiceField(label=_('Tunnel'), queryset=Tunnel.objects.all(), required=False,
                                 to_field_name='name')

    class Meta:
        model = AccessHop
        fields = ('route', 'path', 'position', 'device', 'virtual_machine', 'tunnel', 'label', 'description', 'owner',
                  'comments', 'tags')


class AccessHopFilterForm(PrimaryModelFilterSetForm):
    model = AccessHop
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('route_id', 'path_id', 'tenant_id', 'on_route', name=_('On')),
        FieldSet('device_id', 'virtual_machine_id', 'tunnel_id', 'label', name=_('Runs through')),
    )
    route_id = DynamicModelMultipleChoiceField(queryset=AccessRoute.objects.all(), required=False, label=_('Route'))
    path_id = DynamicModelMultipleChoiceField(queryset=AccessPath.objects.all(), required=False, label=_('Path'))
    tenant_id = DynamicModelMultipleChoiceField(
        queryset=Tenant.objects.all(), required=False, label=_('Customer (tenant) of the path'),
    )
    on_route = _yes_no(_('On a route (MSP side)'))
    device_id = DynamicModelMultipleChoiceField(queryset=Device.objects.all(), required=False, label=_('Device'))
    virtual_machine_id = DynamicModelMultipleChoiceField(
        queryset=VirtualMachine.objects.all(), required=False, label=_('Virtual machine'),
    )
    tunnel_id = DynamicModelMultipleChoiceField(queryset=Tunnel.objects.all(), required=False, label=_('Tunnel'))
    label = forms.CharField(label=_('Label'), required=False)
    tag = TagFilterField(model)
