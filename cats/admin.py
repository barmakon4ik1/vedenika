from django.contrib import admin
from django import forms
from parler.admin import TranslatableAdmin, TranslatableTabularInline

from .models import *


# =========================
# Общие helpers
# =========================

class TranslatableAdminMixin:
    def get_translated(self, obj, field):
        return obj.safe_translation_getter(field, any_language=True)


class ColorAdminForm(forms.ModelForm):
    class Meta:
        model = Color
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        components = cleaned_data.get("components")
        if components:
            validate_components(components)
        return cleaned_data


# =========================
# Breed
# =========================

@admin.register(Breed)
class BreedAdmin(TranslatableAdmin):
    list_display = ("id", "get_name", "ems_code", "is_active")
    search_fields = ("translations__name", "ems_code")
    list_filter = ("is_active",)
    ordering = ("ems_code",)

    def get_name(self, obj):
        return obj.safe_translation_getter("name", any_language=True)
    get_name.short_description = "Name"


# =========================
# Color components
# =========================

@admin.register(ColorComponentType)
class ColorComponentTypeAdmin(TranslatableAdmin):
    list_display = ("id", "get_name", "code", "order", "is_active")
    ordering = ("order", "code")

    def get_name(self, obj):
        return obj.safe_translation_getter("name", any_language=True)
    get_name.short_description = "Name"


@admin.register(ColorComponent)
class ColorComponentAdmin(TranslatableAdmin):
    list_display = ("id", "get_name", "code", "type", "order", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("translations__name", "code")
    ordering = ("type__order", "order", "code")
    list_select_related = ("type",)

    def get_name(self, obj):
        return obj.safe_translation_getter("name", any_language=True)
    get_name.short_description = "Name"


# =========================
# Inline для компонентов цвета
# =========================

class ColorComponentUsageForm(forms.ModelForm):
    class Meta:
        model = ColorComponentUsage
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk and self.instance.color:
            selected = self.instance.color.components.all()
            self.fields["component"].queryset = Color.allowed_components(selected)


class ColorComponentUsageInline(admin.TabularInline):
    model = ColorComponentUsage
    form = ColorComponentUsageForm
    extra = 1
    autocomplete_fields = ("component",)
    ordering = ("position",)


# =========================
# Color
# =========================

@admin.register(Color)
class ColorAdmin(TranslatableAdmin):
    form = ColorAdminForm

    list_display = ("id", "get_name", "ems_code", "is_active")
    search_fields = ("translations__name", "ems_code")
    list_filter = ("is_active",)
    ordering = ("ems_code",)
    readonly_fields = ("ems_code",)

    inlines = [ColorComponentUsageInline]

    def get_name(self, obj):
        return obj.safe_translation_getter("name", any_language=True)

    def save_model(self, request, obj, form, change):
        """
        Генерируем EMS код при сохранении Color
        """
        super().save_model(request, obj, form, change)

        # Берём компоненты из формы (если объект новый или редактируется)
        components = form.cleaned_data.get("components")
        if components:
            validate_components(components)
            new_code = build_ems_code(components)
            if obj.ems_code != new_code:
                # Обновляем поле в базе, не трогая остальное
                Color.objects.filter(pk=obj.pk).update(ems_code=new_code)

    def save_related(self, request, form, formsets, change):
        """
        Генерируем EMS код после сохранения inline (ColorComponentUsage)
        """
        super().save_related(request, form, formsets, change)

        obj = form.instance
        components = obj.components.select_related("type")
        if components.exists():
            validate_components(components)
            new_code = build_ems_code(components)
            if obj.ems_code != new_code:
                Color.objects.filter(pk=obj.pk).update(ems_code=new_code)


# =========================
# Geography
# =========================

@admin.register(Country)
class CountryAdmin(TranslatableAdmin):
    list_display = ("id", "get_name", "iso_code", "is_active")
    ordering = ("iso_code",)

    def get_name(self, obj):
        return obj.safe_translation_getter("name", any_language=True)
    get_name.short_description = "Name"


@admin.register(Region)
class RegionAdmin(TranslatableAdmin):
    list_display = ("id", "get_name", "country", "code", "is_active")
    list_filter = ("country",)
    list_select_related = ("country",)

    def get_name(self, obj):
        return obj.safe_translation_getter("name", any_language=True)
    get_name.short_description = "Name"


@admin.register(City)
class CityAdmin(TranslatableAdmin):
    list_display = ("id", "get_name", "country", "region")
    list_filter = ("country", "region")
    list_select_related = ("country", "region")

    def get_name(self, obj):
        return obj.safe_translation_getter("name", any_language=True)
    get_name.short_description = "Name"


# =========================
# Address / Person
# =========================

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("id", "city", "street", "house_number")
    list_select_related = ("city",)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "email")
    search_fields = ("first_name", "last_name", "email")


# =========================
# Cattery
# =========================

@admin.register(Cattery)
class CatteryAdmin(TranslatableAdmin):
    list_display = ("id", "get_name", "is_active")
    filter_horizontal = ("owners",)
    search_fields = ("translations__name", "prefix", "suffix")

    def get_name(self, obj):
        return obj.safe_translation_getter("name", any_language=True)


