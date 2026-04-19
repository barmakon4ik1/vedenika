from django.urls import path
from . import views
from .views import *

urlpatterns = [
    path("", views.home, name="home"),
    # path("", HomeView.as_view(), name="home"),

    # # MEDIA
    # path("media/", views.my_media, name="my_media"),
    # path("media/upload/", views.upload_media, name="upload_media"),
    # path("media/delete/<int:pk>/", views.delete_media, name="delete_media"),

    # # DOCUMENTS
    # path("documents/", views.my_documents, name="my_documents"),
    # path("documents/upload/", views.upload_document, name="upload_document"),

    # CATS
    path("cats/", CatListView.as_view(), name="cat_list"),
    path("cats/add/", cat_create, name="cat_add"),
    path("cats/<int:pk>/edit/", cat_update, name="cat_edit"),
    path("cats/<int:pk>/", CatDetailView.as_view(), name="cat_detail"),
    path("cats/<int:pk>/gallery/", CatGalleryView.as_view(), name="cat_gallery"),
    path("cats/<int:pk>/upload-photo/", upload_cat_photo, name="cat_upload_photo"),
    path("cats/<int:cat_pk>/photo/<int:photo_pk>/delete/", delete_cat_photo, name="delete_cat_photo"),
    path("cats/<int:cat_pk>/photo/<int:photo_pk>/set-main/", set_main_photo, name="set_main_photo"),
    path("cats/<int:cat_pk>/color/add/", color_create_for_cat, name="color_create_for_cat"),
    path("cats/<int:cat_pk>/color/edit/", color_update_for_cat, name="color_update_for_cat"),

    # LITTERS
    path("litters/", LitterListView.as_view(), name="litter_list"),
    path("litters/<int:pk>/", LitterDetailView.as_view(), name="litter_detail"),

    # # ADMIN
    # path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),

    # Impressum
    path("impressum/", views.impressum, name="impressum"),

    # GALLERY
    path("gallery/", GalleryListView.as_view(), name="gallery_list"),
    path("gallery/<int:pk>/", GalleryAlbumView.as_view(), name="gallery_album"),

    # VIDEO
    path("video/", VideoListView.as_view(), name="video_list"),

    # VIDEO CRUD (только для staff)
    path("video/manage/", views.video_manage, name="video_manage"),
    path("video/create/", views.video_create, name="video_create"),
    path("video/<int:pk>/edit/", views.video_edit, name="video_edit"),
    path("video/<int:pk>/delete/", views.video_delete, name="video_delete"),

    # CONTACTS
    path("contacts/", views.contacts, name="contacts"),

    # GALLERY CRUD (только для staff)
    path("gallery/manage/", views.gallery_manage, name="gallery_manage"),
    path("gallery/create/", views.gallery_album_create, name="gallery_album_create"),
    path("gallery/<int:pk>/edit/", views.gallery_album_edit, name="gallery_album_edit"),
    path("gallery/<int:pk>/delete/", views.gallery_album_delete, name="gallery_album_delete"),
    path("gallery/<int:pk>/photos/", views.gallery_album_photos, name="gallery_album_photos"),
    path("gallery/<int:album_pk>/upload/", views.gallery_photo_upload, name="gallery_photo_upload"),
    path("gallery/photo/<int:pk>/edit/", views.gallery_photo_edit, name="gallery_photo_edit"),
    path("gallery/photo/<int:pk>/delete/", views.gallery_photo_delete, name="gallery_photo_delete"),
    path("gallery/<int:album_pk>/reorder/", views.gallery_photo_reorder, name="gallery_photo_reorder"),

    # Авторизация
    path('profile/',      views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
]