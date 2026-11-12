from django.urls import include, path

from utilities.urls import get_model_urls

from . import views

urlpatterns = [
    path('routes/', include(get_model_urls('netbox_access_paths', 'accessroute', detail=False))),
    path('routes/<int:pk>/', include(get_model_urls('netbox_access_paths', 'accessroute'))),
    path('paths/', include(get_model_urls('netbox_access_paths', 'accesspath', detail=False))),
    path('paths/<int:pk>/', include(get_model_urls('netbox_access_paths', 'accesspath'))),
    path('hops/', include(get_model_urls('netbox_access_paths', 'accesshop', detail=False))),
    path('hops/<int:pk>/', include(get_model_urls('netbox_access_paths', 'accesshop'))),
    path('review/', views.ReviewView.as_view(), name='review'),
    path('export/', views.ExportView.as_view(), name='export'),
]
