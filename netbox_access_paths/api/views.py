from netbox.api.viewsets import NetBoxModelViewSet
from utilities.query import count_related

from .. import filtersets
from ..models import AccessHop, AccessPath, AccessRoute
from .serializers import AccessHopSerializer, AccessPathSerializer, AccessRouteSerializer

HOP_RELATED = ('hops__device', 'hops__virtual_machine', 'hops__tunnel')


class AccessRouteViewSet(NetBoxModelViewSet):
    queryset = AccessRoute.objects.annotate(path_count=count_related(AccessPath, 'route')) \
        .select_related('tenant').prefetch_related('origin_prefixes', 'tags', *HOP_RELATED)
    serializer_class = AccessRouteSerializer
    filterset_class = filtersets.AccessRouteFilterSet


class AccessPathViewSet(NetBoxModelViewSet):
    queryset = AccessPath.objects.select_related('tenant', 'route', 'approved_by', 'target_type').prefetch_related(
        'target', 'holders', 'holder_groups', 'tags', *HOP_RELATED, *(f'route__{h}' for h in HOP_RELATED),
    )
    serializer_class = AccessPathSerializer
    filterset_class = filtersets.AccessPathFilterSet


class AccessHopViewSet(NetBoxModelViewSet):
    queryset = AccessHop.objects.select_related('route', 'path', 'device', 'virtual_machine', 'tunnel') \
        .prefetch_related('tags')
    serializer_class = AccessHopSerializer
    filterset_class = filtersets.AccessHopFilterSet
