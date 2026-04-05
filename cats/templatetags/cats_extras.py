# cats/templatetags/cats_extras.py
#
# Подключение в шаблоне: {% load cats_extras %}
# Использование: {{ my_dict|get_item:key }}

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Позволяет делать dictionary[key] в шаблоне Django."""
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def trans_title(obj):
    """
    Возвращает переведённое поле 'title' объекта parler.
    Использование: {{ album|trans_title }}
    """
    if obj is None:
        return ""
    return obj.safe_translation_getter("title", any_language=True) or ""


@register.filter
def trans_description(obj):
    """
    Возвращает переведённое поле 'description' объекта parler.
    Использование: {{ album|trans_description }}
    """
    if obj is None:
        return ""
    return obj.safe_translation_getter("description", any_language=True) or ""


@register.filter
def trans_field(obj, field_name):
    """
    Универсальный фильтр для любого поля перевода parler.
    Использование: {{ album|trans_field:"title" }}
    """
    if obj is None:
        return ""
    return obj.safe_translation_getter(field_name, any_language=True) or ""
