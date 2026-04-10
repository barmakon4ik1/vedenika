from django.db import migrations, models
import django.db.models.deletion


def copy_galleryphoto_title_to_translation(apps, schema_editor):
    GalleryPhoto = apps.get_model("cats", "GalleryPhoto")
    GalleryPhotoTranslation = apps.get_model("cats", "GalleryPhotoTranslation")

    db_alias = schema_editor.connection.alias

    for photo in GalleryPhoto.objects.using(db_alias).all():
        title = getattr(photo, "title", "") or ""
        GalleryPhotoTranslation.objects.using(db_alias).get_or_create(
            master_id=photo.pk,
            language_code="ru",
            defaults={
                "title": title,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("cats", "0012_forumcategory_forumtopic_forumpost"),
    ]

    operations = [
        migrations.CreateModel(
            name="GalleryPhotoTranslation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "language_code",
                    models.CharField(
                        db_index=True,
                        max_length=15,
                        verbose_name="Language",
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        blank=True,
                        max_length=200,
                        verbose_name="Подпись",
                    ),
                ),
                (
                    "master",
                    models.ForeignKey(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="translations",
                        to="cats.galleryphoto",
                    ),
                ),
            ],
            options={
                "db_table": "cats_galleryphoto_translation",
                "managed": True,
                "default_permissions": (),
                "unique_together": {("language_code", "master")},
                "verbose_name": "Фото галереи Translation",
            },
        ),
        migrations.RunPython(
            copy_galleryphoto_title_to_translation,
            migrations.RunPython.noop,
        ),
    ]