from django import forms
from .models import *
from .ems import validate_components


class CatForm(forms.ModelForm):
    color = forms.ModelChoiceField(
        queryset=Color.objects.filter(is_active=True).order_by("ems_code"),
        required=False,
        label="Окрас",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = Cat
        fields = [
            "registered_name",
            "call_name",
            "sex",
            "birth_date",
            "death_date",
            "breed",
            "cattery",
            "father",
            "mother",
            "owner",
            "litter",
            "pedigree_number",
            "microchip",
            "is_active",
            "is_for_breeding",
            "is_featured",
            "remark",
        ]
        widgets = {
            "registered_name": forms.TextInput(attrs={"class": "form-control"}),
            "call_name": forms.TextInput(attrs={"class": "form-control"}),
            "sex": forms.Select(attrs={"class": "form-select"}),
            "birth_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "death_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "breed": forms.Select(attrs={"class": "form-select"}),
            "cattery": forms.Select(attrs={"class": "form-select"}),
            "father": forms.Select(attrs={"class": "form-select"}),
            "mother": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "litter": forms.Select(attrs={"class": "form-select"}),
            "pedigree_number": forms.TextInput(attrs={"class": "form-control"}),
            "microchip": forms.TextInput(attrs={"class": "form-control"}),
            "remark": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_for_breeding": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["father"].queryset = Cat.objects.filter(sex="M").order_by("registered_name")
        self.fields["mother"].queryset = Cat.objects.filter(sex="F").order_by("registered_name")

        self.fields["father"].required = False
        self.fields["mother"].required = False
        self.fields["cattery"].required = False
        self.fields["call_name"].required = False
        self.fields["birth_date"].required = False
        self.fields["death_date"].required = False
        self.fields["pedigree_number"].required = False
        self.fields["microchip"].required = False
        self.fields["owner"].required = False
        self.fields["litter"].required = False
        self.fields["remark"].required = False
        self.fields["color"].required = False

        if self.instance.pk and hasattr(self.instance, "cat_color"):
            self.fields["color"].initial = self.instance.cat_color.color

    def clean(self):
        cleaned_data = super().clean()

        father = cleaned_data.get("father")
        mother = cleaned_data.get("mother")
        birth_date = cleaned_data.get("birth_date")
        death_date = cleaned_data.get("death_date")
        microchip = (cleaned_data.get("microchip") or "").strip()
        pedigree_number = (cleaned_data.get("pedigree_number") or "").strip()
        registered_name = (cleaned_data.get("registered_name") or "").strip()
        cattery = cleaned_data.get("cattery")

        if father and father.sex != "M":
            self.add_error("father", "Отец должен быть самцом.")

        if mother and mother.sex != "F":
            self.add_error("mother", "Мать должна быть самкой.")

        if father and mother and father == mother:
            raise forms.ValidationError("Отец и мать не могут быть одним и тем же животным.")

        if birth_date and death_date and death_date < birth_date:
            self.add_error("death_date", "Дата смерти не может быть раньше даты рождения.")

        # Проверка уникальности microchip
        if microchip:
            qs = Cat.objects.filter(microchip=microchip)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("microchip", "Кот с таким микрочипом уже существует.")

        # Проверка уникальности pedigree_number
        if pedigree_number:
            qs = Cat.objects.filter(pedigree_number=pedigree_number)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("pedigree_number", "Кот с таким номером родословной уже существует.")

        # Повторим проверку существующего ограничения registered_name + cattery в удобном виде
        if registered_name:
            qs = Cat.objects.filter(registered_name=registered_name, cattery=cattery)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("registered_name", "Кот с таким именем уже существует в этом питомнике.")

        return cleaned_data

    def save(self, commit=True):
        cat = super().save(commit=commit)

        color = self.cleaned_data.get("color")

        cat_color, _ = CatColor.objects.get_or_create(cat=cat)

        if color:
            cat_color.color = color
            cat_color.save()
        else:
            if cat_color.color_id:
                cat_color.color = None
                cat_color.save()

        return cat


class ColorForm(forms.ModelForm):
    components = forms.ModelMultipleChoiceField(
        queryset=ColorComponent.objects.filter(is_active=True)
        .select_related("type")
        .order_by("type__order", "order", "code"),
        required=True,
        label="Компоненты окраса",
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 12}),
    )

    class Meta:
        model = Color
        fields = [
            "components",
            "is_active",
            "remark",
        ]
        widgets = {
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "remark": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            self.fields["components"].initial = self.instance.get_components_ordered()

    def clean_components(self):
        components = list(self.cleaned_data.get("components") or [])

        if not components:
            raise forms.ValidationError("Выберите хотя бы один компонент.")

        validate_components(components)
        return components

    def save(self, commit=True):
        color = super().save(commit=False)

        if commit:
            color.save()

            components = list(self.cleaned_data["components"])
            components = sorted(
                components,
                key=lambda c: (c.type.order, c.order, c.code)
            )

            ColorComponentUsage.objects.filter(color=color).delete()

            for position, component in enumerate(components, start=1):
                ColorComponentUsage.objects.create(
                    color=color,
                    component=component,
                    position=position
                )

            color.rebuild_ems_code(save=True)

        return color


class CatPhotoForm(forms.ModelForm):
    class Meta:
        model = CatPhoto
        fields = [
            "image",
            "title",
            "description",
            "is_primary",
            "sort_order",
            "is_active",
        ]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_primary": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def save(self, commit=True, cat=None):
        photo = super().save(commit=False)

        if cat is not None:
            photo.cat = cat

        if commit:
            photo.save()

        return photo


class GalleryAlbumForm(forms.ModelForm):
    class Meta:
        model = GalleryAlbum
        fields = ["category", "date", "litter", "sort_order", "is_active", "cover"]
        widgets = {
            "category":   forms.Select(attrs={"class": "form-control"}),
            "date":       forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "litter":     forms.Select(attrs={"class": "form-control"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "cover":      forms.ClearableFileInput(attrs={"class": "form-control"}),
            "is_active":  forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    # Поля перевода (title и description) — добавляем вручную
    # потому что parler не включает их автоматически в ModelForm
    title = forms.CharField(
        max_length=200,
        label="Название альбома",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    description = forms.CharField(
        required=False,
        label="Описание",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["litter"].required = False
        self.fields["date"].required = False
        self.fields["cover"].required = False
        self.fields["sort_order"].required = False

        # Заполняем поля перевода из существующего объекта
        if self.instance.pk:
            self.fields["title"].initial = self.instance.safe_translation_getter(
                "title", any_language=True
            )
            self.fields["description"].initial = self.instance.safe_translation_getter(
                "description", any_language=True
            )

    def save(self, commit=True):
        album = super().save(commit=False)
        if commit:
            album.save()
            # Сохраняем перевод на текущий язык
            album.set_current_language("ru")
            album.title = self.cleaned_data["title"]
            album.description = self.cleaned_data.get("description", "")
            album.save()
        return album


class GalleryPhotoForm(forms.ModelForm):
    class Meta:
        model = GalleryPhoto
        fields = ["image", "title", "instagram_url", "sort_order", "is_active"]
        widgets = {
            "image":         forms.ClearableFileInput(attrs={"class": "form-control"}),
            "title":         forms.TextInput(attrs={"class": "form-control"}),
            "instagram_url": forms.URLInput(attrs={"class": "form-control"}),
            "sort_order":    forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active":     forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False
        self.fields["instagram_url"].required = False
        self.fields["sort_order"].required = False


# Formset для массовой загрузки фото
GalleryPhotoFormSet = forms.modelformset_factory(
    GalleryPhoto,
    form=GalleryPhotoForm,
    extra=5,       # 5 пустых форм для загрузки
    can_delete=True,
)