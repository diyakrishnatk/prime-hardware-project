
import os
from pathlib import Path

import django
import cloudinary
import cloudinary.uploader

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "prime_hardware.settings")
django.setup()

from django.core.files import File
from shop.models import Product

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"],
    secure=True,
)

BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "media" / "images"

products = Product.objects.exclude(image="").exclude(image__isnull=True)

uploaded = 0
missing = 0

for product in products:
    stored_name = product.image.name
    local_path = IMAGE_DIR / Path(stored_name).name

    if not local_path.is_file():
        print(f"MISSING: {product.name} -> {local_path}")
        missing += 1
        continue

    try:
        with local_path.open("rb") as image_file:
            product.image.save(
                local_path.name,
                File(image_file),
                save=True,
            )

        print(f"UPLOADED: {product.name} -> {product.image.name}")
        uploaded += 1

    except Exception as exc:
        print(f"ERROR: {product.name}: {exc}")

print("\nUpload finished.")
print("Uploaded:", uploaded)
print("Missing local files:", missing)
