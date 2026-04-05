from typing import TYPE_CHECKING
from parler.models import TranslatableModel, TranslatedFields
from .ems import build_ems_code, validate_components
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Q
from .utils.media_paths import upload_to_media
from django.utils.translation import get_language
from django.conf import settings
import os
from django.utils.text import slugify
from django.db.models.signals import post_save
from django.dispatch import receiver

User = get_user_model()


def upload_to_cat_photo(instance, filename):
    """
    Фото кота хранятся в:
    images/cat_<id>/<filename>
    """
    base, ext = os.path.splitext(filename)
    safe_name = slugify(base) or "photo"
    return f"images/cat_{instance.cat_id}/{safe_name}{ext.lower()}"


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
            verbose_name="Color name",
            blank=True
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
    )

    class Meta:
        verbose_name = "Color"
        verbose_name_plural = "Colors"
        ordering = ["ems_code"]

    def get_components_ordered(self):
        """
        Возвращает компоненты цвета в правильном порядке EMS.
        """
        return [
            usage.component
            for usage in self.component_usages.select_related(
                "component",
                "component__type"
            ).all()
        ]

    def build_localized_name(self, language_code=None):
        """
        Собирает локализованное имя окраса из переведённых компонентов.
        """
        from django.utils.translation import get_language

        language_code = language_code or get_language() or "ru"
        components = self.get_components_ordered()

        if components:
            parts = []
            for component in components:
                part = component.safe_translation_getter(
                    "name",
                    language_code=language_code,
                    any_language=True
                )
                if part:
                    parts.append(part.strip())

            if parts:
                return " ".join(parts)

        manual_name = self.safe_translation_getter(
            "name",
            language_code=language_code,
            any_language=True
        )
        return (manual_name or "").strip()

    @property
    def localized_name(self):
        return self.build_localized_name()

    def get_display_name(self, language_code=None):
        name = self.build_localized_name(language_code=language_code)
        if name:
            return f"{name} ({self.ems_code})"
        return f"({self.ems_code})"

    def __str__(self):
        return self.get_display_name()

    def rebuild_ems_code(self, save=True):
        """
        Пересчитывает EMS код по компонентам.
        """
        components = self.get_components_ordered()
        if components:
            validate_components(components)
            self.ems_code = build_ems_code(components)

        if save:
            super().save(update_fields=["ems_code"])

        return self.ems_code

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @staticmethod
    def allowed_components(selected):
        """
        Возвращает QuerySet компонентов, которые можно выбрать к уже выбранным.
        С учётом правил EMS (BASE/SILVER/GOLD/WHITE)
        """
        qs = ColorComponent.objects.all()
        selected_ids = [c.id for c in selected]

        if any(c.code == "w" for c in selected):
            return qs.filter(code="w") | ColorComponent.objects.filter(id__in=selected_ids)

        if any(c.type.code == "BASE" for c in selected):
            qs = qs.exclude(type__code="BASE")

        if any(c.code == "s" for c in selected):
            qs = qs.exclude(code="y")
        if any(c.code == "y" for c in selected):
            qs = qs.exclude(code="s")

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
    Модель, связывающая кота с его цветом.
    """

    cat = models.OneToOneField(
        "cats.Cat",
        on_delete=models.CASCADE,
        related_name="cat_color"
    )

    components = models.ManyToManyField(
        ColorComponent,
        related_name="cat_colors",
        blank=True
    )

    ems_code = models.CharField(
        max_length=50,
        verbose_name="EMS code",
        blank=True,
        default=""
    )

    color = models.ForeignKey(
        "Color",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cat_colors"
    )

    class Meta:
        verbose_name = "Cat Color"
        verbose_name_plural = "Cat Colors"

    def __str__(self):
        return f"{self.cat.registered_name} — {self.ems_code}"

    def rebuild_ems_code(self, save=True):
        """
        Пересчитывает EMS код безопасно:
        - если выбран справочный цвет -> берём его ems_code
        - иначе собираем из компонентов
        """
        if self.color:
            self.ems_code = self.color.ems_code
        else:
            if not self.pk:
                self.ems_code = ""
            else:
                components = list(self.components.select_related("type"))
                if components:
                    validate_components(components)
                    self.ems_code = build_ems_code(components)
                else:
                    self.ems_code = ""

        if save:
            super().save(update_fields=["ems_code"] if self.pk else None)

        return self.ems_code

    def save(self, *args, **kwargs):
        """
        На первом сохранении нельзя трогать ManyToMany components,
        потому что объект ещё без pk.
        """
        if self.color:
            self.ems_code = self.color.ems_code
        elif not self.pk:
            self.ems_code = ""

        super().save(*args, **kwargs)

        if not self.color and self.pk:
            components = list(self.components.select_related("type"))
            new_code = ""
            if components:
                validate_components(components)
                new_code = build_ems_code(components)

            if self.ems_code != new_code:
                self.ems_code = new_code
                super().save(update_fields=["ems_code"])


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

    # ===== Социальные сети =====
    instagram = models.URLField(blank=True, verbose_name="Instagram")
    facebook = models.URLField(blank=True, verbose_name="Facebook")
    tiktok = models.URLField(blank=True, verbose_name="TikTok")
    whatsapp = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="WhatsApp",
        help_text="Номер телефона с кодом страны, например +491234567890"
    )

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

    file = models.FileField(upload_to=upload_to_media)

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
    """Модель для связывания медиафайлов с различными объектами."""

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

    is_primary = models.BooleanField(
        default=False,
        verbose_name="Главное фото"
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок"
    )

    class Meta:
        ordering = ["sort_order", "-id"]

    def __str__(self):
        return f"{self.content_object} -> {self.file} ({self.role})"


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
    - Тип титула (для классификации, например, чемпион, интернациональный чемпион)
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
        MALE = "M", "Кот"
        FEMALE = "F", "Кошка"

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

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )

    is_for_breeding = models.BooleanField(
        default=True,
        verbose_name="Допущен к разведению"
    )

    is_featured = models.BooleanField(
        default=False,
        verbose_name="Показывать на витрине"
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
            ),
            models.UniqueConstraint(
                fields=["microchip"],
                condition=~Q(microchip=""),
                name="unique_nonempty_microchip"
            ),
            models.UniqueConstraint(
                fields=["pedigree_number"],
                condition=~Q(pedigree_number=""),
                name="unique_nonempty_pedigree_number"
            ),
        ]

    def __str__(self):
        return self.registered_name

    @property
    def ems_code(self):
        return self.cat_color.ems_code if hasattr(self, "cat_color") else ""

    @property
    def color(self):
        return self.cat_color.color if hasattr(self, "cat_color") else None

    def get_images(self):
        """
        Временно оставляем старое имя метода,
        но теперь возвращаем фотографии из CatPhoto.
        """
        return self.photos.filter(is_active=True)

    def get_main_image(self):
        return (
                self.photos.filter(is_active=True, is_primary=True).first()
                or self.photos.filter(is_active=True).first()
        )


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

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активный помёт",
        help_text="Снимите галочку когда все котята разъехались"
    )

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


class CatPhoto(models.Model):
    """
    Отдельная модель фотографий кота.
    Фото хранятся в images/cat_<id>/...
    """

    cat = models.ForeignKey(
        "Cat",
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="Кот"
    )

    image = models.ImageField(
        upload_to=upload_to_cat_photo,
        verbose_name="Фотография"
    )

    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Название"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )

    is_primary = models.BooleanField(
        default=False,
        verbose_name="Главное фото"
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок"
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата загрузки"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активно"
    )

    class Meta:
        verbose_name = "Фото кота"
        verbose_name_plural = "Фотографии котов"
        ordering = ["sort_order", "-is_primary", "-uploaded_at"]

    def __str__(self):
        return self.title or f"{self.cat.registered_name} - photo #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.is_primary:
            CatPhoto.objects.filter(cat=self.cat).exclude(pk=self.pk).update(is_primary=False)


# ============================================================
# Добавить в models.py — новые модели для галереи и видео
# ============================================================


def upload_to_gallery_cover(instance, filename):
    """
    Обложка альбома хранится в: gallery/album_<id>/cover/<filename>
    instance — это GalleryAlbum, поэтому используем instance.pk
    Если pk ещё нет (новый объект) — кладём во временную папку.
    """
    import os
    from django.utils.text import slugify
    base, ext = os.path.splitext(filename)
    safe_name = slugify(base) or "cover"
    pk = instance.pk or "new"
    return f"gallery/album_{pk}/cover/{safe_name}{ext.lower()}"


def upload_to_gallery_photo(instance, filename):
    """
    Фото галереи хранятся в: gallery/album_<album_id>/<filename>
    instance — это GalleryPhoto, поэтому используем instance.album_id
    """
    import os
    from django.utils.text import slugify
    base, ext = os.path.splitext(filename)
    safe_name = slugify(base) or "photo"
    return f"gallery/album_{instance.album_id}/{safe_name}{ext.lower()}"


def upload_to_video_thumb(instance, filename):
    """Превью видео хранятся в: video/thumbs/<filename>"""
    base, ext = os.path.splitext(filename)
    safe_name = slugify(base) or "thumb"
    return f"video/thumbs/{safe_name}{ext.lower()}"


def upload_to_video_file(instance, filename):
    """Файлы видео хранятся в: video/files/<filename>"""
    base, ext = os.path.splitext(filename)
    safe_name = slugify(base) or "video"
    return f"video/files/{safe_name}{ext.lower()}"


# ============================================================
# GALLERY ALBUM
# ============================================================

class GalleryAlbum(TranslatableModel):
    """
    Альбом галереи.
    Категории:
      - LIFE    — повседневная жизнь питомника
      - LITTER  — общие фото помётов (котята вместе, с родителями)
      - ART     — художественные фото
    """

    class Category(models.TextChoices):
        LIFE   = "LIFE",   "Повседневная жизнь"
        LITTER = "LITTER", "Помёты"
        ART    = "ART",    "Художественные"

    translations = TranslatedFields(
        title=models.CharField(
            max_length=200,
            verbose_name="Название альбома"
        ),
        description=models.TextField(
            blank=True,
            verbose_name="Описание"
        ),
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.LIFE,
        verbose_name="Категория"
    )

    cover = models.ImageField(
        upload_to=upload_to_gallery_cover,
        null=True,
        blank=True,
        verbose_name="Обложка альбома"
    )

    date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата"
    )

    # Связь с помётом — для категории LITTER
    litter = models.ForeignKey(
        "Litter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gallery_albums",
        verbose_name="Помёт (если альбом помёта)"
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Альбом галереи"
        verbose_name_plural = "Альбомы галереи"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return self.safe_translation_getter("title", any_language=True) or f"Album #{self.pk}"

    def get_cover(self):
        """Возвращает обложку альбома или первое фото."""
        if self.cover:
            return self.cover
        first = self.photos.filter(is_active=True).first()
        return first.image if first else None

    @property
    def photos_count(self):
        return self.photos.filter(is_active=True).count()


# ============================================================
# GALLERY PHOTO
# ============================================================

class GalleryPhoto(models.Model):
    """
    Фотография в альбоме галереи.
    Не привязана к конкретному коту — это общие фото питомника.
    """

    album = models.ForeignKey(
        GalleryAlbum,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="Альбом"
    )

    image = models.ImageField(
        upload_to=upload_to_gallery_photo,
        verbose_name="Фото"
    )

    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Подпись"
    )

    # Instagram source — для отслеживания откуда фото
    instagram_url = models.URLField(
        blank=True,
        verbose_name="Ссылка на пост Instagram"
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активно"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Фото галереи"
        verbose_name_plural = "Фото галереи"
        ordering = ["sort_order", "-uploaded_at"]

    def __str__(self):
        return self.title or f"Photo #{self.pk} ({self.album})"


# ============================================================
# VIDEO
# ============================================================

class Video(TranslatableModel):
    """
    Видео питомника.
    Поддерживает два источника:
      - YouTube / Vimeo — через video_url
      - Файл на сервере — через video_file
    Используется то что заполнено (приоритет у video_url).
    """

    class Category(models.TextChoices):
        LIFE   = "LIFE",   "Повседневная жизнь"
        LITTER = "LITTER", "Котята и помёты"
        OTHER  = "OTHER",  "Разное"

    translations = TranslatedFields(
        title=models.CharField(
            max_length=200,
            verbose_name="Название"
        ),
        description=models.TextField(
            blank=True,
            verbose_name="Описание"
        ),
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.LIFE,
        verbose_name="Категория"
    )

    # Источник 1 — ссылка (YouTube / Vimeo)
    video_url = models.URLField(
        blank=True,
        verbose_name="Ссылка на YouTube / Vimeo",
        help_text="Например: https://www.youtube.com/watch?v=XXXXX"
    )

    # Источник 2 — файл на сервере
    video_file = models.FileField(
        upload_to=upload_to_video_file,
        null=True,
        blank=True,
        verbose_name="Видеофайл (mp4)",
        help_text="Только для коротких клипов до 50 МБ"
    )

    # Превью
    thumbnail = models.ImageField(
        upload_to=upload_to_video_thumb,
        null=True,
        blank=True,
        verbose_name="Превью"
    )

    # Связь с помётом (опционально)
    litter = models.ForeignKey(
        "Litter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="videos",
        verbose_name="Помёт"
    )

    date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата съёмки"
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активно"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Видео"
        verbose_name_plural = "Видео"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return self.safe_translation_getter("title", any_language=True) or f"Video #{self.pk}"

    @property
    def embed_url(self):
        """
        Возвращает embed-ссылку для вставки плеера.
        Поддерживает YouTube и Vimeo.
        """
        if not self.video_url:
            return None

        url = self.video_url

        # YouTube
        if "youtube.com/watch" in url:
            video_id = url.split("v=")[-1].split("&")[0]
            return f"https://www.youtube.com/embed/{video_id}"
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[-1].split("?")[0]
            return f"https://www.youtube.com/embed/{video_id}"

        # Vimeo
        if "vimeo.com/" in url:
            video_id = url.rstrip("/").split("/")[-1]
            return f"https://player.vimeo.com/video/{video_id}"

        return url

    @property
    def is_external(self):
        """True если видео на YouTube/Vimeo."""
        return bool(self.video_url)


class UserProfile(models.Model):
    """
    Расширенный профиль пользователя.
    Связан с User через OneToOne.
    Создаётся автоматически при регистрации через сигнал.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    first_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Имя'
    )

    last_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Фамилия'
    )

    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        verbose_name='Аватар'
    )

    bio = models.TextField(
        blank=True,
        verbose_name='О себе'
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Город'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f'Профиль: {self.user.email}'

    @property
    def display_name(self):
        if self.first_name:
            return f'{self.first_name} {self.last_name}'.strip()
        return self.user.email.split('@')[0]

    @property
    def avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return None

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Создаёт профиль при регистрации нового пользователя."""
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сохраняет профиль при сохранении пользователя."""
    if hasattr(instance, 'profile'):
        instance.profile.save()


class ForumCategory(models.Model):
    """
    Раздел форума. Например: «О породе», «Помёты», «Ваши истории».
    Создаётся вручную администратором.
    """
    name = models.CharField(max_length=200, verbose_name='Название')
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True, verbose_name='Описание')
    icon = models.CharField(
        max_length=10, blank=True,
        verbose_name='Иконка (emoji)',
        help_text='Например: 🐱'
    )
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Раздел форума'
        verbose_name_plural = 'Разделы форума'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    @property
    def topics_count(self):
        return self.topics.filter(is_active=True).count()

    @property
    def last_post(self):
        return ForumPost.objects.filter(
            topic__category=self,
            topic__is_active=True,
            is_active=True
        ).order_by('-created_at').first()


