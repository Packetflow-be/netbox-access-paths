from netbox.search import SearchIndex

from .models import AccessHop, AccessPath, AccessRoute


class AccessRouteIndex(SearchIndex):
    model = AccessRoute
    fields = (
        ('name', 100),
        ('description', 500),
        ('comments', 5000),
    )
    display_attrs = ('origin', 'tenant', 'description')


class AccessPathIndex(SearchIndex):
    model = AccessPath
    fields = (
        ('name', 100),
        ('target_url', 300),
        ('credential_ref', 300),
        ('description', 500),
        ('comments', 5000),
    )
    display_attrs = ('tenant', 'route', 'method', 'authentication', 'status', 'description')


class AccessHopIndex(SearchIndex):
    model = AccessHop
    fields = (
        ('label', 100),
        ('description', 500),
        ('comments', 5000),
    )
    display_attrs = ('route', 'path', 'position', 'description')


indexes = (AccessRouteIndex, AccessPathIndex, AccessHopIndex)
