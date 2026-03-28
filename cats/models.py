from typing import TYPE_CHECKING
from parler.models import TranslatableModel, TranslatedFields
from .ems import build_ems_code, validate_components
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

if TYPE_CHECKING:
    from typing import TYPE_CHECKING

# TranslatableModel- Обязателен для parler.


class Breed(TranslatableModel):
    """
    Cat breed (e.g., Maine Coon). Модель породы
    """

    # TranslatedFields- Содержит все поля, которые нужно перевести.
    # В нашем случае это только name, но в будущем может быть больше.
    translations = TranslatedFields(
        name=models.CharField(
            max_length=200,
            verbose_name="Breed name"
        )
    )

    ems_code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="EMS code",
        help_text="FIFe EMS breed code (e.g., MCO)"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Active"
    )    # Позволяет: скрывать устаревшие записи, не удалять данные, сохранять ссылки в Cat

    class Meta:
        verbose_name = "Breed"
        verbose_name_plural = "Breeds"
        ordering = ["ems_code"]

    # safe_translation_getter - Позволяет:
    # не падать, если перевода нет
    # брать любой доступный язык
    # Очень важно для админки и API.
    def __str__(self):
        return f"{self.safe_translation_getter('name', any_language=True)} ({self.ems_code})"


class ColorComponentUsage(models.Model):
    """
    Модель для хранения связи между цветом и его компонентами. Позволяет:
-   Указывать несколько компонентов для одного цвета (например, основа + узор + интенсивность)
-   Хранить позицию компонента в формуле EMS для правильного формирования кода цвета
-   Связывать с общей моделью Color и ColorComponent для удобства фильтрации и статистики
    """
    color = models.ForeignKey(
        "Color",
        on_delete=models.CASCADE,
        related_name="component_usages"
    )

    component = models.ForeignKey(
        "ColorComponent",
        on_delete=models.PROTECT
    )

    position = models.PositiveIntegerField(
        help_text="Position in EMS formula"
    )

    class Meta:
        ordering = ["position"]
        unique_together = ("color", "component")


class Color(TranslatableModel):
    """
    Cat color according to EMS (FIFe) classification.
    Example: ns 22 — black silver blotched tabby
    """

    translations = TranslatedFields(
        name=models.CharField(
            max_length=200,
            verbose_name="Color name"
        )
    )

    components = models.ManyToManyField(
        "ColorComponent",
        through="ColorComponentUsage",
        related_name="colors"
    )

    ems_code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="EMS color code",
        help_text="EMS color code (e.g., ns 22)"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Active"
    )

    remark = models.TextField(
        blank=True,
        verbose_name="Remark (for internal use)"
    )  # Позволяет хранить дополнительную информацию, которая может быть полезна
    # для администраторов, но не обязательно для отображения пользователям
    # (например, примечания по классификации, ссылки на источники информации и т.д.)


    class Meta:
        verbose_name = "Color"
        verbose_name_plural = "Colors"
        ordering = ["ems_code"]

    def __str__(self):
        name = self.safe_translation_getter("name", any_language=True)
        return f"{name} ({self.ems_code})"

    def save(self, *args, **kwargs):
        # Получаем компоненты через M2M (если объект уже существует)
        if self.pk:
            components = self.components.select_related("type")
            if components.exists():
                validate_components(components)
                self.ems_code = build_ems_code(components)
        super().save(*args, **kwargs)

    @staticmethod
    def allowed_components(selected):
        """
        Возвращает QuerySet компонентов, которые можно выбрать к уже выбранным.
        С учётом правил EMS (BASE/SILVER/GOLD/WHITE)
        """
        qs = ColorComponent.objects.all()
        selected_ids = [c.id for c in selected]

        # Белый блокирует всё
        if any(c.code == "w" for c in selected):
            return qs.filter(code="w") | ColorComponent.objects.filter(id__in=selected_ids)

        # Только один BASE
        if any(c.type.code == "BASE" for c in selected):
            qs = qs.exclude(type__code="BASE")

        # Silver vs Gold
        if any(c.code == "s" for c in selected):
            qs = qs.exclude(code="y")
        if any(c.code == "y" for c in selected):
            qs = qs.exclude(code="s")

        # вернуть выбранные обратно
        return qs | ColorComponent.objects.filter(id__in=selected_ids)


