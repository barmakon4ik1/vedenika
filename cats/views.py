from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from .models import *
from .serializers import *

from django.utils import translation


class TranslatableModelSerializer(serializers.ModelSerializer):

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        translatable_fields = getattr(self.Meta, "translatable_fields", [])

        request = self.context.get("request")

        # 👇 берём язык из ?lang= или fallback
        lang = None
        if request:
            lang = request.GET.get("lang") or getattr(request, "LANGUAGE_CODE", None)

        if not lang:
            lang = translation.get_language()

        for field in translatable_fields:
            representation[field] = instance.safe_translation_getter(
                field,
                language_code=lang,   # 🔥 КЛЮЧЕВОЕ
                any_language=True
            )

        return representation


class BaseViewSet(viewsets.ModelViewSet):

    def get_language(self):
        request = self.request
        return request.GET.get("lang") or request.headers.get("Accept-Language")

    def get_queryset(self):
        lang = self.request.GET.get("lang")
        if lang:
            translation.activate(lang)

        return super().get_queryset()


# --- CAT ---

class CatViewSet(BaseViewSet):
    queryset = Cat.objects.select_related(
        "breed", "cattery", "father", "mother", "owner"
    ).prefetch_related(
        "names",
        "health_records",
        "cat_color__components",
    )

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = [
        "sex",
        "breed",
        "cattery",
        "is_active",
        "is_for_breeding",
    ]

    search_fields = [
        "registered_name",
        "call_name",
        "pedigree_number",
    ]

    ordering_fields = ["registered_name", "birth_date"]
    ordering = ["registered_name"]

    def get_serializer_class(self):
        if self.action == "list":
            return CatListSerializer
        return CatDetailSerializer

    # --- КАСТОМНЫЕ ENDPOINTS ---

    @action(detail=True)
    def pedigree(self, request, pk=None):
        cat = self.get_object()

        data = {
            "cat": cat.registered_name,
            "father": str(cat.father) if cat.father else None,
            "mother": str(cat.mother) if cat.mother else None,
        }

        return Response(data)

    @action(detail=True)
    def offspring(self, request, pk=None):
        cat = self.get_object()

        kittens = Cat.objects.filter(
            models.Q(father=cat) | models.Q(mother=cat)
        )

        serializer = CatListSerializer(kittens, many=True)
        return Response(serializer.data)


# --- COLOR ---

class ColorViewSet(BaseViewSet):
    queryset = Color.objects.all()
    serializer_class = ColorSerializer


class ColorComponentViewSet(BaseViewSet):
    queryset = ColorComponent.objects.all()
    serializer_class = ColorComponentSerializer


# --- BREED ---

class BreedViewSet(BaseViewSet):
    queryset = Breed.objects.all()
    serializer_class = BreedSerializer


# --- Cattery ---

class CatteryViewSet(viewsets.ModelViewSet):
    queryset = Cattery.objects.all()
    serializer_class = CatterySerializer


# --- PERSON ---

class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer


# --- ADDRESS ---

class AddressViewSet(BaseViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer


class CountryViewSet(BaseViewSet):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer


# --- LITTER ---

class LitterViewSet(viewsets.ModelViewSet):
    queryset = Litter.objects.all()
    serializer_class = LitterSerializer

    @action(detail=True)
    def kittens(self, request, pk=None):
        litter = self.get_object()
        serializer = CatListSerializer(litter.kittens.all(), many=True)
        return Response(serializer.data)


# --- CMS ---

class PageViewSet(BaseViewSet):
    queryset = Page.objects.prefetch_related("blocks")
    serializer_class = PageSerializer
    lookup_field = "slug"