from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from .models import MediaFile, Document, Cat, MediaLink
from django.views.generic import DetailView, ListView
from django.http import HttpResponseForbidden
from django.contrib.admin.views.decorators import staff_member_required
from .forms import CatForm

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

    def get_queryset(self):
        return (
            Cat.objects
            .select_related("breed", "cattery", "cat_color")
            .prefetch_related("cat_color__components")
            .order_by("registered_name")
        )


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

    return render(request, "cat_form.html", {"form": form, "page_title": "Добавить кота"})