class ColorComponentType(TranslatableModel):
    """
    Модель компонента цвета. Например, "основа", "узор", "интенсивность" и т.д.
    """
    translations = TranslatedFields(
        name=models.CharField(max_length=100, verbose_name="Component type")
    )

    code = models.CharField(max_length=20, unique=True, verbose_name="Code")

    order = models.PositiveSmallIntegerField(default=0, verbose_name="Order in EMS formula")

    is_active = models.BooleanField(default=True, verbose_name="Active")

    remark = models.TextField(blank=True, verbose_name="Remark (for internal use)")

    class Meta:
        verbose_name = "Color Component Type"
        verbose_name_plural = "Color Component Types"
        ordering = ["order", "code"]

    def __str__(self):
        return f"{self.safe_translation_getter('name', any_language=True)} ({self.code})"


class ColorComponent(TranslatableModel):
    """
    Модель конкретного компонента цвета. Например, для типа "узор"
    это может быть "tabby", "spotted", "ticked" и т.д.
    """
    translations = TranslatedFields(
        name=models.CharField(max_length=100, verbose_name="Component name")
    )

    type = models.ForeignKey(ColorComponentType, on_delete=models.PROTECT, related_name="components")

    code = models.CharField(max_length=10, verbose_name="EMS code")

    order = models.PositiveSmallIntegerField(default=0, verbose_name="Order in EMS formula")

    is_active = models.BooleanField(default=True, verbose_name="Active")

    remark = models.TextField(blank=True, verbose_name="Remark (for internal use)")

    class Meta:
        verbose_name = "Color Component"
        verbose_name_plural = "Color Components"
        ordering = ["type__order", "order", "code"]
        unique_together = ("type", "code")

    def __str__(self):
        return f"{self.safe_translation_getter('name', any_language=True)} ({self.code})"


class CatColor(models.Model):
    """
    Модель, связывающая кота с его цветом. Позволяет:
-   Указывать несколько компонентов цвета для одного кота (например, основа + узор + интенсивность)
-   Хранить готовый EMS код цвета для быстрого доступа
-   Связывать с общей моделью Color, если она есть (для удобства фильтрации и статистики)
    """
    cat = models.OneToOneField("cats.Cat", on_delete=models.CASCADE, related_name="cat_color")
    components = models.ManyToManyField(ColorComponent, related_name="cat_colors")

    ems_code = models.CharField(max_length=50, verbose_name="EMS code")

    color = models.ForeignKey("Color", null=True, blank=True, on_delete=models.SET_NULL, related_name="cat_colors")

    class Meta:
        verbose_name = "Cat Color"
        verbose_name_plural = "Cat Colors"

    def __str__(self):
        return f"{self.cat.registered_name} — {self.ems_code}"

    def save(self, *args, **kwargs):
        """
        При сохранении автоматически формируем EMS код цвета
        на основе выбранных компонентов или справочного цвета.
        """

        # 1. Если задан справочный цвет — используем его
        if self.color:
            self.ems_code = self.color.ems_code

        # 2. Иначе строим из компонентов
        else:
            components = list(self.components.select_related("type"))

            if components:
                validate_components(components)
                self.ems_code = build_ems_code(components)
            else:
                self.ems_code = ""

        super().save(*args, **kwargs)


class Country(TranslatableModel):
    """
    Модель страны происхождения кота. Позволяет:
    -   Хранить название страны на нескольких языках
    -   Указывать ISO код страны для стандартизации
    -   Хранить телефонный код страны (может быть полезно для контактов
    заводчиков)
    -   Активность страны (можно скрывать устаревшие или неактивные страны)
    """

    translations = TranslatedFields(
        name=models.CharField(max_length=200)
    )

    iso_code = models.CharField(
        max_length=2,
        unique=True,
        help_text="ISO 3166-1 alpha-2"
    )

    phone_code = models.CharField(
        max_length=10,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["iso_code"]

    def __str__(self):
        return self.safe_translation_getter("name", any_language=True)


class Region(TranslatableModel):
    """Модель региона внутри страны. Позволяет:
    -   Хранить название региона на нескольких языках
    -   Указывать код региона (например, для России это может быть код субъекта федерации)
    -   Связывать регион с конкретной страной, чтобы обеспечить целостность данных
    -   Активность региона (можно скрывать устаревшие или неактивные регионы)
    """

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="regions"
    )

    translations = TranslatedFields(
        name=models.CharField(max_length=200)
    )

    code = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("country", "code")
        ordering = ["country", "code"]

    def __str__(self):
        return self.safe_translation_getter("name", any_language=True)


