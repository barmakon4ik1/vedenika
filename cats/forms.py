from django import forms
from .models import Cat


class CatForm(forms.ModelForm):
    class Meta:
        model = Cat
        fields = [
            "registered_name",
            "call_name",
            "sex",
            "birth_date",
            "breed",
            "cattery",
            "father",
            "mother",
            "pedigree_number",
            "microchip",
            "is_active",
            "is_for_breeding",
            "remark",
        ]
        widgets = {
            "registered_name": forms.TextInput(attrs={"class": "form-control"}),
            "call_name": forms.TextInput(attrs={"class": "form-control"}),
            "sex": forms.Select(attrs={"class": "form-select"}),
            "birth_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "breed": forms.Select(attrs={"class": "form-select"}),
            "cattery": forms.Select(attrs={"class": "form-select"}),
            "father": forms.Select(attrs={"class": "form-select"}),
            "mother": forms.Select(attrs={"class": "form-select"}),
            "pedigree_number": forms.TextInput(attrs={"class": "form-control"}),
            "microchip": forms.TextInput(attrs={"class": "form-control"}),
            "remark": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_for_breeding": forms.CheckboxInput(attrs={"class": "form-check-input"}),
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
        self.fields["pedigree_number"].required = False
        self.fields["microchip"].required = False
        self.fields["remark"].required = False