from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.views.generic import DetailView, ListView
from django.http import HttpResponseForbidden
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from .models import *
from .forms import *

User = get_user_model()
# =========================================================
# 🔐 PERMISSIONS
# =========================================================

def is_admin(user):
    return user.is_authenticated and user.is_staff


def owner_required(obj, user):
    return obj.owner == user


# =========================================================
# 📁 MEDIA
# =========================================================

@login_required
def my_media(request):
    media = MediaFile.objects.filter(owner=request.user)
    return render(request, "my_media.html", {"media": media})


@login_required
def upload_media(request):
    if request.method == "POST":
        file = request.FILES.get("file")

        if file:
            MediaFile.objects.create(
                file=file,
                owner=request.user
            )

        return redirect("my_media")

    return render(request, "upload_media.html")


@login_required
def delete_media(request, pk):
    media = get_object_or_404(MediaFile, pk=pk)

    if not owner_required(media, request.user):
        raise PermissionDenied()

    media.delete()
    return redirect("my_media")


# =========================================================
# 📄 DOCUMENTS
# =========================================================

@login_required
def my_documents(request):
    docs = Document.objects.filter(owner=request.user)
    return render(request, "my_documents.html", {"documents": docs})


@login_required
def upload_document(request):
    if request.method == "POST":
        file_id = request.POST.get("file_id")
        file = get_object_or_404(MediaFile, id=file_id)

        if not owner_required(file, request.user):
            raise PermissionDenied()

        Document.objects.create(
            file=file,
            owner=request.user,
            title=request.POST.get("title", "")
        )

        return redirect("my_documents")

    media = MediaFile.objects.filter(owner=request.user)
    return render(request, "upload_document.html", {"media": media})


# =========================================================
# 🐱 CATS (публичные)
# =========================================================

def cat_list(request):
    cats = Cat.objects.filter(is_active=True)
    return render(request, "cat_list.html", {"cats": cats})


# =========================================================
# 🛠 ADMIN (если нужен вне admin)
# =========================================================

@user_passes_test(is_admin)
def admin_dashboard(request):
    return render(request, "admin_dashboard.html")



# =========================================================
# 🐱 CATS (страница с деталями, с использованием DetailView)
# =========================================================
class CatDetailView(DetailView):
    model = Cat
    template_name = "cat_detail.html"
    context_object_name = "cat"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cat = self.object

        context["images"] = cat.get_images()
        context["main_image"] = cat.get_main_image()

        return context


# =========================================================
# 🐱 Home page
# =========================================================
def home(request):
    return render(request, "home.html")

# =========================================================
# 🐱 Страница котов
# =========================================================
class CatListView(ListView):
    model = Cat
    template_name = "cat_list.html"
    context_object_name = "cats"
    paginate_by = 24

    OWNER_PERSON_ID = 1   # <-- сюда поставь реальный id из cats_person

    def get_queryset(self):
        qs = (
            Cat.objects
            .filter(
                is_active=True,
                is_featured=True,
                owner_id=self.OWNER_PERSON_ID
            )
            .select_related(
                "breed", "cattery", "cat_color",
                "father", "mother", "owner", "litter"
            )
            .prefetch_related("cat_color__components")
            .order_by("registered_name")
            .distinct()
        )

        breed = self.request.GET.get("breed")
        sex = self.request.GET.get("sex")
        color = self.request.GET.get("color")

        if breed:
            qs = qs.filter(breed_id=breed)

        if sex:
            qs = qs.filter(sex=sex)

        if color:
            qs = qs.filter(cat_color__color_id=color)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import Breed, Color

        context["breeds"] = Breed.objects.filter(is_active=True).order_by("ems_code")
        context["colors"] = Color.objects.filter(is_active=True).order_by("ems_code")
        context["selected_breed"] = self.request.GET.get("breed", "")
        context["selected_sex"] = self.request.GET.get("sex", "")
        context["selected_color"] = self.request.GET.get("color", "")
        return context


@staff_member_required
def upload_cat_photo(request, pk):
    cat = get_object_or_404(Cat, pk=pk)

    if request.method == "POST":
        form = CatPhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(cat=cat)

            if photo.is_primary:
                CatPhoto.objects.filter(cat=cat).exclude(pk=photo.pk).update(is_primary=False)
            elif not cat.photos.filter(is_primary=True).exists():
                photo.is_primary = True
                photo.save(update_fields=["is_primary"])

            return redirect("cat_gallery", pk=cat.pk)
    else:
        form = CatPhotoForm(initial={"is_active": True})

    return render(request, "cat_upload.html", {
        "cat": cat,
        "form": form,
    })


@staff_member_required
def delete_cat_photo(request, cat_pk, photo_pk):
    cat = get_object_or_404(Cat, pk=cat_pk)
    photo = get_object_or_404(CatPhoto, pk=photo_pk, cat=cat)

    if request.method == "POST":
        was_primary = photo.is_primary

        if photo.image:
            photo.image.delete(save=False)

        photo.delete()

        if was_primary:
            new_primary = cat.photos.filter(is_active=True).order_by("sort_order", "-uploaded_at").first()
            if new_primary:
                new_primary.is_primary = True
                new_primary.save(update_fields=["is_primary"])

        return redirect("cat_gallery", pk=cat.pk)

    return redirect("cat_gallery", pk=cat.pk)


class CatGalleryView(DetailView):
    model = Cat
    template_name = "cat_gallery.html"
    context_object_name = "cat"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["photos"] = self.object.photos.filter(is_active=True).order_by("sort_order", "-is_primary", "-uploaded_at")
        return context