# =========================
# Organization
# =========================

@admin.register(Organization)
class OrganizationAdmin(TranslatableAdmin):
    list_display = ("id", "get_name", "code", "org_type", "is_active")
    list_filter = ("org_type", "is_active")

    def get_name(self, obj):
        return obj.safe_translation_getter("name", any_language=True)
    get_name.short_description = "Name"


# =========================
# Cats
# =========================

class CatColorInline(admin.StackedInline):
    model = CatColor
    extra = 0

@admin.register(Cat)
class CatAdmin(admin.ModelAdmin):
    inlines = [CatColorInline]
    list_display = ("id", "registered_name", "sex", "breed", "cattery", "litter")
    list_filter = ("sex", "breed", "cattery")
    search_fields = ("registered_name", "call_name")

    autocomplete_fields = ("breed", "cattery", "father", "mother", "owner")
    list_select_related = ("breed", "cattery", "litter")


@admin.register(Litter)
class LitterAdmin(admin.ModelAdmin):
    list_display = ("id", "litter_code", "birth_date", "cattery", "kittens_count")
    list_filter = ("cattery", "birth_date")
    autocomplete_fields = ("father", "mother", "cattery")


@admin.register(CatName)
class CatNameAdmin(admin.ModelAdmin):
    list_display = ("cat", "name", "language_code", "is_official")
    list_filter = ("language_code", "is_official")


# =========================
# Media
# =========================

@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "uploaded_at", "is_public")


@admin.register(MediaLink)
class MediaLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "file", "role")
    raw_id_fields = ("file",)


# =========================
# Membership / Health
# =========================

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("organization", "cattery", "person", "membership_type", "is_active")
    list_filter = ("organization", "membership_type")


@admin.register(HealthRecord)
class HealthRecordAdmin(admin.ModelAdmin):
    list_display = ("cat", "record_type", "name", "date")
    list_select_related = ("cat",)


# =========================
# Documents
# =========================

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "uploaded_at", "is_public")
    raw_id_fields = ("file",)


# =========================
# Titles
# =========================

@admin.register(Title)
class TitleAdmin(TranslatableAdmin):
    list_display = ("abbreviation", "get_full_name", "title_type", "is_active")

    def get_full_name(self, obj):
        return obj.safe_translation_getter("full_name", any_language=True)
    get_full_name.short_description = "Full name"


# =========================
# CatColor
# =========================


@admin.register(CatColor)
class CatColorAdmin(admin.ModelAdmin):
    list_display = ("cat", "ems_code", "color")
    filter_horizontal = ("components",)
    autocomplete_fields = ("cat", "color")
    list_select_related = ("cat", "color")
    search_fields = ("cat__registered_name", "ems_code")
    readonly_fields = ("ems_code", "color_name")

    def color_name(self, obj):
        if obj.color:
            return obj.color.safe_translation_getter("name", any_language=True)
        return "-"

    color_name.short_description = "Color name"

    def save_model(self, request, obj, form, change):
        """
        Генерируем EMS код при сохранении CatColor
        """
        super().save_model(request, obj, form, change)

        if obj.color:
            # Если задан справочный цвет, берём его EMS
            new_code = obj.color.ems_code
        else:
            components = form.cleaned_data.get("components")
            if components:
                validate_components(components)
                new_code = build_ems_code(components)
            else:
                new_code = ""

        if obj.ems_code != new_code:
            CatColor.objects.filter(pk=obj.pk).update(ems_code=new_code)

    def save_related(self, request, form, formsets, change):
        """
        Генерируем EMS код после сохранения компонентов через inline
        """
        super().save_related(request, form, formsets, change)

        obj = form.instance
        if obj.color:
            new_code = obj.color.ems_code
        else:
            components = obj.components.select_related("type")
            if components.exists():
                validate_components(components)
                new_code = build_ems_code(components)
            else:
                new_code = ""

        if obj.ems_code != new_code:
            CatColor.objects.filter(pk=obj.pk).update(ems_code=new_code)

"""
Пояснения
    1. TranslatableTabularInline
        Позволяет редактировать блоки прямо внутри страницы.
        Каждая строка — один блок (заголовок, параграф, изображение, список).
    2. sortable_field_name = "order"
        Можно менять порядок блоков через drag-and-drop в админке.
    3. TranslatableAdmin / TranslatableTabularInline
        Автоматически добавляет поля для всех языков, если включена мультиязычность через TranslatableModel.
    4. prepopulated_fields
        Слаг генерируется автоматически из названия страницы.
"""
# Inline для блоков контента на странице
class ContentBlockInline(TranslatableTabularInline):
    model = ContentBlock
    extra = 1  # по умолчанию добавляется один пустой блок
    fields = ('order', 'block_type', 'title', 'text', 'image')
    sortable_field_name = "order"  # позволяет перетаскивать порядок блоков
    show_change_link = True

# Админка для страниц
@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at', 'updated_at')
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ContentBlockInline]

