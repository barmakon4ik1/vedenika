from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.views.generic import DetailView, ListView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from .forms import *
from .models import *
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

owner_id = settings.CATTERY_OWNER_PERSON_ID

User = get_user_model()
OWNER_PERSON_ID = 1
HOME_RANDOM_PHOTO_COUNT = 24

def impressum(request):
    owner = Person.objects.select_related("address__city", "address__country").filter(
        pk=OWNER_PERSON_ID
    ).first()
    return render(request, "impressum.html", {"owner": owner})

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

# @login_required
# def my_documents(request):
#     docs = Document.objects.filter(owner=request.user)
#     return render(request, "my_documents.html", {"documents": docs})
#
#
# @login_required
# def upload_document(request):
#     if request.method == "POST":
#         file_id = request.POST.get("file_id")
#         file = get_object_or_404(MediaFile, id=file_id)
#
#         if not owner_required(file, request.user):
#             raise PermissionDenied()
#
#         Document.objects.create(
#             file=file,
#             owner=request.user,
#             title=request.POST.get("title", "")
#         )
#
#         return redirect("my_documents")
#
#     media = MediaFile.objects.filter(owner=request.user)
#     return render(request, "upload_document.html", {"media": media})


# =========================================================
# 🐱 CATS (публичные)
# =========================================================

def cat_list(request):
    cats = Cat.objects.filter(is_active=True)
    return render(request, "cat_list.html", {"cats": cats})


# =========================================================
# 🛠 ADMIN (если нужен вне admin)
# =========================================================

# @user_passes_test(is_admin)
# def admin_dashboard(request):
#     return render(request, "admin_dashboard.html")



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
    from .models import GalleryPhoto, Cat
    import random

    photo_ids = list(
        GalleryPhoto.objects.filter(
            is_active=True,
            album__is_active=True
        ).values_list("id", flat=True)
    )

    random_photos = []
    if photo_ids:
        photo_count = min(HOME_RANDOM_PHOTO_COUNT, len(photo_ids))
        sample_ids = random.sample(photo_ids, photo_count)
        random_photos = list(
            GalleryPhoto.objects.filter(id__in=sample_ids).select_related("album")
        )

    belt_photos = list(
        GalleryPhoto.objects.filter(
            is_active=True,
            album__is_active=True,
            album_id=3
        ).select_related("album")
    )

    featured_cats = list(
        Cat.objects.filter(is_active=True, is_featured=True)
        .select_related("cat_color", "breed")
        .prefetch_related("photos")
        .order_by("?")[:4]
    )

    return render(request, "home.html", {
        "random_photos": random_photos,
        "belt_photos": belt_photos,
        "featured_cats": featured_cats,
    })


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
                # is_active=True,
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

        # Разделяем на активных и неактивных
        cats = context["cats"]
        context["cats_active"] = [c for c in cats if c.is_active]
        context["cats_inactive"] = [c for c in cats if not c.is_active]

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

            # Помёт считается активным, пока галочка стоит
            is_active = litter.is_active

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


# =========================================================
# 🖼 GALLERY
# =========================================================

