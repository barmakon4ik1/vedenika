from rest_framework import serializers
from django.utils import translation
from django.conf import settings

from .models import *


# =========================================================
# 🌍 UNIVERSAL TRANSLATION FIELD
# =========================================================

class TranslatedField(serializers.Field):
    """
    Универсальное поле для django-parler.
    Поддерживает:
    - ?lang=de
    - Accept-Language
    - fallback
    - all_langs режим
    """

    def __init__(self, field_name, **kwargs):
        self.field_name = field_name
        super().__init__(read_only=True, **kwargs)

    def to_representation(self, instance):
        request = self.context.get("request")

        lang = None
        if request:
            lang = request.GET.get("lang") or getattr(request, "LANGUAGE_CODE", None)

        if not lang:
            lang = translation.get_language()

        # 🔥 режим: вернуть все языки
        if request and request.GET.get("all_langs"):
            return {
                code: instance.safe_translation_getter(
                    self.field_name,
                    language_code=code,
                    any_language=True
                )
                for code, _ in settings.LANGUAGES
            }

        return instance.safe_translation_getter(
            self.field_name,
            language_code=lang,
            any_language=True
        )


# =========================================================
# 🧠 BASE TRANSLATABLE SERIALIZER
# =========================================================

class TranslatableModelSerializer(serializers.ModelSerializer):
    """
    Автоматически заменяет поля из Meta.translatable_fields
    на TranslatedField
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        translatable_fields = getattr(self.Meta, "translatable_fields", [])

        for field in translatable_fields:
            self.fields[field] = TranslatedField(field)


# =========================================================
# 🧬 BASE MODELS
# =========================================================

class BreedSerializer(TranslatableModelSerializer):
    class Meta:
        model = Breed
        fields = ["id", "ems_code", "name", "is_active"]
        translatable_fields = ["name"]


class CountrySerializer(TranslatableModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "iso_code", "phone_code", "name", "is_active"]
        translatable_fields = ["name"]


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id",
            "country",
            "region",
            "city",
            "street",
            "house_number",
            "apartment",
            "postal_code",
            "latitude",
            "longitude",
            "remark",
        ]


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["id", "first_name", "last_name", "email", "phone"]


class CatterySerializer(TranslatableModelSerializer):
    class Meta:
        model = Cattery
        fields = [
            "id",
            "name",
            "website",
            "email",
            "phone",
            "is_active",
        ]
        translatable_fields = ["name"]


# =========================================================
# 🎨 COLOR SYSTEM
# =========================================================

class ColorComponentSerializer(TranslatableModelSerializer):
    class Meta:
        model = ColorComponent
        fields = ["id", "code", "name", "type"]
        translatable_fields = ["name"]


class ColorSerializer(TranslatableModelSerializer):
    class Meta:
        model = Color
        fields = ["id", "ems_code", "name"]
        translatable_fields = ["name"]


class CatColorSerializer(serializers.ModelSerializer):
    components = ColorComponentSerializer(many=True, read_only=True)
    color = ColorSerializer(read_only=True)

    class Meta:
        model = CatColor
        fields = ["ems_code", "color", "components"]


# =========================================================
# 🏥 HEALTH
# =========================================================

class HealthRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthRecord
        fields = ["id", "record_type", "name", "date", "remark"]


# =========================================================
# 🏷 NAMES
# =========================================================

class CatNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatName
        fields = ["id", "name", "language_code", "is_official"]


# =========================================================
# 🐾 LITTER
# =========================================================

class LitterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Litter
        fields = ["id", "litter_code", "birth_date", "kittens_count"]


# =========================================================
# 🐱 CAT
# =========================================================

class CatListSerializer(serializers.ModelSerializer):
    breed = BreedSerializer(read_only=True)
    cattery = CatterySerializer(read_only=True)

    class Meta:
        model = Cat
        fields = [
            "id",
            "registered_name",
            "sex",
            "birth_date",
            "breed",
            "cattery",
            "is_active",
        ]


class CatDetailSerializer(serializers.ModelSerializer):
    breed = BreedSerializer(read_only=True)
    cattery = CatterySerializer(read_only=True)
    owner = PersonSerializer(read_only=True)

    father = serializers.StringRelatedField()
    mother = serializers.StringRelatedField()

    color_info = CatColorSerializer(source="cat_color", read_only=True)

    health_records = HealthRecordSerializer(many=True, read_only=True)
    names = CatNameSerializer(many=True, read_only=True)

    class Meta:
        model = Cat
        fields = [
            "id",
            "registered_name",
            "call_name",
            "sex",
            "birth_date",
            "death_date",
            "breed",
            "cattery",
            "owner",
            "father",
            "mother",
            "color_info",
            "health_records",
            "names",
            "is_active",
            "is_for_breeding",
            "remark",
        ]


# =========================================================
# 📄 CMS
# =========================================================

class ContentBlockSerializer(TranslatableModelSerializer):
    class Meta:
        model = ContentBlock
        fields = ["block_type", "title", "text", "image", "order"]
        translatable_fields = ["title", "text"]


class PageSerializer(serializers.ModelSerializer):
    blocks = ContentBlockSerializer(many=True, read_only=True)

    class Meta:
        model = Page
        fields = ["slug", "name", "blocks"]