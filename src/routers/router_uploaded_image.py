import io

import PIL.Image as PilImage
from fastapi import APIRouter, Depends, UploadFile, File
from src.services.email_service import send_email
from src.services.processing_files_service import UploadedImage

router = APIRouter()

@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    uploaded_image_service: UploadedImage = Depends(UploadedImage),
):  
    content = await file.read()
    filename = file.filename

    processed_path = await uploaded_image_service.check_and_change_format(filename, content)
    final_path = await uploaded_image_service.compress_image(processed_path)

    image = PilImage.open(final_path)
    image = image.convert("RGB")

    ext = processed_path.suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        fmt = "JPEG"
    elif ext == ".png":
        fmt = "PNG"
    elif ext == ".webp":
        fmt = "WEBP"
    elif ext == ".gif":
        fmt = "GIF"
    else:
        fmt = image.format or "PNG"

    output_bytes = io.BytesIO()
    image.save(output_bytes, format=fmt)
    output_bytes = output_bytes.getvalue()

    send_email(
        to="test@test.com",
        subject="New image uploaded",
        body="Файл загружен и обработан",
        attachments=[{
            "filename": f"{final_path.stem}.{fmt.lower()}",
            "content": output_bytes,
            "mime_type": f"image/{fmt.lower()}"
        }]
    )

    return {"info": f"file '{file.filename}' saved at '{final_path}'"}