class GalleryListView(ListView):
    model = GalleryAlbum
    template_name = "gallery_list.html"
    context_object_name = "albums"

    def get_queryset(self):
        return (
            GalleryAlbum.objects
            .filter(is_active=True)
            .prefetch_related("photos")
            .order_by("-date", "-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        albums = context["albums"]

        # Разбиваем по категориям
        context["albums_life"]   = [a for a in albums if a.category == "LIFE"]
        context["albums_litter"] = [a for a in albums if a.category == "LITTER"]
        context["albums_art"]    = [a for a in albums if a.category == "ART"]

        # Текущий фильтр
        context["selected_category"] = self.request.GET.get("category", "")
        return context


class GalleryAlbumView(DetailView):
    model = GalleryAlbum
    template_name = "gallery_album.html"
    context_object_name = "album"

    def get_queryset(self):
        return GalleryAlbum.objects.filter(is_active=True).prefetch_related(
            "photos"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["photos"] = self.object.photos.filter(
            is_active=True
        ).order_by("sort_order", "-uploaded_at")
        return context


# =========================================================
# 🎬 VIDEO
# =========================================================

class VideoListView(ListView):
    model = Video
    template_name = "video_list.html"
    context_object_name = "videos"

    def get_queryset(self):
        return Video.objects.filter(is_active=True).order_by("-date", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        videos = context["videos"]
        context["videos_life"]   = [v for v in videos if v.category == "LIFE"]
        context["videos_litter"] = [v for v in videos if v.category == "LITTER"]
        context["videos_other"]  = [v for v in videos if v.category == "OTHER"]
        return context


# =========================================================
# 🐱 О ПОРОДЕ
# =========================================================

def about_breed(request):
    return render(request, "about_breed.html")


# =========================================================
# 📬 КОНТАКТЫ
# =========================================================

def contacts(request):
    return render(request, "contacts.html")


# =========================================================
# АЛЬБОМЫ / CRUD
# =========================================================
# ---- Список альбомов (для управления, только staff) ----

@staff_member_required
def gallery_manage(request):
    """Страница управления галереей для администратора."""
    albums = GalleryAlbum.objects.prefetch_related("photos").order_by("-date", "-created_at")
    return render(request, "gallery_manage.html", {"albums": albums})


# ---- Создать альбом ----

@staff_member_required
def gallery_album_create(request):
    if request.method == "POST":
        form = GalleryAlbumForm(request.POST, request.FILES)
        if form.is_valid():
            album = form.save()
            return redirect("gallery_album_photos", pk=album.pk)
    else:
        form = GalleryAlbumForm()

    return render(request, "gallery_album_form.html", {
        "form": form,
        "page_title": "Создать альбом",
        "is_edit": False,
    })


# ---- Редактировать альбом ----

@staff_member_required
def gallery_album_edit(request, pk):
    album = get_object_or_404(GalleryAlbum, pk=pk)

    if request.method == "POST":
        form = GalleryAlbumForm(request.POST, request.FILES, instance=album)
        if form.is_valid():
            form.save()
            return redirect("gallery_album_photos", pk=album.pk)
    else:
        form = GalleryAlbumForm(instance=album)

    return render(request, "gallery_album_form.html", {
        "form": form,
        "album": album,
        "page_title": f"Редактировать: {album.safe_translation_getter('title', any_language=True)}",
        "is_edit": True,
    })


# ---- Удалить альбом ----

@staff_member_required
def gallery_album_delete(request, pk):
    album = get_object_or_404(GalleryAlbum, pk=pk)
    if request.method == "POST":
        # Удаляем файлы фото
        for photo in album.photos.all():
            if photo.image:
                photo.image.delete(save=False)
        # Удаляем обложку
        if album.cover:
            album.cover.delete(save=False)
        album.delete()
        return redirect("gallery_manage")

    return render(request, "gallery_album_confirm_delete.html", {"album": album})


# ---- Фото альбома — просмотр и управление ----

@staff_member_required
def gallery_album_photos(request, pk):
    album = get_object_or_404(GalleryAlbum, pk=pk)
    photos = album.photos.order_by("sort_order", "-uploaded_at")
    return render(request, "gallery_album_photos.html", {
        "album": album,
        "photos": photos,
    })


# ---- Загрузить фото в альбом ----

@staff_member_required
def gallery_photo_upload(request, album_pk):
    album = get_object_or_404(GalleryAlbum, pk=album_pk)

    album_title = album.safe_translation_getter("title", any_language=True)

    if request.method == "POST":
        files = request.FILES.getlist("images")  # множественная загрузка
        saved = 0
        for f in files:
            GalleryPhoto.objects.create(
                album=album,
                image=f,
                is_active=True,
            )
            saved += 1

        if saved:
            return redirect("gallery_album_photos", pk=album.pk)

    return render(
        request,
        "gallery_photo_upload.html",
        {
            "album": album,
            "album_title": album_title,  # 👉 передаём в шаблон
        },
    )

# ---- Редактировать одно фото ----

@staff_member_required
def gallery_photo_edit(request, pk):
    photo = get_object_or_404(GalleryPhoto, pk=pk)
    album = photo.album

    album_title = album.safe_translation_getter("title", any_language=True)

    if request.method == "POST":
        form = GalleryPhotoForm(request.POST, request.FILES, instance=photo)
        if form.is_valid():
            form.save()
            return redirect("gallery_album_photos", pk=album.pk)
    else:
        form = GalleryPhotoForm(instance=photo)

    return render(
        request,
        "gallery_photo_form.html",
        {
            "form": form,
            "photo": photo,
            "album": album,
            "album_title": album_title,
        },
    )


# ---- Удалить фото ----

@staff_member_required
def gallery_photo_delete(request, pk):
    photo = get_object_or_404(GalleryPhoto, pk=pk)
    album_pk = photo.album_id

    if request.method == "POST":
        if photo.image:
            photo.image.delete(save=False)
        photo.delete()
        return redirect("gallery_album_photos", pk=album_pk)

    return render(request, "gallery_photo_confirm_delete.html", {
        "photo": photo,
        "album": photo.album,
    })


# ---- Изменить порядок фото (AJAX) ----

@staff_member_required
@require_POST
def gallery_photo_reorder(request, album_pk):
    """
    Принимает JSON: {"order": [id1, id2, id3, ...]}
    Обновляет sort_order для каждого фото.
    """
    try:
        data = json.loads(request.body)
        order = data.get("order", [])
        for index, photo_id in enumerate(order):
            GalleryPhoto.objects.filter(pk=photo_id, album_id=album_pk).update(
                sort_order=index
            )
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


# ---- Список видео (управление) ----

@staff_member_required
def video_manage(request):
    videos = Video.objects.order_by("-date", "-created_at")
    return render(request, "video_manage.html", {"videos": videos})


# ---- Создать видео ----

@staff_member_required
def video_create(request):
    if request.method == "POST":
        form = VideoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("video_manage")
    else:
        form = VideoForm()

    return render(request, "video_form.html", {
        "form": form,
        "page_title": "Добавить видео",
        "is_edit": False,
    })


# ---- Редактировать видео ----

@staff_member_required
def video_edit(request, pk):
    video = get_object_or_404(Video, pk=pk)

    if request.method == "POST":
        form = VideoForm(request.POST, request.FILES, instance=video)
        if form.is_valid():
            form.save()
            return redirect("video_manage")
    else:
        form = VideoForm(instance=video)

    return render(request, "video_form.html", {
        "form": form,
        "video": video,
        "page_title": f"Редактировать: {video.safe_translation_getter('title', any_language=True)}",
        "is_edit": True,
    })


# ---- Удалить видео ----

@staff_member_required
def video_delete(request, pk):
    video = get_object_or_404(Video, pk=pk)

    if request.method == "POST":
        if video.video_file:
            video.video_file.delete(save=False)
        if video.thumbnail:
            video.thumbnail.delete(save=False)
        video.delete()
        return redirect("video_manage")

    return render(request, "video_confirm_delete.html", {"video": video})


@login_required
def profile_view(request):
    """Страница профиля текущего пользователя."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'profile.html', {'profile': profile})


@login_required
def profile_edit(request):
    """Редактирование профиля."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'profile_edit.html', {'form': form, 'profile': profile})


def forum_index(request):
    """Главная страница форума — список разделов."""
    categories = ForumCategory.objects.filter(is_active=True).prefetch_related(
        'topics__posts'
    )
    return render(request, 'forum_index.html', {'categories': categories})


def forum_category(request, category_slug):
    """Список тем в разделе."""
    category = get_object_or_404(ForumCategory, slug=category_slug, is_active=True)
    topics = (
        ForumTopic.objects
        .filter(category=category, is_active=True)
        .select_related('author', 'author__profile')
        .prefetch_related('posts')
        .order_by('-is_pinned', '-created_at')
    )
    return render(request, 'forum_category.html', {
        'category': category,
        'topics':   topics,
    })


def forum_topic(request, category_slug, topic_slug):
    """Тема с постами + форма ответа."""
    category = get_object_or_404(ForumCategory, slug=category_slug, is_active=True)
    topic    = get_object_or_404(ForumTopic, slug=topic_slug, category=category, is_active=True)

    # Считаем просмотры
    ForumTopic.objects.filter(pk=topic.pk).update(views_count=models.F('views_count') + 1)

    posts = topic.posts.filter(is_active=True).select_related(
        'author', 'author__profile'
    )

    form = None
    if request.user.is_authenticated:
        if request.method == 'POST':
            form = ForumPostForm(request.POST)
            if form.is_valid():
                post = form.save(commit=False)
                post.topic  = topic
                post.author = request.user
                post.save()
                return redirect(f'{topic.get_absolute_url()}#post-{post.pk}')
        else:
            form = ForumPostForm()

    return render(request, 'forum_topic.html', {
        'category': category,
        'topic':    topic,
        'posts':    posts,
        'form':     form,
    })


@login_required
def forum_topic_create(request, category_slug):
    """Создать новую тему."""
    category = get_object_or_404(ForumCategory, slug=category_slug, is_active=True)

    if request.method == 'POST':
        form = ForumTopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.category = category
            topic.author   = request.user
            topic.save()
            return redirect(topic.get_absolute_url())
    else:
        form = ForumTopicForm()

    return render(request, 'forum_topic_form.html', {
        'form':      form,
        'category':  category,
        'page_title': f'Новая тема в «{category.name}»',
    })


@login_required
def forum_post_edit(request, post_pk):
    """Редактировать своё сообщение."""
    post = get_object_or_404(ForumPost, pk=post_pk, is_active=True)

    # Только автор или staff
    if post.author != request.user and not request.user.is_staff:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if request.method == 'POST':
        form = ForumPostForm(request.POST, instance=post)
        if form.is_valid():
            p = form.save(commit=False)
            p.is_edited = True
            p.edited_at = timezone.now()
            p.save()
            return redirect(f'{post.topic.get_absolute_url()}#post-{post.pk}')
    else:
        form = ForumPostForm(instance=post)

    return render(request, 'forum_post_edit.html', {
        'form': form,
        'post': post,
    })


@login_required
def forum_post_delete(request, post_pk):
    """Удалить сообщение (только staff или автор)."""
    post = get_object_or_404(ForumPost, pk=post_pk, is_active=True)

    if post.author != request.user and not request.user.is_staff:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    topic_url = post.topic.get_absolute_url()

    if request.method == 'POST':
        post.is_active = False  # soft delete
        post.save()
        return redirect(topic_url)

    return render(request, 'forum_post_confirm_delete.html', {'post': post})


@login_required
def forum_topic_delete(request, topic_pk):
    """Удалить тему (только staff)."""
    if not request.user.is_staff:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    topic = get_object_or_404(ForumTopic, pk=topic_pk)
    category_slug = topic.category.slug

    if request.method == 'POST':
        topic.is_active = False  # soft delete
        topic.save()
        return redirect('forum_category', category_slug=category_slug)

    return render(request, 'forum_topic_confirm_delete.html', {'topic': topic})


def forum_rules(request):
    return render(request, 'forum_rules.html')