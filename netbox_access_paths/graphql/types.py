from typing import TYPE_CHECKING, Annotated

import strawberry
import strawberry_django

from dcim.models import Device
from ipam.models import IPAddress, Service
from netbox.graphql.optimization import build_gfk_prefetch
from netbox.graphql.types import PrimaryObjectType, register_type
from virtualization.models import VirtualMachine

from .. import models
from .filters import AccessHopFilter, AccessPathFilter, AccessRouteFilter

if TYPE_CHECKING:
    from dcim.graphql.types import DeviceType
    from ipam.graphql.types import IPAddressType, PrefixType, ServiceType
    from tenancy.graphql.types import ContactGroupType, ContactType, TenantType
    from virtualization.graphql.types import VirtualMachineType
    from vpn.graphql.types import TunnelType

__all__ = ('AccessHopType', 'AccessPathType', 'AccessRouteType')


@register_type(models.AccessRoute, fields='__all__', filters=AccessRouteFilter, pagination=True)
class AccessRouteType(PrimaryObjectType):
    origin_prefixes: list[Annotated['PrefixType', strawberry.lazy('ipam.graphql.types')]]
    tenant: Annotated['TenantType', strawberry.lazy('tenancy.graphql.types')] | None
    hops: list[Annotated['AccessHopType', strawberry.lazy('netbox_access_paths.graphql.types')]]
    paths: list[Annotated['AccessPathType', strawberry.lazy('netbox_access_paths.graphql.types')]]


@register_type(models.AccessPath, exclude=['target_type', 'target_id'], filters=AccessPathFilter, pagination=True)
class AccessPathType(PrimaryObjectType):
    tenant: Annotated['TenantType', strawberry.lazy('tenancy.graphql.types')]
    route: Annotated['AccessRouteType', strawberry.lazy('netbox_access_paths.graphql.types')]
    holders: list[Annotated['ContactType', strawberry.lazy('tenancy.graphql.types')]]
    holder_groups: list[Annotated['ContactGroupType', strawberry.lazy('tenancy.graphql.types')]]
    approved_by: Annotated['ContactType', strawberry.lazy('tenancy.graphql.types')] | None
    hops: list[Annotated['AccessHopType', strawberry.lazy('netbox_access_paths.graphql.types')]]

    @strawberry_django.field(
        prefetch_related=build_gfk_prefetch('target', [Device, VirtualMachine, Service, IPAddress]),
        only=['target_type', 'target_id'],
    )
    def target(self) -> Annotated[
        Annotated['DeviceType', strawberry.lazy('dcim.graphql.types')]
        | Annotated['VirtualMachineType', strawberry.lazy('virtualization.graphql.types')]
        | Annotated['ServiceType', strawberry.lazy('ipam.graphql.types')]
        | Annotated['IPAddressType', strawberry.lazy('ipam.graphql.types')],
        strawberry.union('AccessPathTargetType'),
    ] | None:
        return self.target


@register_type(models.AccessHop, fields='__all__', filters=AccessHopFilter, pagination=True)
class AccessHopType(PrimaryObjectType):
    route: Annotated['AccessRouteType', strawberry.lazy('netbox_access_paths.graphql.types')] | None
    path: Annotated['AccessPathType', strawberry.lazy('netbox_access_paths.graphql.types')] | None
    device: Annotated['DeviceType', strawberry.lazy('dcim.graphql.types')] | None
    virtual_machine: Annotated['VirtualMachineType', strawberry.lazy('virtualization.graphql.types')] | None
    tunnel: Annotated['TunnelType', strawberry.lazy('vpn.graphql.types')] | None
