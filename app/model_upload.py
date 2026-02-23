from fastapi import APIRouter, Request, UploadFile, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.models import Model3D
from app.database import get_db
from app.model_storage import process_and_upload_glb, read_storage_config

router = APIRouter()

@router.post("/admin/3d-block/settings/upload-model")
def upload_model(
    request: Request,
    name: str = Form(...),
    glb_file: UploadFile = Form(...),
    db: Session = Depends(get_db),
):
    file_bytes = glb_file.file.read()
    try:
        storage_config = read_storage_config(db)
        url, size, _ = process_and_upload_glb(glb_file.filename or "", file_bytes, storage_config=storage_config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    db.add(Model3D(name=name, url=url, size=size))
    db.commit()
    return RedirectResponse("/admin/3d-block/settings", status_code=303)

@router.post("/admin/3d-block/settings/delete-model")
def delete_model(request: Request, id: int = Form(...), db: Session = Depends(get_db)):
    model = db.query(Model3D).filter(Model3D.id == id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    # Remove from S3 (parse key from URL)
    s3_key = model.url.replace("https://", "", 1).split("/", 1)[-1]
    try:
        storage_config = read_storage_config(db)
        import boto3
        boto3.client(
            "s3",
            aws_access_key_id=storage_config.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=storage_config.get("AWS_SECRET_ACCESS_KEY"),
            region_name=storage_config.get("AWS_REGION", "ap-south-1"),
        ).delete_object(Bucket=storage_config.get("S3_BUCKET"), Key=s3_key)
    except Exception:
        pass  # Ignore S3 errors for now
    db.delete(model)
    db.commit()
    return RedirectResponse("/admin/3d-block/settings", status_code=303)
