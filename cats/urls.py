from django.urls import path
from . import views

urlpatterns = [
    # MEDIA
    path("media/", views.my_media, name="my_media"),
    path("media/upload/", views.upload_media, name="upload_media"),
    path("media/delete/<int:pk>/", views.delete_media, name="delete_media"),

    # DOCUMENTS
    path("documents/", views.my_documents, name="my_documents"),
    path("documents/upload/", views.upload_document, name="upload_document"),

    # CATS
    path("cats/", views.cat_list, name="cat_list"),
    path("cats/<int:pk>/", views.cat_detail, name="cat_detail"),

    # ADMIN
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
]