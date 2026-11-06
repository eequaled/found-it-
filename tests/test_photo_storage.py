import io
import os
from unittest.mock import AsyncMock

import pytest
from PIL import Image, PngImagePlugin

from app import storage
from app.errors import DomainError
from app.storage import PhotoStore, read_upload


def picture(kind="PNG", **options):
    stream = io.BytesIO()
    Image.new("RGB", (3, 2), "red").save(stream, kind, **options)
    return stream.getvalue()


@pytest.fixture
def store(tmp_path):
    return PhotoStore(tmp_path / "photos", 1024 * 1024)


@pytest.mark.parametrize("kind,suffix,mime", [
    ("JPEG", "jpg", "image/jpeg"), ("PNG", "png", "image/png"), ("WEBP", "webp", "image/webp"),
])
def test_store_decodes_and_canonicalizes_allowed_images(store, kind, suffix, mime):
    saved = store.save(picture(kind) + b"hidden trailing bytes")
    assert saved.key.endswith("." + suffix)
    assert saved.media_type == mime
    content, actual_mime = store.load(saved.key)
    assert actual_mime == mime and b"hidden trailing bytes" not in content
    with Image.open(io.BytesIO(content)) as image:
        image.load()
        assert image.format == kind and image.size == (3, 2)
    assert os.stat(store.root / saved.key).st_mode & 0o777 == 0o600
    assert len(list(store.root.iterdir())) == 1


@pytest.mark.parametrize("data", [b"", b"not a photo", b"\x89PNG\r\n\x1a\n", picture()[:40], picture("GIF")])
def test_invalid_images_create_no_file_or_directory(store, data):
    with pytest.raises(DomainError) as error:
        store.save(data)
    assert error.value.code == "invalid_photo" and error.value.status_code == 422
    assert not store.root.exists()


def test_input_and_normalized_output_are_both_size_bounded(tmp_path, monkeypatch):
    small = PhotoStore(tmp_path / "photos", 10)
    with pytest.raises(DomainError):
        small.save(picture())
    data = picture()
    # Simulate an encoder producing more than the accepted byte limit.
    original = Image.Image.save

    def expanded(image, output, *args, **kwargs):
        original(image, output, *args, **kwargs)
        output.write(b"x" * len(data))

    monkeypatch.setattr(Image.Image, "save", expanded)
    with pytest.raises(DomainError):
        PhotoStore(small.root, len(data)).save(data)
    assert not small.root.exists()


def test_reject_large_pixel_count_and_animation_before_storage(store, monkeypatch):
    monkeypatch.setattr(storage, "MAX_PIXELS", 5)
    with pytest.raises(DomainError):
        store.save(picture())
    monkeypatch.setattr(storage, "MAX_PIXELS", 16_000_000)
    output = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(
        output, "PNG", save_all=True, append_images=[Image.new("RGB", (2, 2), "blue")],
    )
    with pytest.raises(DomainError):
        store.save(output.getvalue())
    assert not store.root.exists()


def test_strip_metadata_and_apply_orientation(store):
    exif = Image.Exif()
    exif[270] = "private address"
    exif[274] = 6
    saved = store.save(picture("JPEG", exif=exif))
    with Image.open(io.BytesIO(store.load(saved.key)[0])) as image:
        assert image.size == (2, 3)
        assert not image.getexif()
    text = PngImagePlugin.PngInfo()
    text.add_text("location", "private address")
    saved = store.save(picture(pnginfo=text))
    with Image.open(io.BytesIO(store.load(saved.key)[0])) as image:
        assert "location" not in image.info


def test_preserve_png_transparency(store):
    output = io.BytesIO()
    Image.new("RGBA", (2, 2), (255, 0, 0, 0)).save(output, "PNG")
    saved = store.save(output.getvalue())
    with Image.open(io.BytesIO(store.load(saved.key)[0])) as image:
        assert image.getpixel((0, 0))[3] == 0


def test_concurrent_storage_keeps_distinct_complete_files(store):
    from concurrent.futures import ThreadPoolExecutor

    data = picture()
    with ThreadPoolExecutor(max_workers=4) as executor:
        saved = list(executor.map(store.save, [data] * 8))
    assert len({photo.key for photo in saved}) == 8
    assert len(list(store.root.iterdir())) == 8
    assert all(store.load(photo.key)[0] == store.load(saved[0].key)[0] for photo in saved)


def test_unique_names_and_idempotent_deletion(store):
    first, second = store.save(picture()), store.save(picture())
    assert first.key != second.key
    store.delete(first.key)
    store.delete(first.key)
    with pytest.raises(DomainError):
        store.load(first.key)
    assert store.load(second.key)[0]


@pytest.mark.parametrize("key", ["../secret", "/etc/passwd", "x.png", "a" * 32 + ".svg"])
def test_reject_unsafe_keys_without_accessing_files(store, key):
    with pytest.raises(DomainError):
        store.load(key)
    with pytest.raises(DomainError):
        store.delete(key)


def test_do_not_follow_symlinks_or_read_special_files(store, tmp_path):
    store.root.mkdir()
    secret = tmp_path / "secret"
    secret.write_text("private")
    key = "a" * 32 + ".png"
    (store.root / key).symlink_to(secret)
    with pytest.raises(DomainError):
        store.load(key)
    store.delete(key)
    assert secret.read_text() == "private"
    os.mkfifo(store.root / key)
    with pytest.raises(DomainError):
        store.load(key)


def test_failed_write_removes_only_new_file(store, monkeypatch):
    previous = store.save(picture())
    monkeypatch.setattr(storage.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("disk error")))
    with pytest.raises(OSError):
        store.save(picture())
    assert [path.name for path in store.root.iterdir()] == [previous.key]


def test_name_collision_never_overwrites_or_deletes_existing_file(store, monkeypatch):
    from types import SimpleNamespace

    saved = store.save(picture())
    before = store.load(saved.key)
    monkeypatch.setattr(storage, "uuid4", lambda: SimpleNamespace(hex=saved.key.split(".")[0]))
    with pytest.raises(FileExistsError):
        store.save(picture())
    assert store.load(saved.key) == before


@pytest.mark.parametrize("pixel_limit", [1, 4])
def test_pillow_bomb_errors_and_warnings_are_validation_failures(store, monkeypatch, pixel_limit):
    data = picture()
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", pixel_limit)
    with pytest.raises(DomainError) as error:
        store.save(data)
    assert error.value.status_code == 422
    assert not store.root.exists()


async def test_read_upload_probes_boundary_without_unbounded_reads():
    upload = AsyncMock()
    upload.read.side_effect = [b"123", b""]
    assert await read_upload(upload, 3) == b"123"
    assert [call.args[0] for call in upload.read.call_args_list] == [4, 1]
    upload.read.side_effect = [b"1234"]
    with pytest.raises(DomainError):
        await read_upload(upload, 3)