class City(TranslatableModel):
    """
    Модель города. Позволяет:
    -   Хранить название города на нескольких языках
    -   Указывать код города (например, для России это может быть код ОКТМО)
    -   Связывать город с конкретной страной и регионом, чтобы обеспечить цельность данных
    -   Активность города (можно скрывать устаревшие или неактивные города)
    """

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="cities"
    )

    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cities"
    )

    translations = TranslatedFields(
        name=models.CharField(max_length=200)
    )

    postal_code = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["country", "region", "translations__name"]

    def __str__(self):
        return self.safe_translation_getter("name", any_language=True)


class Address(models.Model):
    """
    Модель адреса. Позволяет:
    -   Хранить адрес кота (например, адрес заводчика или место проживания)
    -   Связывать адрес с конкретной страной, регионом и городом для обеспечения целостности данных
    -   Указывать улицу, номер дома, квартиру и почтовый индекс для более
    точного описания местоположения
    -   Хранить географические координаты (широта и долгота) для
    интеграции с картами и геолокационными сервисами
    -   Добавлять примечания к адресу для дополнительной информации (например, ""ряд"
    или "напротив парка")
    """

    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT
    )

    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT
    )

    street = models.CharField(max_length=255)

    house_number = models.CharField(max_length=20, blank=True)
    apartment = models.CharField(max_length=20, blank=True)

    postal_code = models.CharField(max_length=20, blank=True)

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    remark = models.TextField(blank=True)

    def __str__(self):
        return f"{self.street} {self.house_number}, {self.city}"


class Cattery(TranslatableModel):
    """
    Модель питомника. Позволяет:

    - Хранить название питомника на нескольких языках
    - Указывать адрес питомника (необязательно, может быть скрыт)
    - Хранить контактную информацию
    - Хранить регистрационные данные питомника
    - Связывать питомник с владельцами
    - Отмечать активность питомника
    - Добавлять служебные примечания
    """

    translations = TranslatedFields(
        name=models.CharField(
            max_length=200,
            verbose_name="Название питомника"
        )
    )

    # ===== Регистрационные данные =====

    registration_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Регистрационный номер"
    )

    prefix = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Зарегистрированный префикс"
    )

    suffix = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Зарегистрированный суффикс"
    )

    founded_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Год основания"
    )

    # ===== Владельцы =====

    owners = models.ManyToManyField(
        "Person",
        related_name="catteries",
        blank=True,
        verbose_name="Владельцы"
    )

    # ===== Адрес =====

    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="catteries",
        verbose_name="Адрес"
    )

    # ===== Контакты =====

    website = models.URLField(
        blank=True,
        verbose_name="Веб-сайт"
    )

    email = models.EmailField(
        blank=True,
        verbose_name="Email"
    )

    phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Телефон"
    )

    # ===== Статус =====

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )

    # ===== Служебная информация =====

    remark = models.TextField(
        blank=True,
        verbose_name="Примечание"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата изменения"
    )

    class Meta:
        verbose_name = "Питомник"
        verbose_name_plural = "Питомники"
        ordering = ["translations__name"]

    def __str__(self):
        return self.safe_translation_getter(
            "name",
            any_language=True
        )


