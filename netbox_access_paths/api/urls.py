from netbox.api.routers import NetBoxRouter

from . import views

router = NetBoxRouter()
router.register('routes', views.AccessRouteViewSet)
router.register('paths', views.AccessPathViewSet)
router.register('hops', views.AccessHopViewSet)

urlpatterns = router.urls
