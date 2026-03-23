from django.core.exceptions import ValidationError

EMS_ORDER = [
    "BASE",
    "SILVER",
    "MOD",
    "WHITE",
    "TABBY",
    "POINT",
    "TAIL",
    "EYE",
    "EAR",
    "COAT",
]

def validate_components(components):
    """
    Проверяет, что компоненты соответствуют правилам EMS-кода
    1. Белый (w) не может сочетаться с другими компонентами
    2. Должен быть ровно один базовый цвет (BASE)
    3. Silver (s) и Gold (y) не могут сочетаться
    4. Не может быть двух компонентов одного типа
    """

    components = list(components)

    # Белый — только один
    if any(c.code == "w" for c in components):
        if len(components) > 1:
            raise ValidationError(
                "White color cannot have additional modifiers"
            )

    # Один базовый цвет
    bases = [c for c in components if c.type.code == "BASE"]
    print("DEBUG:", [(c.code, c.type.code) for c in components])

    if len(bases) != 1:
        raise ValidationError(
            "Exactly one base color must be selected"
        )

    # Silver vs Gold
    has_silver = any(c.code == "s" for c in components)
    has_gold = any(c.code == "y" for c in components)

    if has_silver and has_gold:
        raise ValidationError(
            "Silver and Gold cannot coexist"
        )

    # Дубликаты типов
    seen = set()

    for c in components:
        if c.type.code in seen:
            raise ValidationError(
                f"Multiple components of type {c.type.code} not allowed"
            )
        seen.add(c.type.code)


def build_ems_code(components):
    """
    Строит EMS-код из набора компонентов,
    сортируя их по типу в соответствии с EMS_ORDER
    и объединяя компоненты одного типа в одну строку
    """

    components = list(components)

    grouped = {}

    for c in components:
        grouped.setdefault(c.type.code, []).append(c.code)

    parts = []

    for t in EMS_ORDER:
        if t in grouped:
            parts.append("".join(sorted(grouped[t])))

    return " ".join(parts)


def allowed_components(selected, queryset):
    """
    Возвращает queryset компонентов, которые можно добавить к уже выбранным
    """
    selected_ids = list(selected.values_list("id", flat=True))

    # Белый блокирует всё
    if any(c.code == "w" for c in selected):
        return queryset.filter(code="w") | queryset.filter(id__in=selected_ids)

    # Только один BASE
    if any(c.type.code == "BASE" for c in selected):
        queryset = queryset.exclude(type__code="BASE")

    # Silver vs Gold
    if any(c.code == "s" for c in selected):
        queryset = queryset.exclude(code="y")

    if any(c.code == "y" for c in selected):
        queryset = queryset.exclude(code="s")

    # 🔥 КРИТИЧНО: вернуть выбранные
    return queryset | queryset.filter(id__in=selected_ids)