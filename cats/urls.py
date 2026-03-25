from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()

# --- CAT ---
router.register(r'cats', CatViewSet)

# --- CORE ---
router.register(r'breeds', BreedViewSet)
router.register(r'catteries', CatteryViewSet)
router.register(r'persons', PersonViewSet)

# --- COLOR ---
router.register(r'colors', ColorViewSet)
router.register(r'color-components', ColorComponentViewSet)

# --- LOCATION ---
router.register(r'countries', CountryViewSet)
router.register(r'addresses', AddressViewSet)

# --- LITTER ---
router.register(r'litters', LitterViewSet)

# --- CMS ---
router.register(r'pages', PageViewSet)

app_name = 'cats'

urlpatterns = [
    path('api/v1/', include(router.urls)),
]