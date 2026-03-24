# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'cats', CatViewSet)
router.register(r'pages', PageViewSet)
router.register(r'address', AddressViewSet)
router.register(r'country', CountryViewSet)

app_name = 'cats'

urlpatterns = [
    path('api/', include(router.urls)),
    # path('', views.cat_list, name='cat_list'),
    # path('<int:pk>/', views.cat_detail, name='cat_detail'),
]