import strawberry
import strawberry_django

from .types import AccessHopType, AccessPathType, AccessRouteType


@strawberry.type(name='Query')
class AccessPathsQuery:
    access_paths_route: AccessRouteType = strawberry_django.field()
    access_paths_route_list: list[AccessRouteType] = strawberry_django.field()

    access_paths_path: AccessPathType = strawberry_django.field()
    access_paths_path_list: list[AccessPathType] = strawberry_django.field()

    access_paths_hop: AccessHopType = strawberry_django.field()
    access_paths_hop_list: list[AccessHopType] = strawberry_django.field()


schema = [AccessPathsQuery]
