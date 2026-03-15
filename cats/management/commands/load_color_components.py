from django.core.management.base import BaseCommand
from cats.models import ColorComponent, ColorComponentType


COLOR_COMPONENTS = [

    # ================= BASE COLORS =================
    ("n", {"ru": "чёрный", "de": "schwarz", "en": "black"}, 10, "BASE"),
    ("a", {"ru": "голубой", "de": "blau", "en": "blue"}, 10, "BASE"),
    ("b", {"ru": "шоколадный", "de": "schokolade", "en": "chocolate"}, 10, "BASE"),
    ("c", {"ru": "лиловый", "de": "lilac", "en": "lilac"}, 10, "BASE"),
    ("d", {"ru": "красный", "de": "rot", "en": "red"}, 10, "BASE"),
    ("e", {"ru": "кремовый", "de": "creme", "en": "cream"}, 10, "BASE"),
    ("f", {"ru": "чёрный черепаховый", "de": "schildpatt schwarz", "en": "black tortie"}, 10, "BASE"),
    ("g", {"ru": "голубой черепаховый", "de": "schildpatt blau", "en": "blue tortie"}, 10, "BASE"),
    ("h", {"ru": "шоколадный черепаховый", "de": "schildpatt schokolade", "en": "chocolate tortie"}, 10, "BASE"),
    ("j", {"ru": "лиловый черепаховый", "de": "schildpatt lilac", "en": "lilac tortie"}, 10, "BASE"),
    ("o", {"ru": "циннамон", "de": "zimt", "en": "cinnamon"}, 10, "BASE"),
    ("p", {"ru": "фавн", "de": "fawn", "en": "fawn"}, 10, "BASE"),
    ("q", {"ru": "циннамон черепаховый", "de": "schildpatt zimt", "en": "cinnamon tortie"}, 10, "BASE"),
    ("r", {"ru": "фавн черепаховый", "de": "schildpatt fawn", "en": "fawn tortie"}, 10, "BASE"),
    ("w", {"ru": "белый", "de": "weiß", "en": "white"}, 10, "BASE"),

    # Норвежские янтарные
    ("nt", {"ru": "янтарный", "de": "amber", "en": "amber"}, 20, "BASE"),
    ("at", {"ru": "светлый янтарный", "de": "light amber", "en": "light amber"}, 20, "BASE"),
    ("ft", {"ru": "янтарный черепаховый", "de": "amber tortie", "en": "amber tortie"}, 20, "BASE"),
    ("gt", {"ru": "светлый янтарный черепаховый", "de": "light amber tortie", "en": "light amber tortie"}, 20, "BASE"),

    # ================= SILVER / GOLD =================
    ("s", {"ru": "серебро", "de": "silber", "en": "silver"}, 30, "SILVER"),
    ("y", {"ru": "золото", "de": "gold", "en": "gold"}, 30, "SILVER"),

    # ================= DILUTE MODIFIER (CARAMEL) =================
    ("am", {"ru": "карамель голубой", "de": "karamel blau", "en": "blue caramel"}, 40, "MOD"),
    ("cm", {"ru": "карамель лиловый", "de": "karamel lilac", "en": "lilac caramel"}, 40, "MOD"),
    ("em", {"ru": "абрикосовый", "de": "apricot", "en": "apricot"}, 40, "MOD"),
    ("pm", {"ru": "карамель фавн", "de": "karamel fawn", "en": "fawn caramel"}, 40, "MOD"),
    ("gm", {"ru": "голубой карамель черепаховый", "de": "karamel tortie blau", "en": "blue caramel tortie"}, 40, "MOD"),

    # ================= WHITE AMOUNT =================
    ("01", {"ru": "ван", "de": "van", "en": "van"}, 50, "WHITE"),
    ("02", {"ru": "арлекин", "de": "harlekin", "en": "harlequin"}, 50, "WHITE"),
    ("03", {"ru": "биколор", "de": "bicolor", "en": "bicolour"}, 50, "WHITE"),
    ("04", {"ru": "миттед", "de": "mitted", "en": "mitted"}, 50, "WHITE"),
    ("05", {"ru": "сноу-шу", "de": "snowshoe", "en": "snowshoe"}, 50, "WHITE"),
    ("09", {"ru": "небольшое количество белого", "de": "wenig weiß", "en": "small amount of white"}, 50, "WHITE"),

    # ================= TABBY PATTERN =================
    ("11", {"ru": "затушеванный", "de": "shaded", "en": "shaded"}, 60, "TABBY"),
    ("12", {"ru": "шиншилла", "de": "shell", "en": "shell"}, 60, "TABBY"),
    ("21", {"ru": "табби без рисунка", "de": "tabby unspecified", "en": "unspecified tabby"}, 60, "TABBY"),
    ("22", {"ru": "мраморный табби", "de": "classic tabby", "en": "blotched tabby"}, 60, "TABBY"),
    ("23", {"ru": "тигровый табби", "de": "mackerel tabby", "en": "mackerel tabby"}, 60, "TABBY"),
    ("24", {"ru": "пятнистый табби", "de": "spotted tabby", "en": "spotted tabby"}, 60, "TABBY"),
    ("25", {"ru": "тикированный табби", "de": "ticked tabby", "en": "ticked tabby"}, 60, "TABBY"),

    # ================= POINTED =================
    ("31", {"ru": "бурманский пойнт", "de": "burmese pointed", "en": "Burmese pointed"}, 70, "POINT"),
    ("32", {"ru": "тонкинский пойнт", "de": "tonkinese pointed", "en": "Tonkinese pointed"}, 70, "POINT"),
    ("33", {"ru": "сиамский пойнт", "de": "siamese pointed", "en": "Siamese pointed"}, 70, "POINT"),

    # ================= TAIL =================
    ("51", {"ru": "без хвоста", "de": "rumpy", "en": "rumpy"}, 80, "TAIL"),
    ("52", {"ru": "короткий хвост", "de": "rumpy riser", "en": "rumpy riser"}, 80, "TAIL"),
    ("53", {"ru": "бобтейл", "de": "stumpy", "en": "stumpy"}, 80, "TAIL"),
    ("54", {"ru": "длинный хвост", "de": "longie", "en": "longie"}, 80, "TAIL"),

    # ================= EYES =================
    ("61", {"ru": "голубые глаза", "de": "blaue Augen", "en": "blue eyes"}, 90, "EYE"),
    ("62", {"ru": "оранжевые глаза", "de": "orange Augen", "en": "orange eyes"}, 90, "EYE"),
    ("63", {"ru": "разноглазие", "de": "odd-eyed", "en": "odd-eyed"}, 90, "EYE"),
    ("64", {"ru": "зеленые глаза", "de": "grüne Augen", "en": "green eyes"}, 90, "EYE"),
    ("65", {"ru": "бурманские глаза", "de": "burmese eyes", "en": "burmese eyes"}, 90, "EYE"),
    ("66", {"ru": "тонкинские глаза", "de": "tonkinese eyes", "en": "tonkinese eyes"}, 90, "EYE"),
    ("67", {"ru": "сиамские глаза", "de": "siamese eyes", "en": "siamese eyes"}, 90, "EYE"),

    # ================= EARS =================
    ("71", {"ru": "прямые уши", "de": "straight ears", "en": "straight ears"}, 100, "EAR"),
    ("72", {"ru": "завитые уши", "de": "curled ears", "en": "curled ears"}, 100, "EAR"),

    # ================= COAT =================
    ("81", {"ru": "длинная шерсть", "de": "langhaar", "en": "longhair"}, 110, "COAT"),
    ("82", {"ru": "короткая шерсть", "de": "kurzhaar", "en": "shorthair"}, 110, "COAT"),
    ("83", {"ru": "браш", "de": "brush", "en": "brush"}, 110, "COAT"),
]

class Command(BaseCommand):
    help = "Load EMS color components"

    def handle(self, *args, **options):

        for code, names, order, type_code in COLOR_COMPONENTS:

            type_obj = ColorComponentType.objects.get(code=type_code)

            obj, created = ColorComponent.objects.get_or_create(
                code=code,
                type=type_obj,
                defaults={"order": order}
            )

            for lang, text in names.items():
                obj.set_current_language(lang)
                obj.name = text

            obj.save()

        self.stdout.write(self.style.SUCCESS("Color components loaded"))
