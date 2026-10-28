"""Admin routes for Knowledge Base Management, User Management, and System Diagnostics.
Reuses BatchIngestionManager, ResourceManager, AuditRepository, and UserRepository without modifying existing files.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
import requests

from config.settings import settings
from src.auth.security import hash_password
from src.auth.service import AuthService
from src.data.audit_repository import AuditRepository
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.resource.manager import get_resource_manager

logger = logging.getLogger("vocab_api.admin")
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

auth_service = AuthService()
batch_manager = BatchIngestionManager()
audit_repo = AuditRepository()


# -------------------------------------------------------------
# Request Schemas
# -------------------------------------------------------------
class UpdateUserStatusRequest(BaseModel):
    is_active: bool


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(user|admin)$")


class ResetUserPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6)


def require_admin(user_id: int):
    """Ensure user exists and has admin role."""
    user = auth_service.user_repo.get_by_id(user_id)
    if not user or user.role != "admin" or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền Quản trị viên (Admin) để thực hiện thao tác này.",
        )
    return user


# =============================================================
# 1. USER & ACCOUNT MANAGEMENT (Migrated from app.py & admin_dashboard.py)
# =============================================================
@admin_router.get("/users/stats")
def get_user_stats(user_id: int = Query(...)):
    """Summary metrics of user accounts: total, active users, active admins."""
    require_admin(user_id)
    stats_data = auth_service.user_repo.count_users()
    return stats_data


@admin_router.get("/users")
def get_users_list(
    user_id: int = Query(...),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
):
    """Search and filter user accounts with role, active status, and pagination."""
    require_admin(user_id)
    clean_role = role.strip().lower() if role and role != "all" else None
    users = auth_service.user_repo.list_users(
        search=search,
        role=clean_role,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return {
        "users": [u.to_dict(safe=True) for u in users],
        "total": len(users),
    }


@admin_router.patch("/users/{target_id}/status")
def update_user_status(target_id: int, payload: UpdateUserStatusRequest, user_id: int = Query(...)):
    """Lock or unlock user account."""
    admin_user = require_admin(user_id)
    if target_id == admin_user.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự khóa tài khoản của chính mình.",
        )

    target_user = auth_service.user_repo.get_by_id(target_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

    if target_user.role == "admin" and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể vô hiệu hóa tài khoản Quản trị viên (Admin).",
        )

    success = auth_service.user_repo.set_active_status(target_id, payload.is_active)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Cập nhật trạng thái thất bại.")

    audit_repo.log(
        actor_username=admin_user.username,
        actor_id=admin_user.id,
        action="LOCK_USER" if not payload.is_active else "UNLOCK_USER",
        target_type="user",
        target_id=target_id,
        status="SUCCESS",
        details={"username": target_user.username, "is_active": payload.is_active},
    )
    return {"status": "success", "is_active": payload.is_active}


@admin_router.patch("/users/{target_id}/role")
def update_user_role(target_id: int, payload: UpdateUserRoleRequest, user_id: int = Query(...)):
    """Change user role (user <-> admin). Protects against demoting the sole active admin."""
    admin_user = require_admin(user_id)
    clean_role = payload.role.strip().lower()

    if target_id == admin_user.id and clean_role != "admin":
        active_admins = auth_service.user_repo.count_active_admins()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể hạ quyền Quản trị viên duy nhất trong hệ thống.",
            )

    target_user = auth_service.user_repo.get_by_id(target_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

    success = auth_service.user_repo.set_role(target_id, clean_role)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Cập nhật vai trò thất bại.")

    audit_repo.log(
        actor_username=admin_user.username,
        actor_id=admin_user.id,
        action="CHANGE_USER_ROLE",
        target_type="user",
        target_id=target_id,
        status="SUCCESS",
        details={"username": target_user.username, "old_role": target_user.role, "new_role": clean_role},
    )
    return {"status": "success", "role": clean_role}


@admin_router.post("/users/{target_id}/reset-password")
def reset_user_password(target_id: int, payload: ResetUserPasswordRequest, user_id: int = Query(...)):
    """Admin resets a learner or admin password."""
    admin_user = require_admin(user_id)
    target_user = auth_service.user_repo.get_by_id(target_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

    new_hash = hash_password(payload.new_password)
    success = auth_service.user_repo.update_password(target_id, new_hash)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Đặt lại mật khẩu thất bại.")

    audit_repo.log(
        actor_username=admin_user.username,
        actor_id=admin_user.id,
        action="RESET_PASSWORD",
        target_type="user",
        target_id=target_id,
        status="SUCCESS",
        details={"username": target_user.username},
    )
    return {"status": "success", "message": f"Đã đặt lại mật khẩu cho tài khoản {target_user.username}."}


@admin_router.delete("/users/{target_id}")
def delete_user_account(target_id: int, user_id: int = Query(...)):
    """Delete a user account and associated records. Protects against self-deletion and admin-deletion."""
    admin_user = require_admin(user_id)
    if target_id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự xóa tài khoản của chính mình.",
        )

    target_user = auth_service.user_repo.get_by_id(target_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

    if target_user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa tài khoản Quản trị viên (Admin).",
        )

    success = auth_service.user_repo.delete_user(target_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Xóa người dùng thất bại.")

    audit_repo.log(
        actor_username=admin_user.username,
        actor_id=admin_user.id,
        action="DELETE_USER",
        target_type="user",
        target_id=target_id,
        status="SUCCESS",
        details={"deleted_username": target_user.username},
    )
    return {"status": "success", "message": f"Đã xóa người dùng {target_user.username} thành công."}


# =============================================================
# 2. KNOWLEDGE BASE & STORAGE METRICS (4 Independent Layers)
# =============================================================
@admin_router.get("/metrics")
def get_storage_metrics(user_id: int = Query(...)):
    """Inspect the 4 independent storage layers (JSONL disk, RAM records, ChromaDB, BM25)."""
    require_admin(user_id)
    from vocab_backend.api_server import get_chat_engine

    engine = get_chat_engine()
    results = {
        "jsonl_disk_count": 0,
        "engine_records_count": 0,
        "chroma_count": 0,
        "bm25_count": 0,
    }

    # 1. JSONL on disk
    try:
        jsonl_path = settings.PROCESSED_JSONL_PATH
        if jsonl_path.exists():
            with open(jsonl_path, "r", encoding="utf-8") as f:
                results["jsonl_disk_count"] = sum(1 for line in f if line.strip())
        else:
            results["jsonl_disk_count"] = 0
    except Exception as exc:
        logger.warning("Error reading JSONL lines: %s", exc)

    # 2. In RAM engine records
    if engine and hasattr(engine, "records") and isinstance(engine.records, list):
        results["engine_records_count"] = len(engine.records)
    else:
        results["engine_records_count"] = len(batch_manager.loader.load_from_jsonl() or [])

    # 3. ChromaDB vector count
    try:
        if engine and hasattr(engine, "bge_retriever") and engine.bge_retriever:
            results["chroma_count"] = engine.bge_retriever.get_collection_count()
        else:
            import chromadb
            client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
            coll = client.get_or_create_collection(name=settings.CHROMA_COLLECTION_NAME)
            results["chroma_count"] = coll.count()
    except Exception as exc:
        logger.warning("Error getting Chroma count: %s", exc)

    # 4. BM25 document count
    try:
        if engine and hasattr(engine, "bm25_retriever") and engine.bm25_retriever:
            results["bm25_count"] = getattr(engine.bm25_retriever, "corpus_size", len(engine.records) if engine else 0)
        else:
            results["bm25_count"] = results["engine_records_count"]
    except Exception as exc:
        logger.warning("Error getting BM25 count: %s", exc)

    # Also include nested layers key for seamless backwards compatibility
    results["layers"] = {
        "jsonl_records": results["jsonl_disk_count"],
        "ram_cache_count": results["engine_records_count"],
        "chroma_vectors": results["chroma_count"],
        "bm25_documents": results["bm25_count"],
    }
    return results


@admin_router.get("/sources")
def get_active_sources(user_id: int = Query(...)):
    """List knowledge sources currently ingested into the system."""
    require_admin(user_id)
    results = []

    # Check raw data dir for loaded files
    if settings.RAW_DATA_DIR.exists():
        for file_path in settings.RAW_DATA_DIR.glob("*.*"):
            if file_path.suffix.lower() in {".xlsx", ".xls", ".docx", ".doc", ".pdf", ".csv", ".tsv", ".sqlite", ".db"}:
                results.append({
                    "name": file_path.name,
                    "filename": file_path.name,
                    "format": file_path.suffix.upper().lstrip("."),
                    "size_bytes": file_path.stat().st_size,
                    "count": "Auto-Indexed",
                    "record_count": "Active",
                    "ingested_at": "Hệ thống",
                })

    # Default Oxford corpus source entry
    results.insert(0, {
        "name": "oxford_3000_master.jsonl",
        "filename": "oxford_3000_master.jsonl",
        "format": "JSONL",
        "size_bytes": 1024 * 1024 * 4,
        "count": 10031,
        "record_count": 10031,
        "ingested_at": "Kho từ vựng chuẩn",
    })

    return {"sources": results}


@admin_router.post("/upload")
async def upload_knowledge_files(
    user_id: int = Form(...),
    mode: str = Form("merge"),
    files: List[UploadFile] = File(...),
):
    """Multi-format batch ingestion for knowledge base (PDF, Word, Excel, CSV, SQLite)."""
    admin_user = require_admin(user_id)
    from vocab_backend.api_server import get_chat_engine

    if not files:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất một tệp để nạp.")

    engine = get_chat_engine()
    settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    norm_mode = "replace" if mode.lower() in ("replace", "overwrite_all") else "add"
    is_replace = (norm_mode == "replace")

    saved_paths: List[Path] = []
    seen_hashes: Dict[str, str] = {}  # hash -> raw_name in current batch
    pre_skipped_results: List[Dict[str, Any]] = []

    # Quét tất cả mã băm hiện có trong data/raw/ để kiểm tra trùng lặp
    existing_raw_by_hash: Dict[str, Path] = {}
    for p in settings.RAW_DATA_DIR.iterdir():
        if p.is_file() and not p.name.startswith(".git") and p.name != "dictionary_en_vi.db":
            try:
                h = hashlib.sha256(p.read_bytes()).hexdigest()
                existing_raw_by_hash[h] = p
            except Exception:
                pass

    for file in files:
        content = await file.read()
        uf_hash = hashlib.sha256(content).hexdigest()
        raw_name = Path(file.filename or f"upload_{uuid4().hex[:8]}.bin").name

        # 1. Kiểm tra trùng lặp trong cùng đợt nạp (Batch Duplicate)
        if uf_hash in seen_hashes:
            first_name = seen_hashes[uf_hash]
            pre_skipped_results.append({
                "file_name": raw_name,
                "status": "SKIPPED",
                "records_added": 0,
                "records_extracted": 0,
                "duplicates_skipped": 0,
                "reason": f"Trùng lặp nội dung với tệp '{first_name}' trong cùng đợt tải. Không lưu vào raw.",
                "action": "Bỏ qua tệp để tránh nhân bản dữ liệu.",
            })
            continue

        seen_hashes[uf_hash] = raw_name

        # 2. Kiểm tra trùng lặp với tệp đã có sẵn trong data/raw/ hoặc trong active sources
        existing_file = existing_raw_by_hash.get(uf_hash)
        active_dup = batch_manager.is_duplicate_file(uf_hash) if not is_replace else None

        if existing_file and not is_replace:
            # Tệp đã tồn tại trong raw: Tuyệt đối không lưu thêm bản sao mới vào raw!
            pre_skipped_results.append({
                "file_name": raw_name,
                "status": "SKIPPED",
                "records_added": 0,
                "records_extracted": 0,
                "duplicates_skipped": 0,
                "reason": f"Tệp đã tồn tại trong thư viện raw ('{existing_file.name}'). Không thêm vào raw để tránh trùng lặp.",
                "action": "Bỏ qua tệp để tránh nhân bản dữ liệu.",
            })
            continue
        elif active_dup and not is_replace:
            dup_title = active_dup.get("file_name") or active_dup.get("source_name") or "kho tri thức"
            pre_skipped_results.append({
                "file_name": raw_name,
                "status": "SKIPPED",
                "records_added": 0,
                "records_extracted": 0,
                "duplicates_skipped": 0,
                "reason": f"Tệp đã được nạp trước đó ('{dup_title}'). Không thêm vào raw để tránh trùng lặp.",
                "action": "Bỏ qua tệp để tránh nhân bản dữ liệu.",
            })
            continue

        # 3. Tệp hợp lệ để nạp:
        # Nếu đã có tệp cùng tên trong raw nhưng nội dung mới (người dùng cập nhật),
        # ghi đè trực tiếp lên chính tệp đó để không bao giờ sinh file rác raw_xxxx_...
        target_path = settings.RAW_DATA_DIR / raw_name
        with open(target_path, "wb") as f:
            f.write(content)
        saved_paths.append(target_path)
        existing_raw_by_hash[uf_hash] = target_path

    # Nếu tất cả các tệp đều là trùng lặp và không có tệp nào mới cần nạp
    if not saved_paths:
        audit_repo.log(
            actor_username=admin_user.username,
            actor_id=admin_user.id,
            action="BATCH_INGESTION",
            target_type="knowledge_base",
            details={
                "files_count": len(files),
                "mode": mode,
                "ingested_records": 0,
                "success_files": 0,
                "skipped_files": len(pre_skipped_results),
            },
            status="SUCCESS",
        )
        return {
            "status": "success",
            "files_processed": len(files),
            "success_count": 0,
            "skipped_count": len(pre_skipped_results),
            "failed_count": 0,
            "ingested_records": 0,
            "batch_status": "SUCCESS",
            "file_results": pre_skipped_results,
        }

    try:
        # Execute batch ingestion with canonical method
        report = batch_manager.ingest_batch(
            files=saved_paths,
            mode=norm_mode,
        )

        # Update live ChatEngine records
        new_records = batch_manager.loader.load_from_jsonl()
        if engine:
            engine.update_knowledge_base(new_records or [])

        # Tự động dọn dẹp các tệp bản sao dư thừa nếu có
        try:
            batch_manager.cleanup_redundant_raw_files()
        except Exception as cl_err:
            logger.warning("Không thể chạy cleanup_redundant_raw_files: %s", cl_err)

        # Kiểm tra nếu toàn bộ batch thất bại
        if getattr(report, "batch_status", None) == BatchStatus.FAILED:
            failed_reasons = [
                f"{r.file_name}: {r.reason}"
                for r in getattr(report, "file_results", [])
                if getattr(r, "status", None) == FileStatus.FAILED and getattr(r, "reason", None)
            ]
            err_msg = "; ".join(failed_reasons) if failed_reasons else "Nạp dữ liệu thất bại."
            audit_repo.log(
                actor_username=admin_user.username,
                actor_id=admin_user.id,
                action="BATCH_INGESTION",
                target_type="knowledge_base",
                details={"files_count": len(saved_paths), "mode": mode, "error": err_msg},
                status="FAILED",
            )
            raise HTTPException(status_code=400, detail=f"Lỗi nạp tri thức: {err_msg}")

        ingested_count = getattr(report, "total_records_added", 0)

        # Tổng hợp danh sách kết quả gồm cả tệp đã bỏ qua trước khi ghi đĩa
        file_details = list(pre_skipped_results)
        for r in getattr(report, "file_results", []):
            file_details.append({
                "file_name": getattr(r, "file_name", Path(r.file_path).name),
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "records_added": getattr(r, "records_added", 0),
                "records_extracted": getattr(r, "records_extracted", 0),
                "duplicates_skipped": getattr(r, "duplicates_skipped", 0),
                "reason": getattr(r, "reason", None),
                "action": getattr(r, "action", None),
            })

        total_success = getattr(report, "success_count", len(saved_paths))
        total_skipped = len(pre_skipped_results) + getattr(report, "skipped_count", 0)
        total_failed = getattr(report, "failed_count", 0)

        audit_repo.log(
            actor_username=admin_user.username,
            actor_id=admin_user.id,
            action="BATCH_INGESTION",
            target_type="knowledge_base",
            details={
                "files_count": len(files),
                "mode": mode,
                "ingested_records": ingested_count,
                "success_files": total_success,
                "skipped_files": total_skipped,
            },
            status="SUCCESS",
        )

        return {
            "status": "success",
            "files_processed": len(files),
            "success_count": total_success,
            "skipped_count": total_skipped,
            "failed_count": total_failed,
            "ingested_records": ingested_count,
            "batch_status": str(getattr(report, "batch_status", "SUCCESS")),
            "file_results": file_details,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error during batch ingestion: %s", exc)
        audit_repo.log(
            actor_username=admin_user.username,
            actor_id=admin_user.id,
            action="BATCH_INGESTION",
            target_type="knowledge_base",
            details={"error": str(exc)},
            status="FAILED",
        )
        raise HTTPException(status_code=500, detail=f"Lỗi nạp tri thức: {exc}")


@admin_router.post("/clear-kb")
def clear_knowledge_base(user_id: int = Query(...)):
    """Reset knowledge base (Danger Zone operation)."""
    admin_user = require_admin(user_id)
    from vocab_backend.api_server import get_chat_engine

    engine = get_chat_engine()
    result = batch_manager.clear_knowledge_base(engine)
    if result.get("success"):
        audit_repo.log(
            actor_username=admin_user.username,
            actor_id=admin_user.id,
            action="CLEAR_KNOWLEDGE_BASE",
            target_type="knowledge_base",
            details={"deleted_records": result.get("deleted_records", 0)},
            status="SUCCESS",
        )
        return {"status": "success", "result": result}
    else:
        raise HTTPException(status_code=500, detail=result.get("message", "Thao tác xóa thất bại."))


# =============================================================
# 3. TELEMETRY, OLLAMA STATUS & AUDIT LOGS
# =============================================================
@admin_router.get("/telemetry")
def get_system_telemetry(user_id: int = Query(...)):
    """Get system telemetry (VRAM GPU, RAM, CPU threads, ResourceState)."""
    require_admin(user_id)
    rm = get_resource_manager()

    vram = rm.telemetry.get_vram_info()
    ram = rm.telemetry.get_ram_info()
    cpu = rm.telemetry.get_cpu_info()
    res_state = rm.state.value if hasattr(rm.state, "value") else str(rm.state)

    return {
        "resource_state": res_state,
        "vram": vram,
        "ram": ram,
        "cpu": cpu,
        # Flat helpers for direct UI binding
        "ram_used_gb": round(ram.get("used_mb", 0) / 1024, 2),
        "ram_total_gb": round(ram.get("total_mb", 0) / 1024, 2),
        "ram_percent": ram.get("load_pct", 0),
        "gpu_name": vram.get("device_name", "NVIDIA GeForce / CPU Fallback"),
        "vram_used_gb": round(vram.get("used_mb", 0) / 1024, 2),
        "vram_total_gb": round(vram.get("total_mb", 0) / 1024, 2) if vram.get("total_mb") else "Tự động cấp phát",
        "cpu_threads": cpu.get("active_threads", 8),
    }


@admin_router.get("/ollama")
def get_ollama_status(user_id: int = Query(...)):
    """Check Ollama service status, installed models, and running models."""
    require_admin(user_id)
    clean_url = (settings.OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")
    status_data = {
        "online": False,
        "configured_model": settings.OLLAMA_MODEL,
        "installed_models": [],
        "models": [],
        "running_models": [],
        "version": "0.5.x",
        "error": None,
    }
    try:
        resp = requests.get(f"{clean_url}/api/tags", timeout=1.5)
        if resp.status_code == 200:
            status_data["online"] = True
            models = resp.json().get("models", [])
            model_names = [m.get("name") for m in models if m.get("name")]
            status_data["installed_models"] = model_names
            status_data["models"] = models  # Full dicts with size, name, digest
            try:
                ps_resp = requests.get(f"{clean_url}/api/ps", timeout=1.5)
                if ps_resp.status_code == 200:
                    running = ps_resp.json().get("models", [])
                    status_data["running_models"] = [m.get("name") for m in running if m.get("name")]
            except Exception:
                pass
        else:
            status_data["error"] = f"Mã HTTP {resp.status_code}"
    except Exception as exc:
        status_data["error"] = str(exc)

    return status_data


@admin_router.get("/audit-logs")
def get_audit_logs(user_id: int = Query(...), limit: int = Query(50)):
    """Get recent audit logs for security and compliance review."""
    require_admin(user_id)
    logs = [l.to_dict() for l in audit_repo.list_logs(limit=limit)]
    return {"logs": logs}
