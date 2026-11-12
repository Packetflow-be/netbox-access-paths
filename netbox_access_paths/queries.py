"""Shared lookups: paths into an asset, paths through an asset, paths a contact holds, paths that need attention."""
from functools import reduce
from operator import or_

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils import timezone

from .choices import AccessPathStatusChoices, AuthenticationChoices

HOP_FIELDS = ('device', 'virtual_machine', 'tunnel')


def _pks(objects):
    return [getattr(o, 'pk', o) for o in objects]


def into_q(devices=(), virtual_machines=()):
    """
    Paths whose target is one of these devices or VMs, or one of their application services or IP addresses.
    """
    from dcim.models import Device
    from ipam.models import IPAddress, Service
    from virtualization.models import VirtualMachine

    get_ct = ContentType.objects.get_for_model
    service_ct, ip_ct = get_ct(Service), get_ct(IPAddress)
    terms = []
    for model, ids, ip_lookup in (
        (Device, _pks(devices), 'interface__device__in'),
        (VirtualMachine, _pks(virtual_machines), 'vminterface__virtual_machine__in'),
    ):
        if not ids:
            continue
        ct = get_ct(model)
        services = Service.objects.filter(parent_object_type=ct, parent_object_id__in=ids).values('pk')
        addresses = IPAddress.objects.filter(**{ip_lookup: ids}).values('pk')
        terms += [
            Q(target_type=ct, target_id__in=ids),
            Q(target_type=service_ct, target_id__in=services),
            Q(target_type=ip_ct, target_id__in=addresses),
        ]
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
