"""
Shared lookups: paths into an asset (directly or through a scope), paths through an asset, paths a contact holds,
paths that need attention.
"""
from functools import reduce
from operator import or_

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .choices import AccessPathStatusChoices, AuthenticationChoices
from .utils import plugin_setting

HOP_FIELDS = ('device', 'virtual_machine', 'tunnel')


def _pks(objects):
    return [getattr(o, 'pk', o) for o in objects]


def _ct(model):
    return ContentType.objects.get_for_model(model)


def _direct_q(model, ids, ip_lookup):
    """Paths whose target is one of these devices or VMs, or one of their application services or IP addresses."""
    from ipam.models import IPAddress, Service

    ct = _ct(model)
    services = Service.objects.filter(parent_object_type=ct, parent_object_id__in=ids).values('pk')
    addresses = IPAddress.objects.filter(**{ip_lookup: ids}).values('pk')
    return (
        Q(target_type=ct, target_id__in=ids) |
        Q(target_type=_ct(Service), target_id__in=services) |
        Q(target_type=_ct(IPAddress), target_id__in=addresses)
    )


def scope_q(asset):
    """
    Paths whose target is a scope this device or VM sits in: its site, its cluster, a prefix that holds one of its
    IP addresses (same VRF), a VLAN (of such a prefix, or on one of its interfaces), or its tenant as a whole.

    With the plugin setting scope_same_tenant (the default) a site, cluster, prefix or VLAN path covers the asset
    only when the asset belongs to the path's tenant or to no tenant: customers share address space and clusters.
    """
    from dcim.models import Device, Interface, Site
    from ipam.models import VLAN, IPAddress, Prefix
    from tenancy.models import Tenant
    from virtualization.models import Cluster, VMInterface

    if isinstance(asset, Device):
        interfaces = Interface.objects.filter(device=asset)
        addresses = IPAddress.objects.filter(interface__device=asset)
        tagged = Interface.tagged_vlans.through.objects.filter(interface__device=asset)
    else:
        interfaces = VMInterface.objects.filter(virtual_machine=asset)
        addresses = IPAddress.objects.filter(vminterface__virtual_machine=asset)
        tagged = VMInterface.tagged_vlans.through.objects.filter(vminterface__virtual_machine=asset)

    terms = []
    if asset.site_id:
        terms.append(Q(target_type=_ct(Site), target_id=asset.site_id))
    if asset.cluster_id:
        terms.append(Q(target_type=_ct(Cluster), target_id=asset.cluster_id))

    containing = [
        Q(prefix__net_contains_or_equals=str(address.ip), vrf_id=vrf_id)
        for address, vrf_id in addresses.values_list('address', 'vrf_id')
    ]
    vlans = Q(pk__in=interfaces.filter(untagged_vlan__isnull=False).values('untagged_vlan')) | Q(
        pk__in=tagged.values('vlan_id'))
    if containing:
        prefixes = Prefix.objects.filter(reduce(or_, containing))
        terms.append(Q(target_type=_ct(Prefix), target_id__in=prefixes.values('pk')))
        vlans |= Q(pk__in=prefixes.filter(vlan__isnull=False).values('vlan'))
    terms.append(Q(target_type=_ct(VLAN), target_id__in=VLAN.objects.filter(vlans).values('pk')))

    q = reduce(or_, terms)
    if asset.tenant_id:
        if plugin_setting('scope_same_tenant'):
            q &= Q(tenant_id=asset.tenant_id)
        q |= Q(target_type=_ct(Tenant), target_id=asset.tenant_id)
    return q


def into_q(devices=(), virtual_machines=(), scopes=True):
    """
    Paths into these devices or VMs: the target is the asset itself, one of its application services or IP
    addresses, or (with scopes) a prefix, VLAN, cluster, site or tenant it sits in.
    """
    from dcim.models import Device
    from virtualization.models import VirtualMachine

    terms = []
    for model, objects, ip_lookup in (
        (Device, devices, 'interface__device__in'),
        (VirtualMachine, virtual_machines, 'vminterface__virtual_machine__in'),
    ):
        ids = _pks(objects)
        if not ids:
            continue
        terms.append(_direct_q(model, ids, ip_lookup))
        if scopes:
            assets = [o for o in objects if isinstance(o, model)]
            if len(assets) != len(ids):
                assets = list(model.objects.filter(pk__in=ids))
            terms += [scope_q(asset) for asset in assets]
    return reduce(or_, terms) if terms else Q(pk__in=[])


def through_q(field, objects, prefix=''):
    """Paths (or, with prefix, objects related to paths) with a hop on this device/VM/tunnel, on the route or path."""
    ids = _pks(objects)
    return Q(**{f'{prefix}hops__{field}__in': ids}) | Q(**{f'{prefix}route__hops__{field}__in': ids})


def groups_with_ancestors(groups):
    """The groups and every group above them: a path granted to "Support" covers "Support / Tier 2" too."""
    seen = set()
    for group in groups:
        while group is not None and group.pk not in seen:
            seen.add(group.pk)
            group = group.parent
    return seen


def held_by_q(contacts):
    """Paths a contact may use: as a holder, or through one of their groups (or a group above it)."""
    from tenancy.models import ContactGroup

    ids = _pks(contacts)
    groups = groups_with_ancestors(ContactGroup.objects.filter(contact__in=ids).select_related('parent'))
    return Q(holders__in=ids) | Q(holder_groups__in=groups)


def live_q():
    return ~Q(status=AccessPathStatusChoices.DISABLED)


def expired_q():
    return live_q() & Q(expires__lt=timezone.localdate())


def review_due_q():
    return live_q() & Q(review_by__lte=timezone.localdate())


def lacks_mfa_q():
    return live_q() & Q(authentication__in=AuthenticationChoices.LACKS_MFA)


def break_glass_q():
    return Q(status=AccessPathStatusChoices.BREAK_GLASS)


def target_missing_q():
    return Q(target_type__isnull=True, target_url='')


def needs_review_q():
    """Any of the review queue's reasons."""
    return expired_q() | review_due_q() | lacks_mfa_q() | break_glass_q() | target_missing_q()


# The review queue's sections: key (also the list filter), title, query, date field to sort by, what to do
REVIEW_SECTIONS = (
    ('expired', _('Expired'), expired_q, 'expires',
     _('Past their expiry date but not disabled: remove the access, or extend it and record who approved that.')),
    ('review_due', _('Review due'), review_due_q, 'review_by',
     _('Review date reached: confirm the path is still needed, then mark it reviewed.')),
    ('lacks_mfa', _('Without MFA'), lacks_mfa_q, None,
     _('Password-only, shared account or unknown authentication.')),
    ('break_glass', _('Break-glass'), break_glass_q, None,
     _('Emergency-only paths: check they are still sealed and who can open them.')),
    ('target_missing', _('Target missing'), target_missing_q, None,
     _('The target was deleted from NetBox: point the path at its new target or disable it.')),
)