@staff_member_required
def cat_create(request):
    if request.method == "POST":
        form = CatForm(request.POST)
        if form.is_valid():
            cat = form.save()
            return redirect("cat_detail", pk=cat.pk)
    else:
        form = CatForm()

    return render(request, "cat_form.html", {
        "form": form,
        "page_title": "Добавить кота",
        "is_edit": False,
    })

@staff_member_required
def cat_update(request, pk):
    cat = get_object_or_404(Cat, pk=pk)

    if request.method == "POST":
        form = CatForm(request.POST, instance=cat)
        if form.is_valid():
            cat = form.save()
            return redirect("cat_detail", pk=cat.pk)
    else:
        form = CatForm(instance=cat)

    return render(request, "cat_form.html", {
        "form": form,
        "page_title": "Редактировать кота",
        "is_edit": True,
        "cat": cat,
    })

@staff_member_required
def set_main_photo(request, cat_pk, photo_pk):
    cat = get_object_or_404(Cat, pk=cat_pk)
    photo = get_object_or_404(CatPhoto, pk=photo_pk, cat=cat)

    if request.method == "POST":
        CatPhoto.objects.filter(cat=cat).update(is_primary=False)
        photo.is_primary = True
        photo.save(update_fields=["is_primary"])

    return redirect("cat_gallery", pk=cat.pk)

@staff_member_required
def color_create_for_cat(request, cat_pk):
    cat = get_object_or_404(Cat, pk=cat_pk)

    if request.method == "POST":
        form = ColorForm(request.POST)
        if form.is_valid():
            color = form.save()

            cat_color, _ = CatColor.objects.get_or_create(cat=cat)
            cat_color.color = color
            cat_color.save()

            return redirect("cat_detail", pk=cat.pk)
    else:
        form = ColorForm()

    return render(request, "color_form.html", {
        "form": form,
        "page_title": f"Добавить окрас для {cat.registered_name}",
        "cat": cat,
        "is_edit": False,
    })


@staff_member_required
def color_update_for_cat(request, cat_pk):
    cat = get_object_or_404(Cat, pk=cat_pk)

    if not hasattr(cat, "cat_color") or not cat.cat_color.color:
        return redirect("color_create_for_cat", cat_pk=cat.pk)

    color = cat.cat_color.color

    if request.method == "POST":
        form = ColorForm(request.POST, instance=color)
        if form.is_valid():
            form.save()
            return redirect("cat_detail", pk=cat.pk)
    else:
        form = ColorForm(instance=color)

    return render(request, "color_form.html", {
        "form": form,
        "page_title": f"Редактировать окрас для {cat.registered_name}",
        "cat": cat,
        "is_edit": True,
        "color": color,
    })


# =========================================================
# 🐾 LITTERS
# =========================================================

class LitterListView(ListView):
    model = Litter
    template_name = "litter_list.html"
    context_object_name = "litters"
    ordering = ["-birth_date"]

    def get_queryset(self):
        return (
            Litter.objects
            .select_related("father", "mother", "cattery")
            .prefetch_related(
                "kittens",
                "kittens__photos",
                "kittens__cat_color",
                "father__photos",
                "mother__photos",
            )
            .order_by("-birth_date")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()

        litters_data = []
        for litter in context["litters"]:
            kittens = list(litter.kittens.all())
            males   = [k for k in kittens if k.sex == "M"]
            females = [k for k in kittens if k.sex == "F"]

            # Возраст в полных месяцах
            delta = today - litter.birth_date
            age_months = delta.days // 30

            # Помёт считается активным, если котята моложе 12 месяцев
            is_active = age_months < 12

            litters_data.append({
                "litter":     litter,
                "kittens":    kittens,
                "males":      males,
                "females":    females,
                "age_months": age_months,
                "is_active":  is_active,
            })

        context["litters_data"] = litters_data
        return context


class LitterDetailView(DetailView):
    model = Litter
    template_name = "litter_detail.html"
    context_object_name = "litter"

    def get_queryset(self):
        return (
            Litter.objects
            .select_related("father", "mother", "cattery")
            .prefetch_related(
                "kittens",
                "kittens__photos",
                "kittens__cat_color",
                "kittens__cat_color__color",
                "father__photos",
                "father__cat_color",
                "mother__photos",
                "mother__cat_color",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        litter  = self.object
        today   = timezone.now().date()

        kittens = list(litter.kittens.select_related(
            "cat_color", "cat_color__color"
        ).prefetch_related("photos").order_by("sex", "registered_name"))

        males   = [k for k in kittens if k.sex == "M"]
        females = [k for k in kittens if k.sex == "F"]

        delta      = today - litter.birth_date
        age_months = delta.days // 30
        age_weeks  = delta.days // 7
        is_active  = age_months < 12

        # Локации котят (без имён владельцев — только город/страна)
        kitten_locations = {}
        for kitten in kittens:
            if kitten.owner and kitten.owner.address:
                addr = kitten.owner.address
                parts = []
                if addr.city:
                    parts.append(str(addr.city))
                if addr.country:
                    parts.append(str(addr.country))
                kitten_locations[kitten.pk] = ", ".join(parts)
            else:
                kitten_locations[kitten.pk] = None

        context.update({
            "kittens":          kittens,
            "males":            males,
            "females":          females,
            "age_months":       age_months,
            "age_weeks":        age_weeks,
            "is_active":        is_active,
            "kitten_locations": kitten_locations,
        })
        return context

