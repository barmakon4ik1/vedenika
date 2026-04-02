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