class Person(models.Model):
    """
    Человек (владелец, заводчик и т.д.)
    """

    user = models.OneToOneField(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="person_profile"
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    address = models.ForeignKey(
        "Address",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class MediaFile(models.Model):
    """
    Модель для хранения медиафайлов.

    - файл
    - владелец (кто загрузил)
    - тип файла
    - публичность
    """

    class MediaType(models.TextChoices):
        PHOTO = "PHOTO", "Фото"
        DOCUMENT = "DOCUMENT", "Документ"
        OTHER = "OTHER", "Другое"

    file = models.FileField(upload_to="media/")

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="media_files"
    )

    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    media_type = models.CharField(
        max_length=20,
        choices=MediaType.choices,
        default=MediaType.PHOTO
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or str(self.file)


class MediaLink(models.Model):
    """Модель для связывания медиафайлов с различными объектами (например, котами,
    питомниками, странами и т.д.) с помощью GenericForeignKey.
    Позволяет:
    -   Связывать медиафайлы с любыми моделями без необходимости создавать отдельные
    поля для каждой модели
    -   Указывать роль файла (например, "фото", родословная","
    "контракт" и т.д.) для более точного описания его назначения
    """

    file = models.ForeignKey(
        MediaFile,
        on_delete=models.CASCADE
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )

    object_id = models.PositiveIntegerField()

    content_object = GenericForeignKey(
        "content_type",
        "object_id"
    )

    role = models.CharField(
        max_length=50,
        blank=True,
        help_text="photo, pedigree, contract, etc."
    )


class Organization(TranslatableModel):
    """
    Модель фелинологической организации (система, федерация, клуб).

    Позволяет:

    - Хранить название организации на нескольких языках
    - Указывать аббревиатуру (например, FIFe, WCF, TICA)
    - Строить иерархию организаций (международная → национальная → клуб)
    - Хранить контактную информацию
    - Указывать адрес организации
    - Отмечать активность организации
    - Добавлять служебные примечания
    """

    translations = TranslatedFields(
        name=models.CharField(
            max_length=200,
            verbose_name="Название организации"
        )
    )

    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Код / аббревиатура"
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suborganizations",
        verbose_name="Родительская организация"
    )

    address = models.ForeignKey(
        "Address",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations",
        verbose_name="Адрес"
    )

    website = models.URLField(
        blank=True,
        verbose_name="Веб-сайт"
    )

    email = models.EmailField(
        blank=True,
        verbose_name="Email"
    )

    phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Телефон"
    )

    class OrganizationType(models.TextChoices):
        SYSTEM = "SYSTEM", "Международная система"
        FEDERATION = "FEDERATION", "Федерация"
        CLUB = "CLUB", "Клуб"
        OTHER = "OTHER", "Другое"

    org_type = models.CharField(
        max_length=20,
        choices=OrganizationType.choices,
        default=OrganizationType.CLUB,
        verbose_name="Тип организации"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна"
    )

    remark = models.TextField(
        blank=True,
        verbose_name="Примечание"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата изменения"
    )

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        ordering = ["code"]

    def __str__(self):
        name = self.safe_translation_getter(
            "name",
            any_language=True
        )
        return f"{name} ({self.code})"


class Membership(models.Model):
    """
    Членство в организации
    """

    organization = models.ForeignKey(
        "Organization",
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    cattery = models.ForeignKey(
        "Cattery",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships"
    )

    person = models.ForeignKey(
        "Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships"
    )

    class MembershipType(models.TextChoices):
        BREEDER = "BREEDER", "Заводчик"
        ASSISTANT = "ASSISTANT", "Помощник"
        JUDGE = "JUDGE", "Судья"
        OTHER = "OTHER", "Другое"

    membership_type = models.CharField(
        max_length=20,
        choices=MembershipType.choices,
        default=MembershipType.BREEDER
    )

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    remark = models.TextField(blank=True)

    class Meta:
        ordering = ["organization", "cattery", "person"]
        constraints = [
            models.CheckConstraint(
                condition=(
                        Q(person__isnull=False, cattery__isnull=True) |
                        Q(person__isnull=True, cattery__isnull=False)
                ),
                name="membership_target_check"
            )
        ]

    def __str__(self):
        target = self.cattery or self.person or "Не указан"
        return f"{target} — {self.organization.code} ({self.membership_type})"


class HealthRecord(models.Model):
    """
    Модель учета здоровья кота:
    - прививки, болезни, обследования
    - дата записи
    - примечания
    """
    cat = models.ForeignKey(
        "Cat",
        on_delete=models.CASCADE,
        related_name="health_records"
    )

    class HealthType(models.TextChoices):
        VACCINATION = "VACCINATION", "Прививка"
        ILLNESS = "ILLNESS", "Болезнь"
        CHECKUP = "CHECKUP", "Обследование"
        OTHER = "OTHER", "Другое"

    record_type = models.CharField(
        max_length=20,
        choices=HealthType.choices,
        default=HealthType.OTHER,
        verbose_name="Тип записи"
    )

    name = models.CharField(max_length=200, verbose_name="Название")
    date = models.DateField(verbose_name="Дата записи")
    remark = models.TextField(blank=True, verbose_name="Примечание")

    class Meta:
        verbose_name = "Запись о здоровье"
        verbose_name_plural = "Записи о здоровье"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.cat} — {self.name} ({self.record_type})"


