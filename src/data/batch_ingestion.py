"""Module điều phối nạp hàng loạt đa tệp (Batch Multi-File Ingestion Engine).

Hỗ trợ:
- Tiếp nhận cùng lúc nhiều định dạng: PDF, DOCX, TXT, CSV, XLSX, JSON, JSONL, MD.
- Xử lý độc lập từng tệp (File Processing Independence & Partial Success).
- Truy vết nguồn gốc chi tiết (Multi-File Metadata & Source Isolation).
- Phát hiện trùng lặp mức tệp (File Hash SHA-256) và mức nội dung (Content Hash).
- Quản lý kho tri thức: Báo cáo Ingestion, Retry, Delete Source, Re-index Source.
- Đảm bảo 100% Cục bộ (Offline-only), không fine-tune Qwen, không dùng API ngoài.
"""

import json
import logging
import re
import shutil
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from config.settings import settings
from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import QALoader
from src.data.loaders.base import clean_source_name, compute_file_hash
from src.data.loaders.router import FileLoaderRouter
from src.retriever.bge_chroma import BGEChromaRetriever
from src.retriever.bm25_retriever import BM25Retriever

logger = logging.getLogger(__name__)


class FileStatus(str, Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    PROCESSING = "PROCESSING"
    INDEXING = "INDEXING"
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class BatchStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL SUCCESS"
    FAILED = "FAILED"


@dataclass
class FileIngestionResult:
    """Kết quả xử lý riêng biệt của từng tệp trong batch."""
    file_name: str
    file_path: str
    file_type: str
    file_size_bytes: int
    file_hash: str
    status: FileStatus = FileStatus.QUEUED
    reason: Optional[str] = None
    action: Optional[str] = None
    records_extracted: int = 0
    records_added: int = 0
    duplicates_skipped: int = 0
    record_ids: List[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_name": self.file_name,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
            "file_hash": self.file_hash,
            "status": self.status.value if isinstance(self.status, FileStatus) else self.status,
            "reason": self.reason,
            "action": self.action,
            "records_extracted": self.records_extracted,
            "records_added": self.records_added,
            "duplicates_skipped": self.duplicates_skipped,
            "record_ids": self.record_ids,
            "elapsed_seconds": self.elapsed_seconds,
        }


@dataclass
class BatchIngestionReport:
    """Báo cáo tổng hợp sau khi xử lý toàn bộ batch đa tệp."""
    total_files: int
    success_count: int
    skipped_count: int
    failed_count: int
    total_records_extracted: int
    total_records_added: int
    total_duplicates_skipped: int
    chromadb_status: str
    bm25_status: str
    batch_status: BatchStatus
    file_results: List[FileIngestionResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def format_report(self) -> str:
        """Định dạng báo cáo dạng văn bản chuẩn theo yêu cầu dự án."""
        lines = [
            "================================",
            "BATCH INGESTION REPORT",
            "================================",
            f"Total Files: {self.total_files}",
            "",
            f"SUCCESS: {self.success_count}",
            f"SKIPPED: {self.skipped_count}",
            f"FAILED:  {self.failed_count}",
            "",
            f"Records Extracted: {self.total_records_extracted:,}",
            f"Records Added:     {self.total_records_added:,}",
            f"Duplicates:        {self.total_duplicates_skipped:,}",
            "",
            f"ChromaDB: {self.chromadb_status}",
            f"BM25:     {self.bm25_status}",
            "",
            f"Batch Status:",
            f"{self.batch_status.value if isinstance(self.batch_status, BatchStatus) else self.batch_status}",
            f"Elapsed Time: {self.elapsed_seconds:.2f}s",
            "================================",
        ]
        if self.file_results:
            lines.append("\nChi tiết từng tệp:")
            for res in self.file_results:
                st_icon = "✅" if res.status == FileStatus.SUCCESS else ("⚠️" if res.status == FileStatus.SKIPPED else "❌")
                lines.append(f"  {st_icon} {res.file_name:<25} | {res.status.value:<9} | +{res.records_added} bản ghi | {res.reason or 'Hoàn tất'}")
        return "\n".join(lines)


class BatchIngestionManager:
    """Bộ điều phối nạp hàng loạt đa tệp và quản lý nguồn dữ liệu tri thức."""

    def __init__(
        self,
        router: Optional[FileLoaderRouter] = None,
        loader: Optional[QALoader] = None,
        manifest_path: Optional[Path] = None,
    ):
        self.router = router or FileLoaderRouter()
        self.loader = loader or QALoader()
        self.manifest_path = manifest_path or (settings.PROCESSED_DATA_DIR / "sources_manifest.json")

    # --- QUẢN LÝ MANIFEST NGUỒN DỮ LIỆU (SOURCE REGISTRY) ---

    def load_manifest(self) -> Dict[str, Any]:
        """Đọc danh mục các nguồn dữ liệu đã nạp từ tệp manifest."""
        if not self.manifest_path.exists():
            return {"sources": {}}
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as err:
            logger.warning("Không thể đọc sources_manifest.json: %s. Tạo mới.", err)
            return {"sources": {}}

    def save_manifest(self, manifest: Dict[str, Any]) -> None:
        """Lưu danh mục nguồn dữ liệu vào tệp manifest."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def get_active_sources(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các nguồn dữ liệu đang hoạt động.
        
        Tự động đồng bộ chuẩn hóa file_name và source_name, loại bỏ tiền tố tạm
        (batch_..., raw_...) và xử lý tương thích ngược cho manifest cũ.
        """
        manifest = self.load_manifest()
        active_list = []
        for s in manifest.get("sources", {}).values():
            if s.get("status") == "ACTIVE":
                src_copy = dict(s)
                raw_name = s.get("file_name") or s.get("source_name")
                if not raw_name and s.get("file_path"):
                    raw_name = Path(s["file_path"]).name

                clean_name = clean_source_name(str(raw_name).strip()) if raw_name else ""
                display_name = clean_name or "Chưa rõ tên nguồn (Thiếu metadata)"

                src_copy["file_name"] = display_name
                src_copy["source_name"] = display_name
                active_list.append(src_copy)
        return active_list

    def is_duplicate_file(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Kiểm tra mã băm SHA-256 đã tồn tại trong manifest nguồn đang hoạt động chưa."""
        manifest = self.load_manifest()
        for src in manifest.get("sources", {}).values():
            if src.get("status") == "ACTIVE" and src.get("file_hash") == file_hash:
                return src
        return None

    def _cleanup_batch_duplicate_files(
        self,
        file_results: List[FileIngestionResult],
        seen_batch_hashes: Dict[str, Tuple[str, Path]],
        manifest: Dict[str, Any],
    ) -> None:
        """Xóa an toàn các bản sao vật lý dư thừa của các tệp bị bỏ qua do trùng lặp nội dung."""
        for res in file_results:
            if res.status != FileStatus.SKIPPED or not res.reason or "Duplicate file" not in res.reason:
                continue

            dup_path = Path(res.file_path)
            if not dup_path.exists() or not dup_path.is_file():
                continue

            # Xác định đường dẫn tệp gốc canonical
            canonical_path: Optional[Path] = None
            if res.file_hash in seen_batch_hashes:
                _, first_p = seen_batch_hashes[res.file_hash]
                canonical_path = Path(first_p)

            if not canonical_path or not canonical_path.exists():
                active_src = self.is_duplicate_file(res.file_hash)
                if active_src and active_src.get("file_path"):
                    canonical_path = Path(active_src["file_path"])

            # Kiểm tra an toàn nghiêm ngặt:
            # 1. Tệp gốc phải tồn tại và là tệp tin thật
            # 2. Mã băm SHA-256 của tệp gốc phải khớp chính xác với file_hash
            # 3. Bản sao phải khác vị trí vật lý với bản gốc (resolve path)
            # 4. Bản sao phải là tệp tạm hoặc tệp trong raw/tmp (không xóa nhầm tệp ngoài phạm vi)
            if (
                canonical_path
                and canonical_path.exists()
                and canonical_path.is_file()
                and dup_path.resolve() != canonical_path.resolve()
            ):
                try:
                    if compute_file_hash(canonical_path) == res.file_hash:
                        is_managed_copy = (
                            bool(re.match(r"^(?:raw|batch|doc|upload|tmp|temp)_[0-9a-fA-F\-]{6,36}_", dup_path.name))
                            or dup_path.parent == settings.RAW_DATA_DIR
                            or "temp" in str(dup_path.parent).lower()
                        )
                        if is_managed_copy:
                            dup_path.unlink(missing_ok=True)
                            logger.info(
                                "Deduplication: Đã xóa bản sao vật lý dư thừa '%s'. Giữ bản gốc '%s'.",
                                dup_path.name, canonical_path.name
                            )
                            res.action = f"Đã loại bỏ bản sao dư thừa, giữ bản gốc duy nhất: {canonical_path.name}"
                except Exception as err:
                    logger.warning("Không thể dọn dẹp bản sao dư thừa '%s': %s", dup_path, err)

    def cleanup_redundant_raw_files(self, raw_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Quét và tự động dọn dẹp các bản sao vật lý dư thừa trong thư mục raw data.
        
        Đảm bảo mỗi nội dung tệp (xác định qua SHA-256) chỉ giữ lại một bản gốc duy nhất.
        Không xóa các tệp hệ thống (.gitkeep, .db, .backup) hoặc tệp đang được tham chiếu
        bởi manifest active sources.
        """
        target_dir = Path(raw_dir or settings.RAW_DATA_DIR)
        if not target_dir.exists():
            return {"scanned": 0, "deleted": [], "preserved": []}

        manifest = self.load_manifest()
        active_sources = manifest.get("sources", {})
        canonical_by_hash: Dict[str, Path] = {}
        for sinfo in active_sources.values():
            if sinfo.get("status") == "ACTIVE" and sinfo.get("file_hash") and sinfo.get("file_path"):
                p = Path(sinfo["file_path"])
                if p.exists() and p.is_file():
                    canonical_by_hash[sinfo["file_hash"]] = p

        files_by_hash: Dict[str, List[Path]] = {}
        skipped_system_files: List[str] = []

        for fpath in target_dir.iterdir():
            if not fpath.is_file():
                continue
            if fpath.name.startswith(".git") or fpath.suffix.lower() in [".backup", ".sqlite3"] or fpath.name == "dictionary_en_vi.db":
                skipped_system_files.append(fpath.name)
                continue

            try:
                f_hash = compute_file_hash(fpath)
                files_by_hash.setdefault(f_hash, []).append(fpath)
            except Exception as err:
                logger.warning("Không thể đọc mã băm tệp '%s': %s", fpath, err)

        deleted_files: List[str] = []
        preserved_files: List[str] = []
        manifest_updated = False

        for f_hash, flist in files_by_hash.items():
            # Ưu tiên tệp có tên chuẩn gốc không có tiền tố raw_... / tmp_...
            clean_candidates = [p for p in flist if clean_source_name(p.name) == p.name]
            if clean_candidates:
                kept = sorted(clean_candidates, key=lambda p: (len(p.name), p.name))[0]
            else:
                first_p = sorted(flist, key=lambda p: (len(p.name), p.name))[0]
                target_clean_name = clean_source_name(first_p.name)
                clean_target_path = first_p.parent / target_clean_name
                if not clean_target_path.exists():
                    try:
                        first_p.rename(clean_target_path)
                        kept = clean_target_path
                    except Exception:
                        kept = first_p
                else:
                    kept = first_p

            preserved_files.append(kept.name)

            for p in flist:
                if p.resolve() == kept.resolve():
                    continue
                try:
                    if compute_file_hash(kept) == f_hash:
                        p.unlink(missing_ok=True)
                        deleted_files.append(p.name)
                        logger.info("Đã dọn dẹp bản sao dư thừa: %s (Bản gốc giữ: %s)", p.name, kept.name)
                except Exception as err:
                    logger.warning("Không thể dọn dẹp bản sao '%s': %s", p.name, err)

            # Đồng bộ lại đường dẫn trong manifest nếu đường dẫn cũ thay đổi
            for sinfo in active_sources.values():
                if sinfo.get("file_hash") == f_hash and sinfo.get("file_path"):
                    if Path(sinfo["file_path"]).resolve() != kept.resolve():
                        sinfo["file_path"] = str(kept.resolve())
                        sinfo["file_name"] = kept.name
                        manifest_updated = True

        if manifest_updated:
            self.save_manifest(manifest)

        return {
            "scanned": sum(len(fl) for fl in files_by_hash.values()) + len(skipped_system_files),
            "deleted": deleted_files,
            "preserved": preserved_files,
            "skipped_system": skipped_system_files
        }

    # --- PIPELINE NẠP BATCH ĐA TỆP ---

    def ingest_batch(
        self,
        files: Optional[List[Path]] = None,
        mode: str = "add",
        progress_callback: Optional[Callable[[str, float, FileIngestionResult], None]] = None,
        batch_size: int = 16,
        sqlite_mappings: Optional[Dict[str, Any]] = None,
        file_paths: Optional[List[Path]] = None,
    ) -> BatchIngestionReport:
        """Thực thi pipeline Batch Multi-File Ingestion với xử lý độc lập từng tệp.

        Args:
            files: Danh sách đường dẫn tệp cần nạp (hỗ trợ cả alias file_paths).
            mode: "add" (bổ sung / update theo ID) hoặc "replace" (xóa làm mới toàn bộ).
            progress_callback: Hàm nhận callback (thông_điệp, tiến_độ_0_đến_1, kết_quả_tệp_hiện_tại).
            batch_size: Kích thước batch embedding BGE-M3 (an toàn cho CPU/RAM).
            sqlite_mappings: Ánh xạ cấu hình SQLite mapping tùy chọn theo file_hash hoặc tên tệp.
            file_paths: Tham số dự phòng đồng nghĩa với files.

        Returns:
            BatchIngestionReport: Báo cáo tổng thể toàn bộ batch.
        """
        target_files = files if files is not None else (file_paths or [])
        files = target_files
        batch_start_time = time.perf_counter()
        total_files = len(files)
        file_results: List[FileIngestionResult] = []
        is_replace = (mode.lower() == "replace")

        # 1. Đọc dữ liệu hiện có và manifest gốc
        original_existing_records: List[QARecord] = []
        if self.loader.processed_jsonl_path.exists():
            try:
                original_existing_records = self.loader.load_from_jsonl()
            except Exception:
                original_existing_records = []

        manifest = self.load_manifest()

        # Staging: Thiết lập vùng làm việc (Working / Staged Records)
        if is_replace:
            # Chế độ REPLACE: Dữ liệu mới được thu thập trên staging độc lập, chưa xóa dữ liệu cũ
            working_records: List[QARecord] = []
        else:
            working_records = list(original_existing_records)

        working_by_id: Dict[str, Tuple[int, QARecord]] = {
            r.record_id: (idx, r) for idx, r in enumerate(working_records) if r.record_id
        }
        working_signatures: Dict[Tuple[str, str], str] = {
            (r.question.strip().lower(), r.answer.strip().lower()): r.record_id
            for r in working_records
        }

        newly_accumulated_records: List[QARecord] = []
        sources_dict = manifest.setdefault("sources", {})
        seen_batch_hashes: Dict[str, Tuple[str, Path]] = {}

        # 2. Xử lý tuần tự từng tệp một cách độc lập
        for file_idx, file_path in enumerate(files, 1):
            file_start = time.perf_counter()

            # Phục hồi tên tệp hiển thị gốc nếu tệp được lưu với prefix tránh trùng lặp
            display_file_name = clean_source_name(file_path.name)

            f_res = FileIngestionResult(
                file_name=display_file_name,
                file_path=str(file_path.resolve()),
                file_type=file_path.suffix.lower().lstrip("."),
                file_size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                file_hash="",
                status=FileStatus.QUEUED,
            )

            # Thông báo tiến độ
            pct = (file_idx - 1) / max(total_files, 1)
            if progress_callback:
                progress_callback(f"Bắt đầu xử lý {display_file_name}...", pct, f_res)

            # Bước 2.1: Xác thực tệp (Validation)
            f_res.status = FileStatus.VALIDATING
            val_res = self.router.validate_file(file_path)
            if not val_res.is_valid:
                f_res.status = FileStatus.FAILED
                f_res.reason = val_res.error_message or "Tệp không hợp lệ."
                f_res.action = "Bỏ qua tệp, không bổ sung vào cơ sở dữ liệu."
                f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)
                file_results.append(f_res)
                if progress_callback:
                    progress_callback(f"Lỗi tệp {display_file_name}: {f_res.reason}", pct, f_res)
                continue

            f_res.file_hash = val_res.file_hash
            f_res.file_size_bytes = val_res.file_size_bytes

            # Bước 2.2: Kiểm tra tệp trùng lặp (Duplicate File Check)
            duplicate_src_name: Optional[str] = None
            dup_origin: str = ""
            if val_res.file_hash in seen_batch_hashes:
                prev_name, _ = seen_batch_hashes[val_res.file_hash]
                duplicate_src_name = prev_name
                dup_origin = "trong cùng đợt nạp"
            elif not is_replace:
                duplicate_src = self.is_duplicate_file(val_res.file_hash)
                if duplicate_src:
                    duplicate_src_name = clean_source_name(duplicate_src.get("file_name") or duplicate_src.get("source_name") or "")
                    dup_origin = "đã nạp trước đó"

            if duplicate_src_name:
                f_res.status = FileStatus.SKIPPED
                f_res.reason = f"Duplicate file: Trùng nội dung với tệp '{duplicate_src_name}' ({dup_origin})."
                f_res.action = "Bỏ qua tệp để tránh nhân bản dữ liệu."
                f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)
                file_results.append(f_res)
                if progress_callback:
                    progress_callback(f"Bỏ qua {display_file_name} (Trùng tệp)", pct, f_res)
                continue

            seen_batch_hashes[val_res.file_hash] = (display_file_name, file_path)

            # Bước 2.3: Phân tích & Trích xuất nội dung (Processing)
            f_res.status = FileStatus.PROCESSING
            f_mapping = None
            if sqlite_mappings:
                f_mapping = (
                    sqlite_mappings.get(val_res.file_hash)
                    or sqlite_mappings.get(file_path.name)
                    or sqlite_mappings.get(display_file_name)
                )

            try:
                raw_extracted = self.router.load_file(
                    file_path=file_path,
                    file_hash=val_res.file_hash,
                    start_index=len(working_records) + 1,
                    mapping_config=f_mapping
                )
            except Exception as err:
                f_res.status = FileStatus.FAILED
                f_res.reason = f"Lỗi phân tích nội dung tệp: {err}"
                f_res.action = "Không thể đọc cấu trúc dữ liệu, bỏ qua tệp."
                f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)
                file_results.append(f_res)
                if progress_callback:
                    progress_callback(f"Lỗi đọc {display_file_name}: {err}", pct, f_res)
                continue

            f_res.records_extracted = len(raw_extracted)
            if not raw_extracted:
                f_res.status = FileStatus.FAILED
                f_res.reason = "Không trích xuất được bản ghi văn bản / Q&A hợp lệ nào."
                f_res.action = "Tệp không chứa nội dung tra cứu phù hợp."
                f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)
                file_results.append(f_res)
                if progress_callback:
                    progress_callback(f"Không có bản ghi trong {display_file_name}", pct, f_res)
                continue

            # Bước 2.4: Phân loại theo Stable ID (ADD / UPDATE / DUPLICATE)
            file_valid_records: List[QARecord] = []
            file_seen_ids: Set[str] = set()
            for r in raw_extracted:
                if not r.record_id:
                    continue

                # Chuẩn hóa metadata nguồn về display_file_name
                if not r.source or r.source == file_path.name:
                    r.source = display_file_name

                # 1. Nếu trong cùng tệp đã xuất hiện ID này rồi:
                # Cập nhật đè lên bản ghi trước trong file_valid_records và working_records thay vì append duplicate
                if r.record_id in file_seen_ids:
                    for i, f_rec in enumerate(file_valid_records):
                        if f_rec.record_id == r.record_id:
                            file_valid_records[i] = r
                            break
                    if r.record_id in working_by_id:
                        old_idx, _ = working_by_id[r.record_id]
                        working_records[old_idx] = r
                    continue

                file_seen_ids.add(r.record_id)

                # 2. Nếu ID đã tồn tại trong KB -> UPDATE / OVERWRITE
                if r.record_id in working_by_id:
                    old_idx, old_r = working_by_id[r.record_id]
                    old_sig = (old_r.question.strip().lower(), old_r.answer.strip().lower())
                    working_signatures.pop(old_sig, None)

                    working_records[old_idx] = r
                    new_sig = (r.question.strip().lower(), r.answer.strip().lower())
                    working_signatures[new_sig] = r.record_id
                    working_by_id[r.record_id] = (old_idx, r)
                    file_valid_records.append(r)
                    continue

                # 3. Nếu trùng hoàn toàn nội dung mà không có ID mới -> Bỏ qua duplicate
                sig = (r.question.strip().lower(), r.answer.strip().lower())
                if sig in working_signatures:
                    f_res.duplicates_skipped += 1
                    continue

                # 4. ID mới và nội dung mới -> ADD
                new_idx = len(working_records)
                working_signatures[sig] = r.record_id
                working_by_id[r.record_id] = (new_idx, r)
                working_records.append(r)
                file_valid_records.append(r)

            if not file_valid_records:
                f_res.status = FileStatus.SKIPPED
                f_res.reason = f"Toàn bộ {f_res.records_extracted} bản ghi đã có sẵn trong kho tri thức."
                f_res.action = "Không cần thêm bản ghi mới."
                f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)
                file_results.append(f_res)
                if progress_callback:
                    progress_callback(f"Bản ghi trong {display_file_name} đều đã tồn tại", pct, f_res)
                continue

            # Tệp có bản ghi mới hợp lệ
            f_res.status = FileStatus.INDEXING
            f_res.records_added = len(file_valid_records)
            f_res.record_ids = [r.record_id for r in file_valid_records]
            f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)

            newly_accumulated_records.extend(file_valid_records)
            file_results.append(f_res)

        # Khử trùng lặp newly_accumulated_records theo record_id (giữ bản ghi mới nhất)
        deduped_accumulated: List[QARecord] = []
        seen_accum_ids: Set[str] = set()
        for r in reversed(newly_accumulated_records):
            if r.record_id:
                if r.record_id in seen_accum_ids:
                    continue
                seen_accum_ids.add(r.record_id)
            deduped_accumulated.append(r)
        deduped_accumulated.reverse()
        newly_accumulated_records = deduped_accumulated

        # 3. Lập chỉ mục ChromaDB & BM25 đồng nhất với cơ chế Staging & Rollback an toàn
        chromadb_status = "UNCHANGED"
        bm25_status = "UNCHANGED"
        rollback_needed = False
        used_gpu = False
        ollama_cli = None

        from src.resource.manager import ResourceState, get_resource_manager
        rm = get_resource_manager()

        # --- KIỂM TRA BẢO VỆ DỮ LIỆU REPLACE (REPLACE DATA SAFETY GATE) ---
        if is_replace and len(newly_accumulated_records) == 0:
            logger.warning(
                "Chế độ REPLACE bị hủy bỏ: Không có bản ghi hợp lệ nào được trích xuất từ các tệp đầu vào. "
                "Kho tri thức hiện tại (%d bản ghi) được bảo toàn nguyên vẹn.",
                len(original_existing_records)
            )
            for res in file_results:
                if res.status == FileStatus.INDEXING or res.status == FileStatus.QUEUED:
                    res.status = FileStatus.FAILED
                    res.reason = "Không có bản ghi hợp lệ để lập chỉ mục. Đã hủy bỏ thao tác REPLACE để bảo vệ dữ liệu cũ."
                    res.action = "Kiểm tra lại nội dung tệp đầu vào."

            chromadb_status = "UNCHANGED (REPLACE ABORTED)"
            bm25_status = "UNCHANGED"
            rollback_needed = True

        elif newly_accumulated_records or (is_replace and len(working_records) > 0):
            jsonl_path = self.loader.processed_jsonl_path
            manifest_path = self.manifest_path
            bak_jsonl = jsonl_path.with_suffix(".jsonl.bak")
            bak_manifest = manifest_path.with_suffix(".json.bak")

            # 3.0. Tạo bản sao lưu Snapshot Backup trước khi ghi
            try:
                if jsonl_path.exists():
                    shutil.copy2(jsonl_path, bak_jsonl)
                if manifest_path.exists():
                    shutil.copy2(manifest_path, bak_manifest)
            except Exception as bak_err:
                logger.warning("Không thể tạo snapshot backup: %s", bak_err)

            target_records = working_records

            # Xác định thiết bị và điều phối tài nguyên
            record_count_for_eval = len(working_records) if is_replace else len(newly_accumulated_records)
            target_device, dev_reason = rm.determine_indexing_device(record_count_for_eval, is_replace=is_replace)
            logger.info("Chính sách điều phối Ingestion: %s (Lý do: %s)", target_device, dev_reason)

            if target_device == "cuda":
                if progress_callback:
                    progress_callback("Đang điều phối tài nguyên GPU (giải phóng mô hình LLM)...", 0.70, None)
                from src.llm.client import OllamaClient
                ollama_cli = OllamaClient()
                success_prep, prep_msg = rm.prepare_gpu_indexing(ollama_client=ollama_cli)
                if success_prep:
                    used_gpu = True
                else:
                    logger.warning("Không thể kích hoạt GPU: %s. Chuyển sang CPU.", prep_msg)
                    target_device = "cpu"
                    used_gpu = False
            else:
                rm.state = ResourceState.INDEXING_CPU

            eff_batch_size = (
                int(getattr(settings, "INDEXING_GPU_BATCH_SIZE", 64))
                if used_gpu
                else int(getattr(settings, "INDEXING_CPU_BATCH_SIZE", 32))
            )

            if progress_callback:
                progress_callback(
                    f"Đang đồng bộ cơ sở dữ liệu ({len(target_records)} bản ghi, thiết bị: {target_device.upper()})...",
                    0.85,
                    None
                )

            try:
                # Thực hiện cập nhật dữ liệu dưới khóa ghi IndexAccessCoordinator (độc quyền siêu ngắn)
                with rm.coordinator.write_lock():
                    # 3.1. Đồng bộ ChromaDB
                    bge_retriever = BGEChromaRetriever(target_records)
                    raw_before = bge_retriever.get_collection_count()
                    if isinstance(raw_before, (int, float)):
                        chroma_count_before = int(raw_before)
                    else:
                        try:
                            chroma_count_before = int(bge_retriever.collection.count())
                        except Exception:
                            chroma_count_before = 0

                    if is_replace:
                        bge_retriever.build_or_load_collection(force_reindex=True)
                    else:
                        bge_retriever.upsert_records(newly_accumulated_records, batch_size=eff_batch_size)
                    chromadb_status = "UPDATED"

                    # 3.2. Cập nhật qa_records.jsonl
                    self.loader.save_to_jsonl(target_records)

                    # 3.3. Tái lập chỉ mục BM25
                    bm25_retriever = BM25Retriever(target_records)
                    bm25_status = "UPDATED"

                    # 3.4. Kiểm tra tính đồng bộ trước khi commit manifest
                    raw_after = bge_retriever.collection.count() if bge_retriever.collection else bge_retriever.get_collection_count()
                    if isinstance(raw_after, (int, float)):
                        chroma_count = int(raw_after)
                    else:
                        try:
                            chroma_count = int(bge_retriever.get_collection_count())
                        except Exception:
                            chroma_count = 0

                    jsonl_count = len(target_records)
                    bm25_count = len(bm25_retriever.records)

                    if is_replace or (chroma_count_before == len(original_existing_records)):
                        if not (chroma_count == jsonl_count == bm25_count):
                            raise RuntimeError(
                                f"Không đồng bộ giữa các thành phần sau khi index: "
                                f"ChromaDB={chroma_count}, JSONL={jsonl_count}, BM25={bm25_count}"
                            )
                    else:
                        if chroma_count < chroma_count_before:
                            raise RuntimeError(
                                f"Lỗi thất thoát vector ChromaDB sau khi index: "
                                f"Trước={chroma_count_before}, Sau={chroma_count}"
                            )
                        if jsonl_count != bm25_count:
                            raise RuntimeError(
                                f"Không đồng bộ giữa JSONL và BM25: JSONL={jsonl_count}, BM25={bm25_count}"
                            )

                    # 3.5. Cập nhật manifest
                    if is_replace:
                        manifest["sources"] = {}
                    sources_dict = manifest.setdefault("sources", {})

                    for res in file_results:
                        if res.status == FileStatus.INDEXING:
                            res.status = FileStatus.SUCCESS
                            res.reason = f"Đã nạp thành công {res.records_added} bản ghi vào kho tri thức."
                            res.action = "Sẵn sàng tra cứu."

                            source_id = f"SRC_{res.file_hash[:12]}"
                            sources_dict[source_id] = {
                                "source_id": source_id,
                                "file_name": res.file_name,
                                "source_name": res.file_name,
                                "file_path": res.file_path,
                                "file_hash": res.file_hash,
                                "file_type": res.file_type,
                                "file_size_bytes": res.file_size_bytes,
                                "record_count": res.records_added,
                                "record_ids": res.record_ids,
                                "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "status": "ACTIVE",
                            }

                    self.save_manifest(manifest)

                    # Xóa bản sao lưu sau khi commit thành công
                    if bak_jsonl.exists():
                        bak_jsonl.unlink(missing_ok=True)
                    if bak_manifest.exists():
                        bak_manifest.unlink(missing_ok=True)

            except Exception as err:
                logger.error("Lỗi khi lập chỉ mục batch: %s. Đang kích hoạt ROLLBACK...", err)
                rollback_needed = True
                chromadb_status = f"FAILED: {err}"
                bm25_status = "FAILED"

                # Thực hiện ROLLBACK an toàn dưới khóa ghi
                try:
                    with rm.coordinator.write_lock():
                        if bak_jsonl.exists():
                            shutil.copy2(bak_jsonl, jsonl_path)
                            bak_jsonl.unlink(missing_ok=True)
                        elif jsonl_path.exists() and not original_existing_records:
                            jsonl_path.unlink(missing_ok=True)

                        if bak_manifest.exists():
                            shutil.copy2(bak_manifest, manifest_path)
                            bak_manifest.unlink(missing_ok=True)
                        elif manifest_path.exists() and not manifest.get("sources"):
                            manifest_path.unlink(missing_ok=True)

                        if is_replace:
                            BGEChromaRetriever(original_existing_records).build_or_load_collection(force_reindex=True)
                        else:
                            added_ids = [r.record_id for r in newly_accumulated_records if r.record_id]
                            if added_ids:
                                BGEChromaRetriever(original_existing_records).delete_records(added_ids)
                except Exception as rb_err:
                    logger.critical("Rollback thất bại: %s", rb_err)

                for res in file_results:
                    if res.status == FileStatus.INDEXING:
                        res.status = FileStatus.FAILED
                        res.reason = f"Lỗi lập chỉ mục: {err} (Đã phục hồi dữ liệu ban đầu)."

            finally:
                # Luôn khôi phục trạng thái tài nguyên sau khi hoàn tất hoặc lỗi
                rm.finalize_indexing(used_gpu=used_gpu, ollama_client=ollama_cli if used_gpu else None)


        # 3.6. Dọn dẹp an toàn các bản sao vật lý dư thừa của tệp trùng lặp khi không có rollback
        if not rollback_needed:
            self._cleanup_batch_duplicate_files(file_results, seen_batch_hashes, manifest)

        # 4. Tính toán kết quả tổng thể (Batch Status: SUCCESS / PARTIAL SUCCESS / FAILED)
        success_cnt = sum(1 for r in file_results if r.status == FileStatus.SUCCESS)
        skipped_cnt = sum(1 for r in file_results if r.status == FileStatus.SKIPPED)
        failed_cnt = sum(1 for r in file_results if r.status == FileStatus.FAILED)

        if rollback_needed or failed_cnt == total_files:
            b_status = BatchStatus.FAILED
        elif success_cnt == total_files:
            b_status = BatchStatus.SUCCESS
        elif success_cnt > 0 or (skipped_cnt > 0 and failed_cnt == 0):
            b_status = BatchStatus.PARTIAL_SUCCESS
        else:
            b_status = BatchStatus.FAILED

        elapsed_total = round(time.perf_counter() - batch_start_time, 2)
        total_extracted = sum(r.records_extracted for r in file_results)
        total_added = sum(r.records_added for r in file_results)
        total_dupes = sum(r.duplicates_skipped for r in file_results)

        report = BatchIngestionReport(
            total_files=total_files,
            success_count=success_cnt,
            skipped_count=skipped_cnt,
            failed_count=failed_cnt,
            total_records_extracted=total_extracted,
            total_records_added=total_added,
            total_duplicates_skipped=total_dupes,
            chromadb_status=chromadb_status,
            bm25_status=bm25_status,
            batch_status=b_status,
            file_results=file_results,
            elapsed_seconds=elapsed_total,
        )

        if progress_callback:
            progress_callback("Hoàn tất xử lý toàn bộ batch!", 1.0, None)

        logger.info(
            "Batch Ingestion Report: %s (SUCCESS: %d, SKIPPED: %d, FAILED: %d, Total Added: %d)",
            b_status.value, success_cnt, skipped_cnt, failed_cnt, total_added
        )
        return report

    def process_batch(
        self,
        files: Optional[List[Path]] = None,
        file_paths: Optional[List[Path]] = None,
        mode: str = "add",
        progress_callback: Optional[Callable[[str, float, FileIngestionResult], None]] = None,
        batch_size: int = 16,
        sqlite_mappings: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BatchIngestionReport:
        """Bí danh (alias) tương thích ngược cho `ingest_batch`.

        Hỗ trợ cả tham số `files` và `file_paths`, đồng thời chuẩn hóa chế độ `mode`
        (chuyển đổi 'replace'/'overwrite' hoặc 'add'/'merge').
        """
        target_files = files if files is not None else (file_paths or [])
        norm_mode = "replace" if str(mode).lower() == "replace" else "add"
        return self.ingest_batch(
            files=target_files,
            mode=norm_mode,
            progress_callback=progress_callback,
            batch_size=batch_size,
            sqlite_mappings=sqlite_mappings,
            **kwargs,
        )

    # --- QUẢN TRỊ NGUỒN: XÓA NGUỒN (DELETE SOURCE) ---

    def delete_source(self, source_identifier: str) -> Dict[str, Any]:
        """Xóa toàn bộ dữ liệu thuộc một nguồn khỏi ChromaDB, JSONL và BM25.

        Args:
            source_identifier: Có thể là source_id (SRC_...) hoặc tên tệp file_name.

        Returns:
            Dict[str, Any]: Kết quả xóa (status, deleted_count, remaining_count).
        """
        manifest = self.load_manifest()
        sources_dict = manifest.setdefault("sources", {})

        target_source: Optional[Dict[str, Any]] = None
        target_sid: Optional[str] = None

        # 1. Tìm nguồn trong manifest
        if source_identifier in sources_dict:
            target_sid = source_identifier
            target_source = sources_dict[source_identifier]
        else:
            for sid, sinfo in sources_dict.items():
                if sinfo.get("file_name") == source_identifier or sinfo.get("file_hash") == source_identifier:
                    target_sid = sid
                    target_source = sinfo
                    break

        # 2. Đọc toàn bộ bản ghi hiện có
        all_records = self.loader.load_from_jsonl() if self.loader.processed_jsonl_path.exists() else []

        # Xác định các record_ids cần xóa
        ids_to_delete: Set[str] = set()
        if target_source and target_source.get("record_ids"):
            ids_to_delete = set(target_source["record_ids"])
        else:
            # Fallback: tìm theo trường source
            for r in all_records:
                if r.source == source_identifier:
                    ids_to_delete.add(r.record_id)

        if not ids_to_delete:
            return {
                "status": "NOT_FOUND",
                "message": f"Không tìm thấy dữ liệu liên kết với nguồn '{source_identifier}'.",
                "deleted_count": 0,
                "remaining_count": len(all_records),
            }

        # 3. Tạo snapshot backup trước khi xóa
        jsonl_path = self.loader.processed_jsonl_path
        manifest_path = self.manifest_path
        bak_jsonl = jsonl_path.with_suffix(".jsonl.bak")
        bak_manifest = manifest_path.with_suffix(".json.bak")
        try:
            if jsonl_path.exists():
                shutil.copy2(jsonl_path, bak_jsonl)
            if manifest_path.exists():
                shutil.copy2(manifest_path, bak_manifest)
        except Exception as bak_err:
            logger.warning("Không thể tạo snapshot backup trước khi xóa nguồn: %s", bak_err)

        try:
            # Xóa vector trong ChromaDB
            bge_retriever = BGEChromaRetriever(all_records)
            bge_retriever.delete_records(list(ids_to_delete))

            # Loại bỏ bản ghi khỏi qa_records.jsonl
            remaining_records = [r for r in all_records if r.record_id not in ids_to_delete]
            self.loader.save_to_jsonl(remaining_records)

            # Tái lập chỉ mục BM25
            bm25_retriever = BM25Retriever(remaining_records)

            # Kiểm tra tính đồng bộ
            chroma_count = bge_retriever.collection.count() if bge_retriever.collection else 0
            if not (chroma_count == len(remaining_records) == len(bm25_retriever.records)):
                raise RuntimeError(
                    f"Lệch đồng bộ sau khi xóa nguồn: ChromaDB={chroma_count}, JSONL={len(remaining_records)}, BM25={len(bm25_retriever.records)}"
                )

            # Cập nhật manifest
            if target_sid and target_sid in sources_dict:
                sources_dict[target_sid]["status"] = "DELETED"
                sources_dict[target_sid]["deleted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self.save_manifest(manifest)

            if bak_jsonl.exists():
                bak_jsonl.unlink(missing_ok=True)
            if bak_manifest.exists():
                bak_manifest.unlink(missing_ok=True)

            logger.info(
                "Delete Source: Đã xóa hoàn toàn %d bản ghi của nguồn '%s'. Còn lại: %d bản ghi.",
                len(ids_to_delete), source_identifier, len(remaining_records)
            )

            return {
                "status": "SUCCESS",
                "message": f"Đã xóa hoàn toàn {len(ids_to_delete)} bản ghi và vector của nguồn '{source_identifier}'.",
                "deleted_count": len(ids_to_delete),
                "remaining_count": len(remaining_records),
            }
        except Exception as err:
            logger.error("Lỗi khi xóa nguồn '%s': %s. Đang hoàn tác khôi phục dữ liệu...", source_identifier, err)
            if bak_jsonl.exists():
                shutil.copy2(bak_jsonl, jsonl_path)
                bak_jsonl.unlink(missing_ok=True)
            if bak_manifest.exists():
                shutil.copy2(bak_manifest, manifest_path)
                bak_manifest.unlink(missing_ok=True)

            try:
                BGEChromaRetriever(all_records).build_or_load_collection(force_reindex=True)
            except Exception as rb_err:
                logger.critical("Rollback ChromaDB sau lỗi xóa nguồn thất bại: %s", rb_err)

            return {
                "status": "FAILED",
                "message": f"Lỗi xóa nguồn: {err} (Đã phục hồi dữ liệu ban đầu an toàn).",
                "deleted_count": 0,
                "remaining_count": len(all_records),
            }

    # --- TÁI LẬP CHỈ MỤC (REINDEX) ---

    def reindex_source(self, source_identifier: str, batch_size: int = 16) -> Dict[str, Any]:
        """Tái lập chỉ mục vector cho các bản ghi thuộc một nguồn cụ thể."""
        all_records = self.loader.load_from_jsonl() if self.loader.processed_jsonl_path.exists() else []
        manifest = self.load_manifest()

        target_ids: Set[str] = set()
        for sid, sinfo in manifest.get("sources", {}).items():
            if sid == source_identifier or sinfo.get("file_name") == source_identifier:
                target_ids = set(sinfo.get("record_ids", []))
                break

        if not target_ids:
            for r in all_records:
                if r.source == source_identifier:
                    target_ids.add(r.record_id)

        source_records = [r for r in all_records if r.record_id in target_ids]
        if not source_records:
            return {
                "status": "NOT_FOUND",
                "message": f"Không tìm thấy bản ghi nào cho nguồn '{source_identifier}'.",
                "reindexed_count": 0
            }

        # Xóa và tạo lại vector
        bge_retriever = BGEChromaRetriever(all_records)
        bge_retriever.delete_records(list(target_ids))
        added = bge_retriever.add_records(source_records, batch_size=batch_size)

        # Cập nhật BM25
        bm25_retriever = BM25Retriever(all_records)

        # Kiểm tra tính đồng bộ
        chroma_count = bge_retriever.collection.count() if bge_retriever.collection else 0
        synced = (chroma_count == len(all_records) == len(bm25_retriever.records))
        if not synced:
            return {
                "status": "FAILED",
                "message": f"Lệch đồng bộ sau khi reindex: ChromaDB={chroma_count}, JSONL={len(all_records)}, BM25={len(bm25_retriever.records)}",
                "reindexed_count": added
            }

        return {
            "status": "SUCCESS",
            "message": f"Đã tái lập chỉ mục thành công cho {added} vector của nguồn '{source_identifier}'.",
            "reindexed_count": added
        }

    def reindex_all(self, batch_size: int = 32) -> Dict[str, Any]:
        """Tái lập chỉ mục toàn bộ cơ sở dữ liệu (Chỉ dùng khi có yêu cầu đặc biệt)."""
        all_records = self.loader.load_from_jsonl() if self.loader.processed_jsonl_path.exists() else []
        if not all_records:
            return {"status": "EMPTY", "message": "Kho tri thức đang rỗng, không có gì để reindex.", "total": 0}

        bge_retriever = BGEChromaRetriever(all_records)
        bge_retriever.build_or_load_collection(force_reindex=True)
        bm25_retriever = BM25Retriever(all_records)

        chroma_count = bge_retriever.collection.count() if bge_retriever.collection else 0
        synced = (chroma_count == len(all_records) == len(bm25_retriever.records))
        if not synced:
            return {
                "status": "FAILED",
                "message": f"Lỗi không đồng bộ sau khi reindex all: ChromaDB={chroma_count}, JSONL={len(all_records)}, BM25={len(bm25_retriever.records)}",
                "total": len(all_records)
            }

        return {
            "status": "SUCCESS",
            "message": f"Đã tái lập chỉ mục toàn bộ {len(all_records):,} bản ghi.",
            "total": len(all_records)
        }

    def delete_record(self, record_id: str) -> Dict[str, Any]:
        """Xóa 1 bản ghi duy nhất và đồng bộ tuyệt đối giữa Source JSONL, ChromaDB và BM25."""
        all_records = self.loader.load_from_jsonl() if self.loader.processed_jsonl_path.exists() else []
        found = False
        remaining = []
        for r in all_records:
            if r.record_id == record_id:
                found = True
            else:
                remaining.append(r)

        if not found:
            return {
                "status": "NOT_FOUND",
                "message": f"Không tìm thấy bản ghi với record_id: '{record_id}'",
                "deleted": False,
                "remaining_count": len(all_records),
                "synced": True
            }

        # 1. Snapshot backup
        jsonl_path = self.loader.processed_jsonl_path
        bak_jsonl = jsonl_path.with_suffix(".jsonl.bak")
        try:
            if jsonl_path.exists():
                shutil.copy2(jsonl_path, bak_jsonl)
        except Exception:
            pass

        try:
            # 2. Xóa trong ChromaDB
            bge_retriever = BGEChromaRetriever(all_records)
            bge_retriever.delete_records([record_id])

            # 3. Cập nhật lại Source JSONL
            self.loader.save_to_jsonl(remaining)

            # 4. Tái lập chỉ mục BM25
            bm25_retriever = BM25Retriever(remaining)

            # 5. Cập nhật manifest
            manifest = self.load_manifest()
            for sinfo in manifest.get("sources", {}).values():
                if record_id in sinfo.get("record_ids", []):
                    sinfo["record_ids"].remove(record_id)
                    sinfo["record_count"] = max(0, sinfo.get("record_count", 1) - 1)
            self.save_manifest(manifest)

            # 6. Kiểm tra tính đồng bộ
            chroma_count = bge_retriever.collection.count() if bge_retriever.collection else 0
            synced = (len(remaining) == chroma_count == len(bm25_retriever.records))
            if not synced:
                raise RuntimeError(
                    f"Lệch đồng bộ sau khi xóa record: ChromaDB={chroma_count}, JSONL={len(remaining)}, BM25={len(bm25_retriever.records)}"
                )

            if bak_jsonl.exists():
                bak_jsonl.unlink(missing_ok=True)

            logger.info("Delete record %s: Còn lại %d (ChromaDB: %d, BM25: %d, Đồng bộ: %s)",
                        record_id, len(remaining), chroma_count, len(bm25_retriever.records), synced)

            return {
                "status": "SUCCESS",
                "message": f"Đã xóa hoàn toàn bản ghi '{record_id}' khỏi hệ thống.",
                "deleted": True,
                "remaining_count": len(remaining),
                "synced": True
            }
        except Exception as err:
            logger.error("Lỗi khi xóa bản ghi %s: %s. Đang khôi phục...", record_id, err)
            if bak_jsonl.exists():
                shutil.copy2(bak_jsonl, jsonl_path)
                bak_jsonl.unlink(missing_ok=True)
            try:
                BGEChromaRetriever(all_records).build_or_load_collection(force_reindex=True)
            except Exception:
                pass
            return {
                "status": "FAILED",
                "message": f"Lỗi xóa bản ghi: {err}. Đã khôi phục dữ liệu ban đầu.",
                "deleted": False,
                "remaining_count": len(all_records),
                "synced": False
            }

    def verify_sync(self) -> Dict[str, Any]:
        """Kiểm tra tính đồng bộ tuyệt đối giữa Source Data, BM25 và ChromaDB."""
        records = self.loader.load_from_jsonl() if self.loader.processed_jsonl_path.exists() else []
        bge = BGEChromaRetriever(records)
        bge.build_or_load_collection()
        bm25 = BM25Retriever(records)

        jsonl_count = len(records)
        chroma_count = bge.collection.count() if bge.collection else 0
        bm25_count = len(bm25.records)

        synced = (jsonl_count == chroma_count == bm25_count)
        return {
            "synced": synced,
            "source_data_count": jsonl_count,
            "chromadb_count": chroma_count,
            "bm25_count": bm25_count,
            "status": "IN_SYNC" if synced else "OUT_OF_SYNC"
        }

    # --- XÓA TOÀN BỘ KNOWLEDGE BASE (CLEAR KNOWLEDGE BASE) ---

    def clear_knowledge_base(
        self,
        engine: Optional[Any] = None,
        delete_managed_raw_files: bool = True,
    ) -> Dict[str, Any]:
        """Xóa toàn bộ dữ liệu Knowledge Base và đồng bộ toàn bộ pipeline RAG về trạng thái rỗng an toàn.

        Quy trình:
        1. Kiểm tra trạng thái hệ thống: từ chối nếu có tác vụ ingestion đang chạy.
        2. Khóa độc quyền qua IndexAccessCoordinator write_lock.
        3. Tạo snapshot backup (qa_records.jsonl.bak, sources_manifest.json.bak).
        4. Xóa/làm sạch ChromaDB collection.
        5. Làm sạch qa_records.jsonl (0 bản ghi).
        6. Xóa cache embeddings.npy nếu có.
        7. Xóa sạch danh sách Active Sources trong manifest (giữ {"sources": {}}).
        8. Xóa an toàn các bản sao tệp nguồn được quản lý bởi KB (bảo vệ tuyệt đối dictionary_en_vi.db, .gitkeep, v.v.).
        9. Đồng bộ in-memory và ChatEngine về trạng thái rỗng.
        10. Xác minh toàn bộ các thành phần đều phản ánh số lượng = 0.
        11. Tự động rollback nếu xảy ra bất kỳ lỗi nào.
        """
        from src.resource.manager import ResourceState, get_resource_manager
        rm = get_resource_manager()

        # 1. Từ chối nếu đang có tiến trình lập chỉ mục / ingestion đang chạy
        if rm.state in (ResourceState.INDEXING_CPU, ResourceState.INDEXING_GPU, ResourceState.RESTORING_CHAT):
            return {
                "status": "REJECTED",
                "message": "Không thể thực hiện xóa: Hệ thống đang có tiến trình lập chỉ mục/nạp dữ liệu đang chạy. Vui lòng đợi cho đến khi tác vụ hoàn tất hoặc được dừng an toàn.",
                "success": False,
                "deleted_records": 0,
                "deleted_sources": 0,
            }

        # 2. Khóa ghi độc quyền
        with rm.coordinator.write_lock(timeout=30.0) as acquired:
            if not acquired:
                return {
                    "status": "FAILED",
                    "message": "Không thể xin khóa độc quyền dữ liệu (Timeout). Vui lòng thử lại sau.",
                    "success": False,
                    "deleted_records": 0,
                    "deleted_sources": 0,
                }

            jsonl_path = self.loader.processed_jsonl_path
            manifest_path = self.manifest_path
            bak_jsonl = jsonl_path.with_suffix(".jsonl.bak")
            bak_manifest = manifest_path.with_suffix(".json.bak")

            original_records: List[QARecord] = []
            if jsonl_path.exists():
                try:
                    original_records = self.loader.load_from_jsonl()
                except Exception as e:
                    logger.warning("Không thể đọc qa_records.jsonl cũ: %s", e)

            original_manifest = self.load_manifest()
            deleted_raw_files: List[str] = []

            # 3. Tạo snapshot backup trước khi xóa
            try:
                if jsonl_path.exists():
                    shutil.copy2(jsonl_path, bak_jsonl)
                if manifest_path.exists():
                    shutil.copy2(manifest_path, bak_manifest)
            except Exception as bak_err:
                logger.warning("Không thể tạo snapshot backup trước khi xóa KB: %s", bak_err)

            try:
                # 4. Xóa ChromaDB collection & tạo lại collection rỗng
                bge_retriever = BGEChromaRetriever([])
                bge_retriever.clear_collection()

                # 5. Làm sạch qa_records.jsonl (ghi danh sách rỗng [])
                self.loader.save_to_jsonl([])

                # 6. Xóa cache embeddings.npy nếu có
                embeddings_path = getattr(settings, "EMBEDDINGS_PATH", None)
                if embeddings_path and Path(embeddings_path).exists():
                    try:
                        Path(embeddings_path).unlink(missing_ok=True)
                    except Exception as emb_err:
                        logger.warning("Không thể xóa embeddings.npy: %s", emb_err)

                # 7. Xóa sạch manifest
                empty_manifest = {"sources": {}}
                self.save_manifest(empty_manifest)

                # 8. Xóa an toàn tất cả các tệp nguồn đã nạp do KB quản lý
                if delete_managed_raw_files:
                    protected_exact_names = {
                        "dictionary_en_vi.db",
                        "dictionary_en_vi.db.backup",
                        ".gitkeep",
                        ".gitignore",
                        "mau_nhap_lieu_tuvung.xlsx"
                    }
                    if hasattr(settings, "DICTIONARY_DB_PATH") and settings.DICTIONARY_DB_PATH:
                        protected_exact_names.add(Path(settings.DICTIONARY_DB_PATH).name)

                    # Thu thập các tệp nguồn được ghi nhận trong manifest
                    source_paths_to_consider: Set[Path] = set()
                    for sinfo in original_manifest.get("sources", {}).values():
                        fpath_str = sinfo.get("file_path")
                        if fpath_str:
                            p = Path(fpath_str)
                            if p.exists() and p.is_file():
                                source_paths_to_consider.add(p)

                    # Thu thập TẤT CẢ các tệp dữ liệu đã nạp trong data/raw/
                    target_raw_dir = Path(settings.RAW_DATA_DIR)
                    if target_raw_dir.exists():
                        for p in target_raw_dir.iterdir():
                            if p.is_file():
                                source_paths_to_consider.add(p)

                    # Thực hiện xóa an toàn
                    for p in source_paths_to_consider:
                        # Kiểm tra an toàn tuyệt đối: không xóa tệp hệ thống cốt lõi
                        if p.name in protected_exact_names or p.name.startswith(".git"):
                            continue
                        if p.name == "dictionary_en_vi.db" or p.name.startswith("dictionary_en_vi.db"):
                            continue

                        # Phải nằm trong thư mục data hoặc temp của dự án (tuyệt đối không xóa src, .venv)
                        try:
                            resolved_p = p.resolve()
                            resolved_raw = target_raw_dir.resolve()
                            p_str = str(resolved_p).lower()
                            if "\\src\\" in p_str or "/src/" in p_str or "\\.venv\\" in p_str or "/.venv/" in p_str:
                                continue
                            if resolved_raw in resolved_p.parents or resolved_p.parent == resolved_raw or "temp" in p_str:
                                p.unlink(missing_ok=True)
                                deleted_raw_files.append(p.name)
                                logger.info("Clear KB: Đã xóa tệp nguồn đã nạp '%s'.", p.name)
                        except Exception as del_err:
                            logger.warning("Không thể xóa tệp nguồn '%s': %s", p, del_err)

                # 9. Làm sạch ChatEngine trong RAM nếu được cung cấp
                if engine is not None:
                    if hasattr(engine, "clear_knowledge_base"):
                        engine.clear_knowledge_base()
                    else:
                        engine.update_knowledge_base([])
                        if hasattr(engine, "tracker") and hasattr(engine.tracker, "clear"):
                            engine.tracker.clear()

                # 10. Xác minh tính đồng bộ tuyệt đối về 0
                chroma_count = bge_retriever.get_collection_count()
                jsonl_count = len(self.loader.load_from_jsonl()) if jsonl_path.exists() else 0
                active_sources_count = len(self.get_active_sources())
                bm25_count = len(BM25Retriever([]).records)

                if chroma_count != 0 or jsonl_count != 0 or active_sources_count != 0 or bm25_count != 0:
                    raise RuntimeError(
                        f"Xác minh sau khi xóa thất bại: ChromaDB={chroma_count}, JSONL={jsonl_count}, "
                        f"ActiveSources={active_sources_count}, BM25={bm25_count}"
                    )

                # 11. Xóa snapshot backups sau khi thành công
                if bak_jsonl.exists():
                    bak_jsonl.unlink(missing_ok=True)
                if bak_manifest.exists():
                    bak_manifest.unlink(missing_ok=True)

                logger.info(
                    "Clear KB thành công: Đã xóa %d bản ghi, %d nguồn, %d tệp nguồn. Tất cả chỉ mục về 0.",
                    len(original_records), len(original_manifest.get("sources", {})), len(deleted_raw_files)
                )

                return {
                    "status": "SUCCESS",
                    "message": "Đã xóa toàn bộ dữ liệu Knowledge Base và đồng bộ các chỉ mục về trạng thái rỗng thành công.",
                    "success": True,
                    "deleted_records": len(original_records),
                    "deleted_sources": len(original_manifest.get("sources", {})),
                    "deleted_raw_files": deleted_raw_files,
                    "jsonl_count": 0,
                    "chromadb_count": 0,
                    "bm25_count": 0,
                    "active_sources_count": 0,
                }

            except Exception as err:
                logger.error("Lỗi khi xóa Knowledge Base: %s. Đang kích hoạt ROLLBACK...", err)
                # ROLLBACK phục hồi dữ liệu ban đầu
                try:
                    if bak_jsonl.exists():
                        shutil.copy2(bak_jsonl, jsonl_path)
                        bak_jsonl.unlink(missing_ok=True)
                    if bak_manifest.exists():
                        shutil.copy2(bak_manifest, manifest_path)
                        bak_manifest.unlink(missing_ok=True)

                    if original_records:
                        BGEChromaRetriever(original_records).build_or_load_collection(force_reindex=True)
                    if engine is not None:
                        engine.update_knowledge_base(original_records)
                except Exception as rb_err:
                    logger.critical("Rollback sau lỗi xóa Knowledge Base thất bại: %s", rb_err)

                return {
                    "status": "FAILED",
                    "message": f"Lỗi xóa Knowledge Base: {err}. Hệ thống đã khôi phục dữ liệu ban đầu an toàn.",
                    "success": False,
                    "deleted_records": 0,
                    "deleted_sources": 0,
                    "error_detail": str(err),
                }
