# cats/context_processors.py
#
# Передаёт данные владельца питомника во все шаблоны
# (нужно для футера с соцсетями)
#

from django.conf import settings


def cattery_owner(request):
    """
    Добавляет объект owner (Person) в контекст всех шаблонов.
    Используется в футере для отображения соцсетей.
    """
    owner_id = getattr(settings, 'CATTERY_OWNER_PERSON_ID', None)
    if not owner_id:
        return {'owner': None}

    # Ленивый импорт чтобы избежать circular import
    from cats.models import Person

    try:
        owner = Person.objects.select_related(
            'address', 'address__city', 'address__country'
        ).get(pk=owner_id)
    except Person.DoesNotExist:
        owner = None

    return {'owner': owner}


# ============================================================
# В settings.py добавить в TEMPLATES[0]['OPTIONS']['context_processors']:
# ============================================================
#
# TEMPLATES = [
#     {
#         ...
#         'OPTIONS': {
#             'context_processors': [
#                 'django.template.context_processors.debug',
#                 'django.template.context_processors.request',
#                 'django.contrib.auth.context_processors.auth',
#                 'django.contrib.messages.context_processors.messages',
#                 'cats.context_processors.cattery_owner',   # <-- добавить
#             ],
#         },
#     },
# ]
#
# И в settings.py добавить константу:
# CATTERY_OWNER_PERSON_ID = 1   # id владельца в таблице cats_person