class Document(models.Model):
    """
    Документы (родословные, договоры и т.д.)
    """

    file = models.ForeignKey(
        "MediaFile",
        on_delete=models.CASCADE,
        related_name="documents"
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="documents"
    )

    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    doc_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Тип документа"
    )

    is_public = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or str(self.file)


class Title(TranslatableModel):
    """
    Модель титула кота.
    Используется для фиксации титулов из родословных:
    - Аббревиатура титула (например, CH, IC, NW)
    - Полное название титула (можно перевести)
    - Тип титула (для классификации, например, чемпион, интер-чемпион)
    - Дата присвоения титула
    - Примечания
    """

    translations = TranslatedFields(
        full_name=models.CharField(
            max_length=200,
            verbose_name="Полное название титула"
        )
    )

    abbreviation = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Аббревиатура титула"
    )

    class TitleType(models.TextChoices):
        CHAMPION = "CHAMPION", "Чемпион"
        INTERCHAMPION = "INTERCHAMPION", "Международный чемпион"
        NATIONAL = "NATIONAL", "Национальный титул"
        WORLD = "WORLD", "Мировой титул"
        OTHER = "OTHER", "Другое"

    title_type = models.CharField(
        max_length=20,
        choices=TitleType.choices,
        default=TitleType.OTHER,
        verbose_name="Тип титула"
    )

    awarded_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата присвоения"
    )

    remark = models.TextField(
        blank=True,
        verbose_name="Примечание"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата изменения"
    )

    class Meta:
        verbose_name = "Титул"
        verbose_name_plural = "Титулы"
        ordering = ["abbreviation"]

    def __str__(self):
        # Берём имя на доступном языке, если оно есть, иначе пустая строка
        full = self.safe_translation_getter("full_name", any_language=True) or ""
        return f"{self.abbreviation} ({full})"


class Cat(models.Model):
    """
    Главная модель кота в питомнике.
    Хранит базовую информацию:
    - официальное имя
    - пол
    - даты рождения
    - идентификаторы
    - связи с родителями и питомником
    """

    class Sex(models.TextChoices):
        MALE = "M", "Самец"
        FEMALE = "F", "Самка"

    class Status(models.TextChoices):
        ALIVE = "ALIVE", "Жив"
        DECEASED = "DECEASED", "Погиб"
        SOLD = "SOLD", "Продан"

    registered_name = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Официальное имя (родословная)"
    )

    call_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Домашнее имя"
    )

    sex = models.CharField(
        max_length=1,
        choices=Sex.choices,
        verbose_name="Пол"
    )

    birth_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата рождения"
    )

    death_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата смерти"
    )

    # 🧬 Идентификаторы

    microchip = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Микрочип"
    )

    pedigree_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Номер родословной"
    )

    # 🐾 Связи

    breed = models.ForeignKey(
        "Breed",
        on_delete=models.PROTECT,
        related_name="cats",
        verbose_name="Порода"
    )

    cattery = models.ForeignKey(
        "Cattery",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cats",
        verbose_name="Питомник рождения"
    )

    # 🧬 Родители (само-ссылки)

    father = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kittens_from_father",
        limit_choices_to={"sex": "M"},
        verbose_name="Отец"
    )

    mother = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kittens_from_mother",
        limit_choices_to={"sex": "F"},
        verbose_name="Мать"
    )

    owner = models.ForeignKey(
        Person,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_cats"
    )

    # 📊 Статус в питомнике

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )

    is_for_breeding = models.BooleanField(
        default=True,
        verbose_name="Допущен к разведению"
    )

    remark = models.TextField(
        blank=True,
        verbose_name="Примечание"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    litter = models.ForeignKey(
        "Litter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kittens",
        verbose_name="Помёт"
    )

    class Meta:
        verbose_name = "Кот"
        verbose_name_plural = "Коты"
        ordering = ["registered_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["registered_name", "cattery"],
                name="unique_name_per_cattery"
            )
        ]

    def __str__(self):
        return self.registered_name

    @property
    def ems_code(self):
        return self.cat_color.ems_code if hasattr(self, "cat_color") else ""

    @property
    def color(self):
        return self.cat_color.color if hasattr(self, "cat_color") else None


