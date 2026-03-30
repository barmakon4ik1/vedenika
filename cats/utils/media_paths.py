def upload_cat_image(instance, filename):
    return f"images/cats/{instance.id or 'tmp'}/{filename}"


def upload_document(instance, filename):
    return f"documents/{filename}"


def upload_pedigree(instance, filename):
    return f"pedigrees/{filename}"


def upload_contract(instance, filename):
    return f"contracts/{filename}"


def upload_generic(instance, filename):
    return f"uploads/{filename}"

def upload_to_cat(instance, filename):
    return f"images/cats/{instance.cat.id}/{filename}"

def upload_to_media(instance, filename):
    model_name = instance.__class__.__name__.lower()
    return f"uploads/{model_name}/{filename}"