class ForumTopic(models.Model):
    """
    Тема (тред) в разделе форума.
    Создаётся пользователем.
    """
    category = models.ForeignKey(
        ForumCategory,
        on_delete=models.CASCADE,
        related_name='topics',
        verbose_name='Раздел'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='forum_topics',
        verbose_name='Автор'
    )
    title = models.CharField(max_length=300, verbose_name='Заголовок')
    slug = models.SlugField(max_length=300, unique=True)
    body = models.TextField(verbose_name='Текст')

    is_pinned = models.BooleanField(
        default=False,
        verbose_name='Закреплено',
        help_text='Закреплённые темы всегда сверху'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    views_count = models.PositiveIntegerField(default=0, verbose_name='Просмотры')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Тема форума'
        verbose_name_plural = 'Темы форума'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('forum_topic', kwargs={
            'category_slug': self.category.slug,
            'topic_slug': self.slug
        })

    @property
    def posts_count(self):
        return self.posts.filter(is_active=True).count()

    @property
    def last_post(self):
        return self.posts.filter(is_active=True).order_by('-created_at').first()

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            import uuid
            base_slug = slugify(self.title)[:280] or 'topic'
            self.slug = f'{base_slug}-{str(uuid.uuid4())[:8]}'
        super().save(*args, **kwargs)


class ForumPost(models.Model):
    """
    Сообщение в теме форума.
    """
    topic = models.ForeignKey(
        ForumTopic,
        on_delete=models.CASCADE,
        related_name='posts',
        verbose_name='Тема'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='forum_posts',
        verbose_name='Автор'
    )
    body = models.TextField(verbose_name='Текст сообщения')

    # Для редактирования
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True, verbose_name='Активно')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Сообщение форума'
        verbose_name_plural = 'Сообщения форума'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.author} → {self.topic.title[:50]}'


