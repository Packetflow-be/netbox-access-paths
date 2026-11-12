import strawberry_django
from strawberry.scalars import ID
from strawberry_django import FilterLookup, StrFilterLookup

from netbox.graphql.filters import PrimaryModelFilter, register_filter
from tenancy.graphql.filter_mixins import TenancyFilterMixin

from .. import models

__all__ = ('AccessHopFilter', 'AccessPathFilter', 'AccessRouteFilter')


@register_filter(models.AccessRoute, lookups=True)
class AccessRouteFilter(TenancyFilterMixin, PrimaryModelFilter):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    origin: StrFilterLookup[str] | None = strawberry_django.filter_field()


@register_filter(models.AccessPath, lookups=True)
class AccessPathFilter(TenancyFilterMixin, PrimaryModelFilter):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    route_id: ID | None = strawberry_django.filter_field()
    target_id: ID | None = strawberry_django.filter_field()
    target_url: StrFilterLookup[str] | None = strawberry_django.filter_field()
    method: StrFilterLookup[str] | None = strawberry_django.filter_field()
    authentication: StrFilterLookup[str] | None = strawberry_django.filter_field()
    credential_ref: StrFilterLookup[str] | None = strawberry_django.filter_field()
    status: StrFilterLookup[str] | None = strawberry_django.filter_field()
    approved_by_id: ID | None = strawberry_django.filter_field()


@register_filter(models.AccessHop, lookups=True)
class AccessHopFilter(PrimaryModelFilter):
    route_id: ID | None = strawberry_django.filter_field()
    path_id: ID | None = strawberry_django.filter_field()
    position: FilterLookup[int] | None = strawberry_django.filter_field()
    device_id: ID | None = strawberry_django.filter_field()
    virtual_machine_id: ID | None = strawberry_django.filter_field()
    tunnel_id: ID | None = strawberry_django.filter_field()
    label: StrFilterLookup[str] | None = strawberry_django.filter_field()
