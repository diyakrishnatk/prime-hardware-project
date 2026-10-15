
import os
import re
from pathlib import Path
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.http import HttpResponse, Http404

def serve_media(request, path):
    media_root = Path(settings.MEDIA_ROOT)
    
    # Strip any leading 'media/' or '/'
    clean_path = re.sub(r'^(media/)+', '', path.lstrip('/'))
    
    target = media_root / clean_path
    if not target.is_file():
        # Strip Cloudinary hash suffix like _e0blqf or _xdvnis
        base_name = re.sub(r'_[a-zA-Z0-9]{5,8}(\.[a-zA-Z0-9]+)?$', '', clean_path)
        parent_dir = media_root / Path(clean_path).parent
        if not parent_dir.is_dir():
            parent_dir = media_root / "images"
            
        target_stem = Path(base_name).stem.lower().replace(' ', '_').replace('-', '_')
        
        found = None
        if parent_dir.is_dir():
            for f in parent_dir.iterdir():
                if f.is_file():
                    f_stem = f.stem.lower().replace(' ', '_').replace('-', '_')
                    if f_stem == target_stem or f_stem.startswith(target_stem) or target_stem.startswith(f_stem):
                        found = f
                        break
        target = found

    if not target or not target.is_file():
        raise Http404(f"Media file not found: {path}")

    with open(target, 'rb') as f:
        head = f.read(32)
        f.seek(0)
        content = f.read()

    if head.startswith(b'RIFF') and b'WEBP' in head[:16]:
        content_type = 'image/webp'
    elif head.startswith(b'\xff\xd8\xff'):
        content_type = 'image/jpeg'
    elif head.startswith(b'\x89PNG\r\n\x1a\n'):
        content_type = 'image/png'
    elif b'<svg' in head.lower() or b'<?xml' in head.lower():
        content_type = 'image/svg+xml'
    elif head.startswith(b'GIF8'):
        content_type = 'image/gif'
    else:
        content_type = 'image/jpeg'

    response = HttpResponse(content, content_type=content_type)
    response["Cache-Control"] = "public, max-age=86400"
    return response

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('shop.urls')),
    re_path(r'^media/(?P<path>.*)$', serve_media),
]

