from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.views.generic import DetailView, ListView
from django.http import HttpResponseForbidden
from django.contrib.admin.views.decorators import staff_member_required
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


def upload_cat_photo(request, pk):
    if not request.user.is_staff:
        return HttpResponseForbidden("Недостаточно прав")

    cat = get_object_or_404(Cat, pk=pk)

    if request.method == "POST":
        file = request.FILES.get("file")

        if file:
            media = MediaFile.objects.create(
                file=file,
                owner=request.user if request.user.is_authenticated else None,
                media_type=MediaFile.MediaType.PHOTO,
                title=cat.registered_name,
            )

            MediaLink.objects.create(
                file=media,
                content_object=cat,
                role="photo",
            )

        return redirect("cat_gallery", pk=cat.pk)

    return render(request, "cat_upload.html", {"cat": cat})


def delete_cat_photo(request, cat_pk, photo_pk):
    if not request.user.is_staff:
        return HttpResponseForbidden("Недостаточно прав")

    cat = get_object_or_404(Cat, pk=cat_pk)

    photo_link = get_object_or_404(
        MediaLink.objects.select_related("file"),
        pk=photo_pk,
        object_id=cat.pk,
        content_type=ContentType.objects.get_for_model(Cat),
    )

    media_file = photo_link.file

    if request.method == "POST":
        if media_file.file:
            media_file.file.delete(save=False)

        media_file.delete()
        return redirect("cat_gallery", pk=cat.pk)

    return redirect("cat_gallery", pk=cat.pk)


class CatGalleryView(DetailView):
    model = Cat
    template_name = "cat_gallery.html"
    context_object_name = "cat"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_type = ContentType.objects.get_for_model(Cat)

        context["photos"] = (
            MediaLink.objects
            .filter(
                content_type=content_type,
                object_id=self.object.pk,
                role="photo"
            )
            .select_related("file")
            .order_by("-file__uploaded_at")
        )
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
    content_type = ContentType.objects.get_for_model(Cat)

    MediaLink.objects.filter(
        content_type=content_type,
        object_id=cat.pk,
        role="photo"
    ).update(is_primary=False)

    photo = get_object_or_404(
        MediaLink,
        pk=photo_pk,
        content_type=content_type,
        object_id=cat.pk,
        role="photo"
    )

    photo.is_primary = True
    photo.save()

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
