from PIL import Image
from pathlib import Path

unsuported_formats = [
    "BMP", "TIFF", "TIF", "HEIC", "HEIF", "ICO",
    "PNM", "PPM", "PGM", "PBM", "XBM", "XPM",
    "DDS", "WBMP"
    ]
suported_formats = ["JPEG", "JPG", "PNG", "GIF", "WEBP"]

UPLOAD_DIR = Path("uploads/")
UPLOAD_DIR.mkdir(exist_ok=True)


class UploadedImage():


    async def check_and_change_format(self, filename: str, content: bytes) -> Path:
        
        stem = Path(filename).stem
        original_path = UPLOAD_DIR / filename

        with open(original_path, "wb") as f:
            f.write(content)

        try:
            image = Image.open(original_path)

        except Exception as e:
            original_path.unlink(missing_ok=True)
            raise ValueError("Uploaded file is not a valid image.") from e

        if image.format in unsuported_formats:
            image_mode = image.mode

            if image_mode in ["RGBA", "P"]:
                new_filepath = UPLOAD_DIR / f"{stem}.png"
                image.save(new_filepath, format="PNG", compress_level=5)

            elif image_mode in ["RGB", "L"]:
                new_filepath = UPLOAD_DIR / f"{stem}.jpeg"
                image.save(new_filepath, format="JPEG", quality=90)
            
            original_path.unlink(missing_ok=True)

            return new_filepath
        
        else:
            return UPLOAD_DIR / filename

    async def compress_image(self, processed_path: Path) -> Path:

        image_size_bytes = processed_path.stat().st_size
        if image_size_bytes <= 2_048_000:
            return processed_path
        
        image = Image.open(processed_path)

        if image.format in suported_formats and image_size_bytes > 2_048_000:

            if image.format == "PNG":
                quantize_image = image.quantize(colors=256)
                quantize_image.save(processed_path, format="PNG", compress_level=9)

            elif image.format == "JPEG":
                need_to_compress = image_size_bytes - 2_048_000

                quality = int(90 - (need_to_compress / image_size_bytes) * 90)
                if quality < 70:
                    quality = 70
                image.save(processed_path, format="JPEG", quality=quality)

            elif image.format == "WEBP":
                need_to_compress = image_size_bytes - 2_048_000
                quality = int(90 - (need_to_compress / image_size_bytes) * 90)
                if quality < 70:
                    quality = 70
                image.save(processed_path, format="WEBP", quality=quality)

            elif image.format == "GIF":
                quantize_image = image.quantize(colors=256)
                quantize_image.save(processed_path, format="GIF", optimize=True)
            else:
                raise ValueError("Unsupported image format for compression.")

class DocumentFile:
    pass

