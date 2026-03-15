from django.contrib import admin
from parler.admin import TranslatableAdmin
from .models import ColorComponentType, ColorComponent, CatColor, Color, Breed, Cat


@admin.register(Breed)
class BreedAdmin(TranslatableAdmin):
    list_display = ("name", "ems_code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("translations__name", "ems_code")

@admin.register(Color)
class ColorAdmin(TranslatableAdmin):
    list_display = ("name", "ems_code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("translations__name", "ems_code")

@admin.register(ColorComponentType)
class ColorComponentTypeAdmin(TranslatableAdmin):
    list_display = ("name", "code", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("translations__name", "code")

@admin.register(ColorComponent)
class ColorComponentAdmin(TranslatableAdmin):
    list_display = ("name", "code", "type", "order", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("translations__name", "code")

@admin.register(CatColor)
class CatColorAdmin(admin.ModelAdmin):
    list_display = ("cat", "ems_code", "color")
    search_fields = ("cat__registered_name", "ems_code")
    filter_horizontal = ("components",)  # удобно выбирать несколько компонентов


class CatColorInline(admin.StackedInline):
    model = CatColor
    extra = 0
    filter_horizontal = ("components",)


@admin.register(Cat)
class CatAdmin(admin.ModelAdmin):
    list_display = ("registered_name",)
    inlines = [CatColorInline]
