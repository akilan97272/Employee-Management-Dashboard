import os
import re
from datetime import date, datetime, timedelta
from urllib.parse import quote_plus
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError, URLError
from fastapi import APIRouter, Request, UploadFile, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from app.models import Model3D, User
from app.models import Attendance
from app.models_3d_block import Area, Building
from app.database import get_db
from app.app_context import get_current_user
from app.model_storage import process_and_upload_glb, read_storage_config, upsert_storage_config

router = APIRouter()
templates = Jinja2Templates(directory="templates")
_AREA_DATA_CACHE = {"payload": None, "generated_at": "", "expires_at": None}
MODEL_PROXY_CACHE_SECONDS = max(60, int(os.getenv("MODEL_PROXY_CACHE_SECONDS", "86400")))
AREA_DATA_CACHE_TTL_SECONDS = max(5, int(os.getenv("AREA_DATA_CACHE_TTL_SECONDS", "15")))


def _ensure_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def _sanitize_max_limit_people(value, fallback: int = 20) -> int:
    try:
        parsed = int(value)
    except Exception:
        return fallback
    return max(1, parsed)


def _parse_floor_from_text(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "Unknown"

    if re.fullmatch(r"\d+", text):
        return f"Floor {int(text)}"

    if text in {"ground", "ground floor", "gf", "g"} or "ground floor" in text or re.search(r"\bgf\b", text):
        return "Ground Floor"

    basement_direct = re.fullmatch(r"b(?:asement)?\s*(\d+)", text)
    if basement_direct:
        return f"Basement {basement_direct.group(1)}"
    if "basement" in text:
        return "Basement"

    patterns = [
        r"\bfloor\s*[-: ]*\s*(\d+)\b",
        r"\b(\d+)(?:st|nd|rd|th)?\s*floor\b",
        r"\bfl\s*[-: ]*\s*(\d+)\b",
        r"\blevel\s*[-: ]*\s*(\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"Floor {int(match.group(1))}"

    basement_match = re.search(r"\bb\s*(\d+)\b", text)
    if basement_match:
        return f"Basement {basement_match.group(1)}"

    return "Unknown"


def _extract_floor_label(*values: object) -> str:
    # Prefer explicit floor tokens from individual values first (e.g., floor_no="12").
    for value in values:
        parsed = _parse_floor_from_text(value)
        if parsed != "Unknown":
            return parsed

    merged = " ".join(str(v or "") for v in values)
    return _parse_floor_from_text(merged)


def _floor_sort_key(label: str) -> tuple[int, int, str]:
    text = str(label or "").strip().lower()
    if not text:
        return (99, 0, "")
    if "basement" in text:
        m = re.search(r"(\d+)", text)
        level = int(m.group(1)) if m else 0
        return (0, -level, text)
    if "ground" in text:
        return (1, 0, text)
    m = re.search(r"(\d+)", text)
    if m:
        return (2, int(m.group(1)), text)
    return (3, 0, text)


def _unique_known_floors(*values: object) -> list[str]:
    floors: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = _extract_floor_label(value)
        if label == "Unknown":
            continue
        if label in seen:
            continue
        seen.add(label)
        floors.append(label)
    floors.sort(key=_floor_sort_key)
    return floors


def _floor_summary(occupied_floors: list[str], *fallback_values: object) -> str:
    if occupied_floors:
        return ", ".join(occupied_floors)
    fallback = _extract_floor_label(*fallback_values)
    return fallback or "Unknown"


def _build_area_data(db: Session):
    today = date.today()
    live_occupancy_rows = (
        db.query(
            Attendance.location_name.label("location_name"),
            Attendance.room_no.label("room_no"),
            func.count(func.distinct(Attendance.employee_id)).label("people_count"),
        )
        .filter(
            Attendance.date == today,
            Attendance.exit_time.is_(None),
        )
        .group_by(Attendance.location_name, Attendance.room_no)
        .all()
    )
    live_floor_rows = (
        db.query(
            Attendance.location_name.label("location_name"),
            Attendance.room_no.label("room_no"),
            Attendance.floor_no.label("floor_no"),
        )
        .filter(
            Attendance.date == today,
            Attendance.exit_time.is_(None),
            Attendance.room_no.isnot(None),
        )
        .all()
    )

    recent_window_days = 7
    trend_start_day = today - timedelta(days=recent_window_days - 1)

    peak_occupancy_rows = (
        db.query(
            Attendance.location_name.label("location_name"),
            Attendance.room_no.label("room_no"),
            Attendance.date.label("day"),
            func.count(func.distinct(Attendance.employee_id)).label("daily_people_count"),
        )
        .filter(Attendance.date >= (today - timedelta(days=60)))
        .group_by(Attendance.location_name, Attendance.room_no, Attendance.date)
        .all()
    )

    def _key(location_name: str, room_no: str) -> tuple[str, str]:
        return (
            str(location_name or "").strip().lower(),
            str(room_no or "").strip().lower(),
        )

    live_occupancy: dict[tuple[str, str], int] = {}
    for row in live_occupancy_rows:
        live_occupancy[_key(row.location_name, row.room_no)] = int(row.people_count or 0)
    live_floors: dict[tuple[str, str], list[str]] = {}
    for row in live_floor_rows:
        k = _key(row.location_name, row.room_no)
        current = live_floors.get(k, [])
        row_floors = _unique_known_floors(*current, row.floor_no)
        live_floors[k] = row_floors

    peak_occupancy: dict[tuple[str, str], int] = {}
    occupancy_by_day: dict[tuple[str, str], dict[date, int]] = {}
    for row in peak_occupancy_rows:
        k = _key(row.location_name, row.room_no)
        daily_count = int(row.daily_people_count or 0)
        peak_occupancy[k] = max(peak_occupancy.get(k, 0), daily_count)
        day = row.day
        if isinstance(day, date):
            if day >= trend_start_day:
                per_key = occupancy_by_day.setdefault(k, {})
                per_key[day] = max(per_key.get(day, 0), daily_count)

    areas = db.query(Area).all()
    area_data = []
    for area in areas:
        buildings = []
        for b in area.buildings:
            occ_key = _key(area.name, b.name)
            current_people = int(live_occupancy.get(occ_key, 0))
            observed_peak = int(peak_occupancy.get(occ_key, 0))
            estimated_max_limit = max(20, observed_peak + 5, current_people + 5)
            configured_max_limit = _sanitize_max_limit_people(getattr(b, "max_limit_people", None), fallback=estimated_max_limit)
            utilization_pct = int(round((current_people / configured_max_limit) * 100)) if configured_max_limit else 0
            occupied_floors = live_floors.get(occ_key, [])
            floor_label = _floor_summary(occupied_floors, getattr(b, "floor_no", ""), area.name, b.name)
            trend_values = []
            trend_labels = []
            per_day = occupancy_by_day.get(occ_key, {})
            for i in range(recent_window_days):
                d = trend_start_day + timedelta(days=i)
                trend_values.append(int(per_day.get(d, 0)))
                trend_labels.append(d.strftime("%a"))
            buildings.append({
                "id": b.id,
                "name": b.name,
                "glb_path": b.glb_path,
                "floor_label": floor_label,
                "floors_occupied": occupied_floors,
                "current_people": current_people,
                "max_limit_people": configured_max_limit,
                "utilization_percent": utilization_pct,
                "occupancy_trend": trend_values,
                "occupancy_trend_labels": trend_labels,
            })
        area_data.append({
            "id": area.id,
            "name": area.name,
            "buildings": buildings
        })
    return area_data


def _get_cached_area_data(db: Session) -> tuple[list[dict], str, bool]:
    now = datetime.utcnow()
    expires_at = _AREA_DATA_CACHE.get("expires_at")
    if expires_at and now < expires_at and _AREA_DATA_CACHE.get("payload") is not None:
        return (
            _AREA_DATA_CACHE["payload"],
            _AREA_DATA_CACHE.get("generated_at") or now.isoformat() + "Z",
            True,
        )
    payload = _build_area_data(db)
    generated_at = now.isoformat() + "Z"
    _AREA_DATA_CACHE["payload"] = payload
    _AREA_DATA_CACHE["generated_at"] = generated_at
    _AREA_DATA_CACHE["expires_at"] = now + timedelta(seconds=AREA_DATA_CACHE_TTL_SECONDS)
    return payload, generated_at, False


def _draco_to_source_url(url: str) -> str:
    return str(url or "").replace("_draco.glb", "_source.glb")


def _source_to_draco_url(url: str) -> str:
    return str(url or "").replace("_source.glb", "_draco.glb")


def _alternate_model_variant_url(url: str) -> str:
    current = str(url or "")
    if "_source.glb" in current:
        return _source_to_draco_url(current)
    if "_draco.glb" in current:
        return _draco_to_source_url(current)
    return current


def _url_to_s3_key(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return (parsed.path or "").lstrip("/")


def _s3_object_exists(s3_client, bucket: str, key: str) -> bool:
    if not key:
        return False
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False
    except Exception:
        return False


def _normalize_host(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        parsed = urlparse(raw)
        return (parsed.netloc or parsed.path or "").strip().lower().strip("/")
    except Exception:
        return ""


def _try_stream_from_s3_for_cloudfront_url(url: str, db: Session):
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"}:
        return None

    storage_config = read_storage_config(db)
    bucket = (storage_config.get("S3_BUCKET") or "").strip()
    cloudfront_domain = _normalize_host(storage_config.get("CLOUDFRONT_DOMAIN"))
    request_host = _normalize_host(parsed.netloc)
    if not bucket or not request_host:
        return None

    # Only allow S3 fallback for the configured distribution host, when provided.
    if cloudfront_domain and request_host != cloudfront_domain:
        return None

    key = (parsed.path or "").lstrip("/")
    if not key:
        return None

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=storage_config.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=storage_config.get("AWS_SECRET_ACCESS_KEY"),
            region_name=storage_config.get("AWS_REGION") or "ap-south-1",
        )
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        payload = obj["Body"].read()
    except Exception:
        return None

    content_type = obj.get("ContentType") or "model/gltf-binary"
    return Response(
        content=payload,
        media_type=content_type,
        headers={
            "Cache-Control": f"public, max-age={MODEL_PROXY_CACHE_SECONDS}, immutable",
            "Content-Length": str(len(payload)),
        },
    )


def _list_bucket_glb_models(storage_config: dict[str, str]) -> tuple[list[dict[str, object]], str]:
    bucket = (storage_config.get("S3_BUCKET") or "").strip()
    domain = (storage_config.get("CLOUDFRONT_DOMAIN") or "").strip().replace("https://", "").strip("/")
    access_key = (storage_config.get("AWS_ACCESS_KEY_ID") or "").strip()
    secret_key = (storage_config.get("AWS_SECRET_ACCESS_KEY") or "").strip()
    region = (storage_config.get("AWS_REGION") or "ap-south-1").strip()

    if not bucket:
        return [], "S3 bucket is not configured."
    if not domain:
        return [], "CloudFront domain is not configured."
    if not access_key or not secret_key:
        return [], "AWS credentials are not configured."

    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        paginator = s3.get_paginator("list_objects_v2")
        models: list[dict[str, object]] = []
        for page in paginator.paginate(Bucket=bucket, Prefix="models/"):
            for obj in page.get("Contents", []):
                key = (obj.get("Key") or "").strip()
                if not key or key.endswith("/") or not key.lower().endswith(".glb"):
                    continue
                models.append(
                    {
                        "key": key,
                        "filename": os.path.basename(key),
                        "size": int(obj.get("Size") or 0),
                        "last_modified": obj.get("LastModified"),
                        "url": f"https://{domain}/{key}",
                    }
                )
        def _epoch(item: dict[str, object]) -> float:
            stamp = item.get("last_modified")
            if hasattr(stamp, "timestamp"):
                try:
                    return float(stamp.timestamp())
                except Exception:
                    return 0.0
            return 0.0

        models.sort(key=_epoch, reverse=True)
        return models, ""
    except ClientError as exc:
        code = ((exc.response or {}).get("Error") or {}).get("Code", "ClientError")
        msg = ((exc.response or {}).get("Error") or {}).get("Message", "Request failed")
        return [], f"{code}: {msg}"
    except BotoCoreError as exc:
        return [], str(exc)
    except Exception as exc:
        return [], str(exc)


@router.get("/admin/3d-block", response_class=HTMLResponse)
def admin_3d_block(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    areas = db.query(Area).all()
    area_data, _, _ = _get_cached_area_data(db)
    return templates.TemplateResponse(
        "admin/admin_3d_block.html",
        {
            "request": request,
            "areas": areas,
            "area_data": area_data,
            "user": user,
        },
    )


@router.get("/admin/3d-block/data")
def admin_3d_block_data(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    payload, generated_at, cached = _get_cached_area_data(db)
    return {
        "areas": payload,
        "generated_at": generated_at,
        "cached": cached,
    }

@router.get("/admin/3d-block/search")
def search_employee(
    request: Request,
    employee_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    name = (employee_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="employee_name is required")

    try:
        employee = db.query(User).filter(User.name.ilike(f"%{name}%"), User.is_active == True).first()
        if not employee:
            return {"status": "not_found", "message": "Employee not found or currently not inside any building."}

        open_block = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == employee.employee_id,
                Attendance.exit_time.is_(None),
                Attendance.room_no != "77",
            )
            .order_by(Attendance.entry_time.desc())
            .first()
        )
        if not open_block:
            return {
                "status": "not_there",
                "message": "Employee not found or currently not inside any building.",
                "employee": {
                    "name": employee.name,
                    "employee_id": employee.employee_id,
                },
            }

        mapped_building = (
            db.query(
                Area.id.label("area_id"),
                Area.name.label("area_name"),
                Building.id.label("building_id"),
                Building.name.label("building_name"),
                Building.floor_no.label("floor_no"),
                Attendance.floor_no.label("attendance_floor_no"),
            )
            .join(Building, Building.area_id == Area.id)
            .outerjoin(
                Attendance,
                (func.lower(Attendance.location_name) == func.lower(Area.name))
                & (func.lower(Attendance.room_no) == func.lower(Building.name))
                & (Attendance.employee_id == employee.employee_id)
                & (Attendance.exit_time.is_(None)),
            )
            .filter(
                func.lower(Area.name) == func.lower(open_block.location_name),
                func.lower(Building.name) == func.lower(open_block.room_no),
            )
            .first()
        )
        if not mapped_building:
            return {
                "status": "not_there",
                "message": "Employee not found or currently not inside any building.",
                "employee": {
                    "name": employee.name,
                    "employee_id": employee.employee_id,
                },
            }

        now = datetime.now()
        entry_time = open_block.entry_time
        exit_time = open_block.exit_time
        computed_duration = open_block.duration
        if entry_time and not exit_time:
            computed_duration = round((now - entry_time).total_seconds() / 3600, 2)

        def _fmt_dt(value):
            if not value:
                return "-"
            return value.strftime("%Y-%m-%d %H:%M:%S")

        employee_floor = _extract_floor_label(
            open_block.floor_no,
            mapped_building.attendance_floor_no,
            mapped_building.floor_no,
            mapped_building.area_name,
            mapped_building.building_name,
        )
        return {
            "status": "found",
            "area_id": mapped_building.area_id,
            "area_name": mapped_building.area_name,
            "building_id": mapped_building.building_id,
            "building_name": mapped_building.building_name,
            "floor_label": employee_floor,
            "floors_occupied": [employee_floor] if employee_floor != "Unknown" else [],
            "employee": {
                "name": employee.name,
                "employee_id": employee.employee_id,
                "floor": employee_floor,
                "in_time": _fmt_dt(entry_time),
                "out_time": _fmt_dt(exit_time),
                "duration": computed_duration or 0.0,
            },
        }
    except Exception:
        return {
            "status": "error",
            "message": "Employee search is temporarily unavailable. Please try again.",
        }


@router.get("/admin/3d-block/search-suggestions")
def search_employee_suggestions(
    q: str = "",
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    keyword = (q or "").strip()
    if len(keyword) < 1:
        return {"items": []}

    safe_limit = max(1, min(int(limit or 10), 20))
    rows = (
        db.query(User.name, User.employee_id)
        .filter(
            User.is_active == True,
            User.name.ilike(f"%{keyword}%"),
        )
        .order_by(User.name.asc())
        .limit(safe_limit)
        .all()
    )
    return {
        "items": [
            {
                "name": r.name,
                "employee_id": r.employee_id,
                "label": f"{r.name} ({r.employee_id})",
            }
            for r in rows
        ]
    }


@router.get("/admin/3d-block/building-people")
def building_people(
    area_id: int,
    building_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)

    area = db.query(Area).filter(Area.id == area_id).first()
    building = db.query(Building).filter(Building.id == building_id, Building.area_id == area_id).first()
    if not area or not building:
        raise HTTPException(status_code=404, detail="Area or building not found")

    today = date.today()
    rows = (
        db.query(
            Attendance.employee_id,
            Attendance.entry_time,
            Attendance.floor_no,
            User.name,
            User.photo_blob,
        )
        .join(User, User.employee_id == Attendance.employee_id)
        .filter(
            Attendance.date == today,
            Attendance.exit_time.is_(None),
            func.lower(Attendance.location_name) == func.lower(area.name),
            func.lower(Attendance.room_no) == func.lower(building.name),
            User.is_active == True,
        )
        .order_by(Attendance.entry_time.desc())
        .all()
    )

    seen_ids: set[str] = set()
    people = []
    occupied_floors: list[str] = []
    for row in rows:
        emp_id = str(row.employee_id or "").strip()
        if not emp_id or emp_id in seen_ids:
            continue
        seen_ids.add(emp_id)
        person_floor = _extract_floor_label(row.floor_no, getattr(building, "floor_no", ""), area.name, building.name)
        occupied_floors = _unique_known_floors(*occupied_floors, person_floor)
        people.append(
            {
                "name": row.name or "-",
                "employee_id": emp_id,
                "in_time": row.entry_time.strftime("%Y-%m-%d %H:%M:%S") if row.entry_time else "-",
                "floor": person_floor,
                "photo_url": f"/employee/photo/{quote_plus(emp_id)}" if row.photo_blob else "",
            }
        )
    floor_label = _floor_summary(occupied_floors, getattr(building, "floor_no", ""), area.name, building.name)

    return {
        "area_id": area.id,
        "area_name": area.name,
        "building_id": building.id,
        "building_name": building.name,
        "floor_label": floor_label,
        "floors_occupied": occupied_floors,
        "count": len(people),
        "people": people,
    }

@router.get("/admin/3d-block/filter")
def filter_area(request: Request, area_id: int, db: Session = Depends(get_db)):
    area = db.query(Area).filter(Area.id == area_id).first()
    if area:
        return {"buildings": [b.name for b in area.buildings]}
    return {"error": "Area not found"}


@router.get("/admin/3d-block/model-proxy")
def model_proxy(
    url: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Invalid model URL scheme")

    # Prefer direct S3 stream for configured CloudFront-hosted assets to avoid CORS and signed URL issues.
    s3_stream = _try_stream_from_s3_for_cloudfront_url(url, db)
    if s3_stream is not None:
        return s3_stream

    alt_url = _alternate_model_variant_url(url)
    if alt_url != url:
        alt_s3_stream = _try_stream_from_s3_for_cloudfront_url(alt_url, db)
        if alt_s3_stream is not None:
            return alt_s3_stream

    try:
        upstream = urlopen(
            UrlRequest(url, headers={"User-Agent": "TeamSync-ModelProxy/1.0"}),
            timeout=25,
        )
        payload = upstream.read()
    except HTTPError as exc:
        if (exc.code or 0) == 403:
            s3_stream = _try_stream_from_s3_for_cloudfront_url(url, db)
            if s3_stream is not None:
                return s3_stream

            # Try alternate source/draco variant if the requested URL is forbidden.
            if alt_url != url:
                try:
                    alt_upstream = urlopen(
                        UrlRequest(alt_url, headers={"User-Agent": "TeamSync-ModelProxy/1.0"}),
                        timeout=25,
                    )
                    alt_payload = alt_upstream.read()
                    alt_content_type = alt_upstream.headers.get("Content-Type", "model/gltf-binary")
                    return Response(
                        content=alt_payload,
                        media_type=alt_content_type,
                        headers={
                            "Cache-Control": f"public, max-age={MODEL_PROXY_CACHE_SECONDS}, immutable",
                            "Content-Length": str(len(alt_payload)),
                        },
                    )
                except Exception:
                    alt_s3_stream = _try_stream_from_s3_for_cloudfront_url(alt_url, db)
                    if alt_s3_stream is not None:
                        return alt_s3_stream

            raise HTTPException(status_code=403, detail="Model access forbidden by upstream and variant fallback failed")
        raise HTTPException(status_code=exc.code or 502, detail="Upstream model URL returned an error")
    except URLError:
        raise HTTPException(status_code=502, detail="Unable to reach upstream model URL")
    except Exception:
        raise HTTPException(status_code=502, detail="Model proxy request failed")

    content_type = upstream.headers.get("Content-Type", "model/gltf-binary")
    return Response(
        content=payload,
        media_type=content_type,
        headers={
            "Cache-Control": f"public, max-age={MODEL_PROXY_CACHE_SECONDS}, immutable",
            "Content-Length": str(len(payload)),
        },
    )


@router.post("/admin/3d-block/settings/migrate-source-urls")
def migrate_draco_urls_to_source(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)

    storage_config = read_storage_config(db)
    bucket = (storage_config.get("S3_BUCKET") or "").strip()
    if not bucket:
        raise HTTPException(status_code=400, detail="S3 bucket is not configured")

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=storage_config.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=storage_config.get("AWS_SECRET_ACCESS_KEY"),
            region_name=storage_config.get("AWS_REGION") or "ap-south-1",
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to initialize S3 client")

    cache: dict[str, bool] = {}
    checked = 0
    updated_buildings = 0
    updated_models = 0
    skipped_missing_source = 0

    def _source_available_for(url: str) -> tuple[str, bool]:
        source_url = _draco_to_source_url(url)
        if source_url == url:
            return source_url, False
        key = _url_to_s3_key(source_url)
        if key in cache:
            return source_url, cache[key]
        exists = _s3_object_exists(s3_client, bucket, key)
        cache[key] = exists
        return source_url, exists

    buildings = db.query(Building).all()
    for b in buildings:
        current = (b.glb_path or "").strip()
        if "_draco.glb" not in current:
            continue
        checked += 1
        source_url, exists = _source_available_for(current)
        if exists:
            b.glb_path = source_url
            updated_buildings += 1
        else:
            skipped_missing_source += 1

    models = db.query(Model3D).all()
    for m in models:
        current = (m.url or "").strip()
        if "_draco.glb" not in current:
            continue
        checked += 1
        source_url, exists = _source_available_for(current)
        if exists:
            m.url = source_url
            updated_models += 1
        else:
            skipped_missing_source += 1

    db.commit()
    return {
        "status": "ok",
        "checked": checked,
        "updated_buildings": updated_buildings,
        "updated_models": updated_models,
        "skipped_missing_source": skipped_missing_source,
    }

@router.get("/admin/3d-block/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    areas = db.query(Area).all()
    models = db.query(Model3D).order_by(Model3D.created_at.desc()).all()
    storage_config = read_storage_config(db)
    bucket_models, bucket_model_error = _list_bucket_glb_models(storage_config)
    return templates.TemplateResponse(
        "admin/admin_3d_block_settings.html",
        {
            "request": request,
            "areas": areas,
            "models": models,
            "bucket_models": bucket_models,
            "bucket_model_error": bucket_model_error,
            "storage_config": storage_config,
            "config_status": request.query_params.get("config_status", ""),
            "config_message": request.query_params.get("config_message", ""),
            "upload_status": request.query_params.get("upload_status", ""),
            "import_status": request.query_params.get("import_status", ""),
            "import_message": request.query_params.get("import_message", ""),
            "user": user,
        },
    )


@router.post("/admin/3d-block/settings/import-bucket-models")
async def import_bucket_models(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    form = await request.form()

    area_id_raw = str(form.get("area_id") or "").strip()
    if not area_id_raw.isdigit():
        return RedirectResponse("/admin/3d-block/settings?import_status=invalid", status_code=303)

    area = db.query(Area).filter(Area.id == int(area_id_raw)).first()
    if not area:
        return RedirectResponse("/admin/3d-block/settings?import_status=invalid", status_code=303)

    selected_indices = [str(i).strip() for i in form.getlist("selected_index") if str(i).strip()]
    if not selected_indices:
        return RedirectResponse("/admin/3d-block/settings?import_status=empty", status_code=303)

    created = 0
    skipped = 0
    for idx in selected_indices:
        model_url = str(form.get(f"model_url_{idx}") or "").strip()
        building_name = str(form.get(f"building_name_{idx}") or "").strip()
        max_limit_raw = str(form.get(f"max_limit_people_{idx}") or "").strip()
        size_raw = str(form.get(f"model_size_{idx}") or "").strip()

        if not model_url or not building_name:
            skipped += 1
            continue

        existing_building = (
            db.query(Building.id)
            .filter(
                Building.area_id == area.id,
                func.lower(Building.name) == building_name.lower(),
            )
            .first()
        )
        if existing_building:
            skipped += 1
            continue

        try:
            max_limit = _sanitize_max_limit_people(max_limit_raw or "20")
        except Exception:
            max_limit = 20

        try:
            model_size = int(size_raw) if size_raw else 0
        except Exception:
            model_size = 0

        db.add(
            Building(
                name=building_name,
                area_id=area.id,
                glb_path=model_url,
                max_limit_people=max_limit,
            )
        )
        db.add(
            Model3D(
                name=building_name,
                url=model_url,
                size=model_size,
            )
        )
        created += 1

    if created == 0:
        db.rollback()
        return RedirectResponse("/admin/3d-block/settings?import_status=none_created", status_code=303)

    db.commit()
    message = quote_plus(f"Created {created} building mappings in {area.name}. Skipped {skipped}.")
    return RedirectResponse(f"/admin/3d-block/settings?import_status=ok&import_message={message}", status_code=303)


@router.post("/admin/3d-block/settings/storage-config")
def save_storage_config(
    request: Request,
    aws_access_key_id: str = Form(...),
    aws_secret_access_key: str = Form(""),
    aws_region: str = Form("ap-south-1"),
    s3_bucket: str = Form(...),
    cloudfront_domain: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    current = read_storage_config(db)
    secret_value = aws_secret_access_key.strip() or current.get("AWS_SECRET_ACCESS_KEY", "").strip()
    payload = {
        "AWS_ACCESS_KEY_ID": aws_access_key_id.strip(),
        "AWS_SECRET_ACCESS_KEY": secret_value,
        "AWS_REGION": aws_region.strip() or "ap-south-1",
        "S3_BUCKET": s3_bucket.strip(),
        "CLOUDFRONT_DOMAIN": cloudfront_domain.strip().replace("https://", "").strip("/"),
    }
    if not payload["AWS_ACCESS_KEY_ID"] or not payload["AWS_SECRET_ACCESS_KEY"] or not payload["S3_BUCKET"] or not payload["CLOUDFRONT_DOMAIN"]:
        return RedirectResponse("/admin/3d-block/settings?config_status=invalid", status_code=303)
    try:
        upsert_storage_config(db, payload)
        db.commit()
        for key, value in payload.items():
            os.environ[key] = value
        return RedirectResponse("/admin/3d-block/settings?config_status=saved", status_code=303)
    except Exception:
        db.rollback()
        return RedirectResponse("/admin/3d-block/settings?config_status=error", status_code=303)


@router.post("/admin/3d-block/settings/test-storage-config")
def test_storage_config(
    request: Request,
    aws_access_key_id: str = Form(...),
    aws_secret_access_key: str = Form(""),
    aws_region: str = Form("ap-south-1"),
    s3_bucket: str = Form(...),
    cloudfront_domain: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    current = read_storage_config(db)
    secret_value = aws_secret_access_key.strip() or current.get("AWS_SECRET_ACCESS_KEY", "").strip()
    cfg = {
        "AWS_ACCESS_KEY_ID": aws_access_key_id.strip(),
        "AWS_SECRET_ACCESS_KEY": secret_value,
        "AWS_REGION": aws_region.strip() or "ap-south-1",
        "S3_BUCKET": s3_bucket.strip(),
        "CLOUDFRONT_DOMAIN": cloudfront_domain.strip().replace("https://", "").strip("/"),
    }
    if not cfg["AWS_ACCESS_KEY_ID"] or not cfg["AWS_SECRET_ACCESS_KEY"] or not cfg["S3_BUCKET"] or not cfg["CLOUDFRONT_DOMAIN"]:
        return RedirectResponse("/admin/3d-block/settings?config_status=test_invalid", status_code=303)

    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=cfg["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=cfg["AWS_SECRET_ACCESS_KEY"],
            region_name=cfg["AWS_REGION"],
        )
        s3.head_bucket(Bucket=cfg["S3_BUCKET"])
        return RedirectResponse("/admin/3d-block/settings?config_status=test_ok", status_code=303)
    except ClientError as exc:
        code = ((exc.response or {}).get("Error") or {}).get("Code", "ClientError")
        msg = ((exc.response or {}).get("Error") or {}).get("Message", "Request failed")
        detail = quote_plus(f"{code}: {msg}")
        return RedirectResponse(f"/admin/3d-block/settings?config_status=test_error&config_message={detail}", status_code=303)
    except BotoCoreError as exc:
        detail = quote_plus(str(exc)[:180])
        return RedirectResponse(f"/admin/3d-block/settings?config_status=test_error&config_message={detail}", status_code=303)
    except Exception as exc:
        detail = quote_plus(str(exc)[:180])
        return RedirectResponse(f"/admin/3d-block/settings?config_status=test_error&config_message={detail}", status_code=303)


@router.post("/admin/3d-block/settings/add-area")
def add_area(
    request: Request,
    area_name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    area = Area(name=area_name)
    db.add(area)
    db.commit()
    return RedirectResponse("/admin/3d-block/settings", status_code=303)

@router.post("/admin/3d-block/settings/add-building")
def add_building(
    request: Request,
    area_id: int = Form(...),
    building_name: str = Form(...),
    max_limit_people: int = Form(20),
    glb_file: UploadFile = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Selected area not found")
    if not glb_file.filename:
        raise HTTPException(status_code=400, detail="GLB file is required")
    file_bytes = glb_file.file.read()

    try:
        storage_config = read_storage_config(db)
        cdn_url, size, _ = process_and_upload_glb(glb_file.filename, file_bytes, storage_config=storage_config)
        building = Building(
            name=building_name,
            area_id=area_id,
            glb_path=cdn_url,
            max_limit_people=_sanitize_max_limit_people(max_limit_people),
        )
        model_entry = Model3D(name=building_name, url=cdn_url, size=size)
        db.add(building)
        db.add(model_entry)
        db.commit()
    except ValueError as exc:
        return RedirectResponse("/admin/3d-block/settings?upload_status=invalid_file", status_code=303)
    except RuntimeError as exc:
        message = str(exc).lower()
        if "gltf-transform" in message and "not found" in message:
            return RedirectResponse("/admin/3d-block/settings?upload_status=missing_gltf_transform", status_code=303)
        return RedirectResponse("/admin/3d-block/settings?upload_status=upload_error", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse("/admin/3d-block/settings?upload_status=upload_error", status_code=303)

    return RedirectResponse("/admin/3d-block/settings", status_code=303)


@router.post("/admin/3d-block/settings/update-model-name")
def update_model_name(
    request: Request,
    id: int = Form(...),
    name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    model = db.query(Model3D).filter(Model3D.id == id).first()
    if not model:
        return RedirectResponse("/admin/3d-block/settings?config_status=error", status_code=303)
    model.name = name.strip()
    db.commit()
    return RedirectResponse("/admin/3d-block/settings", status_code=303)


@router.post("/admin/3d-block/settings/update-area")
def update_area(
    request: Request,
    area_id: int = Form(...),
    area_name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        return RedirectResponse("/admin/3d-block/settings?config_status=error", status_code=303)
    area.name = area_name.strip()
    db.commit()
    return RedirectResponse("/admin/3d-block/settings", status_code=303)


@router.post("/admin/3d-block/settings/delete-area")
def delete_area(
    request: Request,
    area_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        return RedirectResponse("/admin/3d-block/settings?config_status=error", status_code=303)

    area_buildings = db.query(Building).filter(Building.area_id == area.id).all()
    for b in area_buildings:
        db.query(Model3D).filter(Model3D.url == b.glb_path).delete()
        db.delete(b)
    db.delete(area)
    db.commit()
    return RedirectResponse("/admin/3d-block/settings", status_code=303)


@router.post("/admin/3d-block/settings/update-building")
def update_building(
    request: Request,
    building_id: int = Form(...),
    building_name: str = Form(...),
    area_id: int = Form(...),
    max_limit_people: int = Form(20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    building = db.query(Building).filter(Building.id == building_id).first()
    area = db.query(Area).filter(Area.id == area_id).first()
    if not building or not area:
        return RedirectResponse("/admin/3d-block/settings?config_status=error", status_code=303)
    building.name = building_name.strip()
    building.area_id = area_id
    building.max_limit_people = _sanitize_max_limit_people(max_limit_people)
    linked_model = db.query(Model3D).filter(Model3D.url == building.glb_path).first()
    if linked_model:
        linked_model.name = building.name
    db.commit()
    return RedirectResponse("/admin/3d-block/settings", status_code=303)


@router.post("/admin/3d-block/settings/delete-building")
def delete_building(
    request: Request,
    building_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(user)
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        return RedirectResponse("/admin/3d-block/settings?config_status=error", status_code=303)
    db.query(Model3D).filter(Model3D.url == building.glb_path).delete()
    db.delete(building)
    db.commit()
    return RedirectResponse("/admin/3d-block/settings", status_code=303)
