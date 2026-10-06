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
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from config.settings import settings
from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import QALoader
from src.data.loaders.base import compute_file_hash
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
        """Lấy danh sách các nguồn dữ liệu đang hoạt động."""
        manifest = self.load_manifest()
        return [
            s for s in manifest.get("sources", {}).values()
            if s.get("status") == "ACTIVE"
        ]

    def is_duplicate_file(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Kiểm tra mã băm SHA-256 đã tồn tại trong manifest nguồn đang hoạt động chưa."""
        manifest = self.load_manifest()
        for src in manifest.get("sources", {}).values():
            if src.get("status") == "ACTIVE" and src.get("file_hash") == file_hash:
                return src
        return None

    # --- PIPELINE NẠP BATCH ĐA TỆP ---

    def ingest_batch(
        self,
        files: List[Path],
        progress_callback: Optional[Callable[[str, float, FileIngestionResult], None]] = None,
        batch_size: int = 16,
    ) -> BatchIngestionReport:
        """Thực thi pipeline Batch Multi-File Ingestion với xử lý độc lập từng tệp.

        Args:
            files: Danh sách đường dẫn tệp cần nạp.
            progress_callback: Hàm nhận callback (thông_điệp, tiến_độ_0_đến_1, kết_quả_tệp_hiện_tại).
            batch_size: Kích thước batch embedding BGE-M3 (an toàn cho CPU/RAM).

        Returns:
            BatchIngestionReport: Báo cáo tổng thể toàn bộ batch.
        """
        batch_start_time = time.perf_counter()
        total_files = len(files)
        file_results: List[FileIngestionResult] = []

        # 1. Đọc dữ liệu hiện có để phục vụ kiểm tra trùng lặp bản ghi
        existing_records: List[QARecord] = []
        if self.loader.processed_jsonl_path.exists():
            try:
                existing_records = self.loader.load_from_jsonl()
            except Exception:
                existing_records = []

        existing_signatures: Set[Tuple[str, str]] = {
            (r.question.strip().lower(), r.answer.strip().lower())
            for r in existing_records
        }
        existing_ids: Set[str] = {r.record_id for r in existing_records}

        newly_accumulated_records: List[QARecord] = []
        manifest = self.load_manifest()
        sources_dict = manifest.setdefault("sources", {})
        seen_batch_hashes: Dict[str, str] = {}

        # 2. Xử lý tuần tự từng tệp một cách độc lập
        for file_idx, file_path in enumerate(files, 1):
            file_start = time.perf_counter()
            f_res = FileIngestionResult(
                file_name=file_path.name,
                file_path=str(file_path.resolve()),
                file_type=file_path.suffix.lower().lstrip("."),
                file_size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                file_hash="",
                status=FileStatus.QUEUED,
            )

            # Thông báo tiến độ
            pct = (file_idx - 1) / max(total_files, 1)
            if progress_callback:
                progress_callback(f"Bắt đầu xử lý {file_path.name}...", pct, f_res)

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
                    progress_callback(f"Lỗi tệp {file_path.name}: {f_res.reason}", pct, f_res)
                continue

            f_res.file_hash = val_res.file_hash
            f_res.file_size_bytes = val_res.file_size_bytes

            # Bước 2.2: Kiểm tra tệp trùng lặp (Duplicate File Check)
            duplicate_src_name = seen_batch_hashes.get(val_res.file_hash)
            if not duplicate_src_name:
                duplicate_src = self.is_duplicate_file(val_res.file_hash)
                if duplicate_src:
                    duplicate_src_name = duplicate_src.get("file_name")

            if duplicate_src_name:
                f_res.status = FileStatus.SKIPPED
                f_res.reason = f"Duplicate file: Trùng nội dung với tệp '{duplicate_src_name}' đã nạp."
                f_res.action = "Bỏ qua tệp để tránh nhân bản dữ liệu."
                f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)
                file_results.append(f_res)
                if progress_callback:
                    progress_callback(f"Bỏ qua {file_path.name} (Trùng tệp)", pct, f_res)
                continue

            seen_batch_hashes[val_res.file_hash] = file_path.name

            # Bước 2.3: Phân tích & Trích xuất nội dung (Processing)
            f_res.status = FileStatus.PROCESSING
            try:
                raw_extracted = self.router.load_file(
                    file_path=file_path,
                    file_hash=val_res.file_hash,
                    start_index=len(existing_records) + len(newly_accumulated_records) + 1
                )
            except Exception as err:
                f_res.status = FileStatus.FAILED
                f_res.reason = f"Lỗi phân tích nội dung tệp: {err}"
                f_res.action = "Không thể đọc cấu trúc dữ liệu, bỏ qua tệp."
                f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)
                file_results.append(f_res)
                if progress_callback:
                    progress_callback(f"Lỗi đọc {file_path.name}: {err}", pct, f_res)
                continue

            f_res.records_extracted = len(raw_extracted)
            if not raw_extracted:
                f_res.status = FileStatus.FAILED
                f_res.reason = "Không trích xuất được bản ghi văn bản / Q&A hợp lệ nào."
                f_res.action = "Tệp không chứa nội dung tra cứu phù hợp."
                f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)
                file_results.append(f_res)
                if progress_callback:
                    progress_callback(f"Không có bản ghi trong {file_path.name}", pct, f_res)
                continue

            # Bước 2.4: Kiểm tra trùng lặp bản ghi nội dung (Duplicate Records Filtering)
            file_valid_records: List[QARecord] = []
            for r in raw_extracted:
                sig = (r.question.strip().lower(), r.answer.strip().lower())
                if sig in existing_signatures:
                    f_res.duplicates_skipped += 1
                    continue

                # Đảm bảo record_id không trùng
                if r.record_id in existing_ids:
                    r.record_id = f"BATCH_{len(existing_ids) + 1:04d}"

                existing_signatures.add(sig)
                existing_ids.add(r.record_id)
                file_valid_records.append(r)

            if not file_valid_records:
                f_res.status = FileStatus.SKIPPED
                f_res.reason = f"Toàn bộ {f_res.records_extracted} bản ghi đã có sẵn trong kho tri thức."
                f_res.action = "Không cần thêm bản ghi mới."
                f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)
                file_results.append(f_res)
                if progress_callback:
                    progress_callback(f"Bản ghi trong {file_path.name} đều đã tồn tại", pct, f_res)
                continue

            # Tệp có bản ghi mới hợp lệ
            f_res.status = FileStatus.INDEXING
            f_res.records_added = len(file_valid_records)
            f_res.record_ids = [r.record_id for r in file_valid_records]
            f_res.elapsed_seconds = round(time.perf_counter() - file_start, 2)

            newly_accumulated_records.extend(file_valid_records)
            file_results.append(f_res)

        # 3. Lập chỉ mục ChromaDB & BM25 đồng nhất (Batch Indexing)
        chromadb_status = "UNCHANGED"
        bm25_status = "UNCHANGED"

        if newly_accumulated_records:
            if progress_callback:
                progress_callback(
                    f"Đang lập chỉ mục vector BGE-M3 cho {len(newly_accumulated_records)} bản ghi mới...",
                    0.85,
                    None
                )

            try:
                # 3.1. Thêm vector vào ChromaDB
                bge_retriever = BGEChromaRetriever(existing_records + newly_accumulated_records)
                added_vecs = bge_retriever.add_records(newly_accumulated_records, batch_size=batch_size)
                chromadb_status = "UPDATED"

                # 3.2. Cập nhật qa_records.jsonl
                all_records = existing_records + newly_accumulated_records
                self.loader.save_to_jsonl(all_records)

                # 3.3. Tái lập chỉ mục BM25
                bm25_retriever = BM25Retriever(all_records)
                bm25_status = "UPDATED"

                # 3.4. Đánh dấu trạng thái SUCCESS cho các tệp đã index
                for res in file_results:
                    if res.status == FileStatus.INDEXING:
                        res.status = FileStatus.SUCCESS
                        res.reason = f"Đã nạp thành công {res.records_added} bản ghi vào kho tri thức."
                        res.action = "Sẵn sàng tra cứu."

                        # Đăng ký vào manifest
                        source_id = f"SRC_{res.file_hash[:12]}"
                        sources_dict[source_id] = {
                            "source_id": source_id,
                            "file_name": res.file_name,
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

            except Exception as err:
                logger.error("Lỗi khi lập chỉ mục batch: %s", err)
                chromadb_status = f"FAILED: {err}"
                bm25_status = "FAILED"
                for res in file_results:
                    if res.status == FileStatus.INDEXING:
                        res.status = FileStatus.FAILED
                        res.reason = f"Lỗi lập chỉ mục: {err}"

        # 4. Tính toán kết quả tổng thể (Batch Status: SUCCESS / PARTIAL SUCCESS / FAILED)
        success_cnt = sum(1 for r in file_results if r.status == FileStatus.SUCCESS)
        skipped_cnt = sum(1 for r in file_results if r.status == FileStatus.SKIPPED)
        failed_cnt = sum(1 for r in file_results if r.status == FileStatus.FAILED)

        if success_cnt == total_files:
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

        # 3. Xóa vector trong ChromaDB
        bge_retriever = BGEChromaRetriever(all_records)
        bge_retriever.delete_records(list(ids_to_delete))

        # 4. Loại bỏ bản ghi khỏi qa_records.jsonl
        remaining_records = [r for r in all_records if r.record_id not in ids_to_delete]
        self.loader.save_to_jsonl(remaining_records)

        # 5. Tái lập chỉ mục BM25
        bm25_retriever = BM25Retriever(remaining_records)

        # 6. Cập nhật manifest
        if target_sid and target_sid in sources_dict:
            sources_dict[target_sid]["status"] = "DELETED"
            sources_dict[target_sid]["deleted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self.save_manifest(manifest)

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

        return {
            "status": "SUCCESS",
            "message": f"Đã tái lập chỉ mục toàn bộ {len(all_records):,} bản ghi.",
            "total": len(all_records)
        }
