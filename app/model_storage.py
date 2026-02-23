import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import boto3
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.models import SecurityManagedSetting

load_dotenv()

STORAGE_FEATURE_ID = "3d-model-storage"
STORAGE_KEYS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION",
    "S3_BUCKET",
    "CLOUDFRONT_DOMAIN",
)
DEFAULT_STORAGE_CONFIG = {
    "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", ""),
    "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
    "AWS_REGION": os.getenv("AWS_REGION", "ap-south-1"),
    "S3_BUCKET": os.getenv("S3_BUCKET", "model3dcnd"),
    "CLOUDFRONT_DOMAIN": os.getenv("CLOUDFRONT_DOMAIN", "d2sq08n1my8atm.cloudfront.net"),
}


def read_storage_config(db: Session) -> dict[str, str]:
    config = dict(DEFAULT_STORAGE_CONFIG)
    rows = (
        db.query(SecurityManagedSetting)
        .filter(SecurityManagedSetting.feature_id == STORAGE_FEATURE_ID)
        .all()
    )
    for row in rows:
        if row.key in STORAGE_KEYS and (row.value or "").strip():
            config[row.key] = row.value.strip()
    config["CLOUDFRONT_DOMAIN"] = config["CLOUDFRONT_DOMAIN"].strip().replace("https://", "").strip("/")
    return config


def upsert_storage_config(db: Session, config: dict[str, str]) -> None:
    for key in STORAGE_KEYS:
        value = (config.get(key) or "").strip()
        row = (
            db.query(SecurityManagedSetting)
            .filter(
                SecurityManagedSetting.feature_id == STORAGE_FEATURE_ID,
                SecurityManagedSetting.key == key,
            )
            .first()
        )
        if row:
            row.value = value
        else:
            db.add(SecurityManagedSetting(feature_id=STORAGE_FEATURE_ID, key=key, value=value))


def _s3_client(config: dict[str, str]):
    return boto3.client(
        "s3",
        aws_access_key_id=config.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=config.get("AWS_SECRET_ACCESS_KEY"),
        region_name=config.get("AWS_REGION") or "ap-south-1",
    )


def compress_glb_with_draco(input_path: Path, output_path: Path) -> None:
    gltf_cli = shutil.which("gltf-transform")
    if gltf_cli:
        cmd = [
            gltf_cli,
            "draco",
            str(input_path),
            str(output_path),
        ]
    else:
        npx_cli = shutil.which("npx")
        if not npx_cli:
            raise RuntimeError(
                "gltf-transform CLI not found. Install Node.js and run: npm install -g @gltf-transform/cli"
            )
        cmd = [
            npx_cli,
            "-y",
            "@gltf-transform/cli",
            "draco",
            str(input_path),
            str(output_path),
        ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "gltf-transform CLI not found. Install Node.js and run: npm install -g @gltf-transform/cli"
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"GLB compression failed: {details}") from exc


def process_and_upload_glb(
    filename: str,
    file_bytes: bytes,
    *,
    storage_config: dict[str, Any],
) -> tuple[str, int, str]:
    if not filename or not filename.lower().endswith(".glb"):
        raise ValueError("Only .glb files are supported")
    if not file_bytes:
        raise ValueError("Uploaded GLB file is empty")
    if not (storage_config.get("S3_BUCKET") or "").strip():
        raise RuntimeError("S3_BUCKET is not configured")
    if not (storage_config.get("CLOUDFRONT_DOMAIN") or "").strip():
        raise RuntimeError("CLOUDFRONT_DOMAIN is not configured")
    if not (storage_config.get("AWS_ACCESS_KEY_ID") or "").strip():
        raise RuntimeError("AWS_ACCESS_KEY_ID is not configured")
    if not (storage_config.get("AWS_SECRET_ACCESS_KEY") or "").strip():
        raise RuntimeError("AWS_SECRET_ACCESS_KEY is not configured")

    safe_name = os.path.basename(filename)
    model_stem = Path(safe_name).stem or "model"

    s3 = _s3_client(storage_config)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        source_path = tmp_dir_path / safe_name
        source_name = f"{model_stem}_source.glb"
        compressed_name = f"{model_stem}_draco.glb"
        compressed_path = tmp_dir_path / compressed_name

        source_path.write_bytes(file_bytes)

        # Always upload source GLB so renderer can preserve original material/texture fidelity.
        source_key = f"models/{source_name}"
        with source_path.open("rb") as handle:
            s3.upload_fileobj(
                handle,
                storage_config["S3_BUCKET"],
                source_key,
                ExtraArgs={"ContentType": "model/gltf-binary"},
            )
        source_size = source_path.stat().st_size

        # Try uploading a Draco variant as an optional optimization artifact.
        # Do not fail the request if Draco compression is unavailable or fails.
        try:
            compress_glb_with_draco(source_path, compressed_path)
            draco_key = f"models/{compressed_name}"
            with compressed_path.open("rb") as handle:
                s3.upload_fileobj(
                    handle,
                    storage_config["S3_BUCKET"],
                    draco_key,
                    ExtraArgs={"ContentType": "model/gltf-binary"},
                )
        except Exception:
            pass

    domain = storage_config["CLOUDFRONT_DOMAIN"].replace("https://", "").strip("/")
    cdn_url = f"https://{domain}/{source_key}"
    return cdn_url, source_size, source_key