class CatName(models.Model):
    """
    Альтернативные имена кота
    """

    cat = models.ForeignKey(
        "Cat",
        on_delete=models.CASCADE,
        related_name="names"
    )

    name = models.CharField(max_length=200)

    language_code = models.CharField(
        max_length=10,
        blank=True
    )

    is_official = models.BooleanField(default=False)

    remark = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_official", "name"]
        unique_together = ("cat", "name", "language_code")

    def __str__(self):
        return self.name


class Litter(models.Model):
    """
    Помёт котят.
    Объединяет котят от одной вязки:
    - родители
    - дата рождения
    - питомник
    - код помёта
    """

    litter_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Код помёта"
    )

    birth_date = models.DateField(
        verbose_name="Дата рождения"
    )

    cattery = models.ForeignKey(
        "Cattery",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="litters",
        verbose_name="Питомник"
    )

    father = models.ForeignKey(
        "Cat",
        on_delete=models.PROTECT,
        related_name="litters_as_father",
        limit_choices_to={"sex": "M"},
        verbose_name="Отец"
    )

    mother = models.ForeignKey(
        "Cat",
        on_delete=models.PROTECT,
        related_name="litters_as_mother",
        limit_choices_to={"sex": "F"},
        verbose_name="Мать"
    )

    kittens_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Количество котят"
    )

    remark = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # Явное объявление для IDE, чтобы PyCharm видел обратную связь
    if TYPE_CHECKING:
        kittens: "models.QuerySet[Cat]"

    class Meta:
        verbose_name = "Помёт"
        verbose_name_plural = "Помёты"
        ordering = ["-birth_date"]

    def __str__(self):
        return f"{self.litter_code} ({self.birth_date})"

    def sync_kittens(self):
        """
        Создает недостающих котят в соответствии с kittens_count.
        Безопасно — не удаляет существующих.
        """
        existing_count = self.kittens.count()
        for i in range(existing_count + 1, self.kittens_count + 1):
            # для транзакции обязательно заполняем обязательные NOT NULL поля
            Cat.objects.create(
                registered_name=f"{self.litter_code} Kitten {i}",
                sex="M",  # временно, позже можно задать реальный пол
                birth_date=self.birth_date,
                breed=self.father.breed if self.father else None,
                cattery=self.cattery,
                father=self.father,
                mother=self.mother,
                litter=self
            )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.kittens_count > 0:
            self.sync_kittens()


class Page(models.Model):
    """
    Страница сайта
    """

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ContentBlock(TranslatableModel):
    """
    Блок контента страницы
    """

    BLOCK_TYPES = [
        ('title', 'Заголовок'),
        ('paragraph', 'Параграф'),
        ('image', 'Изображение'),
        ('list', 'Список'),
    ]

    page = models.ForeignKey(
        "Page",
        related_name="blocks",
        on_delete=models.CASCADE
    )

    order = models.PositiveIntegerField(default=0)

    block_type = models.CharField(
        max_length=20,
        choices=BLOCK_TYPES,
        default='paragraph'
    )

    translations = TranslatedFields(
        title=models.CharField(max_length=200, blank=True),
        text=models.TextField(blank=True),
    )

    image = models.ImageField(
        upload_to="page_blocks/",
        blank=True,
        null=True
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.page.slug} - {self.block_type} ({self.order})"


