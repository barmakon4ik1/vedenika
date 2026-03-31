from django.urls import path
from . import views
from .views import *

urlpatterns = [
    path("", views.home, name="home"),
    # path("", HomeView.as_view(), name="home"),

    # MEDIA
    path("media/", views.my_media, name="my_media"),
    path("media/upload/", views.upload_media, name="upload_media"),
    path("media/delete/<int:pk>/", views.delete_media, name="delete_media"),

    # DOCUMENTS
    path("documents/", views.my_documents, name="my_documents"),
    path("documents/upload/", views.upload_document, name="upload_document"),

    # CATS
    path("cats/", CatListView.as_view(), name="cat_list"),
    path("cats/add/", cat_create, name="cat_add"),
    path("cats/<int:pk>/", CatDetailView.as_view(), name="cat_detail"),
    path("cats/<int:pk>/gallery/", CatGalleryView.as_view(), name="cat_gallery"),
    path("cats/<int:pk>/upload-photo/", upload_cat_photo, name="cat_upload_photo"),
    path("cats/<int:cat_pk>/photo/<int:photo_pk>/delete/", delete_cat_photo, name="delete_cat_photo"),

    # ADMIN
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
]