"""Module điều phối nạp dữ liệu tri thức từ Excel vào hệ thống RAG (Ingestion Manager).

Hỗ trợ 2 chế độ:
- 'append' (Khuyên dùng): Bổ sung bản ghi mới, tự động phát hiện và bỏ qua trùng lặp,
  chỉ mã hóa vector BGE-M3 cho các từ mới (chỉ mất vài giây).
- 'replace': Xóa sạch và tái lập toàn bộ cơ sở dữ liệu vector ChromaDB và chỉ mục BM25.
"""

import logging
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from config.settings import settings
from src.core.exceptions import DataLoadError
from src.core.models import QARecord
from src.data.loader import QALoader
from src.retriever.bge_chroma import BGEChromaRetriever
from src.retriever.bm25_retriever import BM25Retriever

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Kết quả chi tiết của phiên nạp dữ liệu."""
    status: str
    total_incoming: int
    newly_added: int
    duplicates_skipped: int
    total_active: int
    elapsed_seconds: float
    mode: str
    sheets_info: Dict[str, int] = field(default_factory=dict)
    sample_words: List[str] = field(default_factory=list)
    message: str = ""


class IngestionManager:
    """Quản lý quy trình xác thực, nạp dữ liệu đa định dạng và cập nhật chỉ mục tìm kiếm."""

    def __init__(self, loader: Optional[QALoader] = None):
        self.loader = loader or QALoader()
        from src.data.loaders.router import FileLoaderRouter
        self.router = FileLoaderRouter()

    def inspect_file(self, file_path: Path) -> Dict:
        """Kiểm tra tính hợp lệ và cấu trúc sơ bộ của bất kỳ tệp dữ liệu nào trước khi nạp."""
        if not file_path.exists():
            return {"valid": False, "error": f"Không tìm thấy tệp tại: {file_path}"}

        ext = file_path.suffix.lower().lstrip(".")
        if ext == "xlsx":
            return self.inspect_excel(file_path)

        val_res = self.router.validate_file(file_path)
        if not val_res.is_valid:
            return {"valid": False, "error": val_res.error_message or "Tệp không hợp lệ."}

        return {
            "valid": True,
            "file_name": file_path.name,
            "file_size_kb": round(file_path.stat().st_size / 1024, 2),
            "sheets": {ext.upper(): 1},
            "estimated_rows": 1,
        }

    def inspect_excel(self, excel_path: Path) -> Dict:
        """Kiểm tra tính hợp lệ và cấu trúc sơ bộ của tệp Excel trước khi nạp."""
        if not excel_path.exists():
            return {"valid": False, "error": f"Không tìm thấy tệp tại: {excel_path}"}

        if not zipfile.is_zipfile(excel_path):
            return {"valid": False, "error": "Tệp không phải định dạng Excel (.xlsx) hợp lệ."}

        try:
            with zipfile.ZipFile(excel_path, "r") as z:
                sheets = self.loader._get_sheet_info(z)
                sst = self.loader._read_shared_strings(z)
                sheet_stats = {}
                total_preview_rows = 0

                for s_name, s_xml in sheets:
                    rows = self.loader._parse_sheet_rows(z, s_xml, sst)
                    sheet_stats[s_name] = len(rows)
                    total_preview_rows += len(rows)

            return {
                "valid": True,
                "file_name": excel_path.name,
                "file_size_kb": round(excel_path.stat().st_size / 1024, 2),
                "sheets": sheet_stats,
                "estimated_rows": total_preview_rows,
            }
        except Exception as err:
            return {"valid": False, "error": f"Lỗi phân tích tệp Excel: {err}"}

    def ingest(
        self,
        file_path: Optional[Path] = None,
        excel_path: Optional[Path] = None,
        mode: str = "append",
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> IngestionResult:
        """Thực thi nạp dữ liệu (từ Excel hoặc các định dạng TXT, PDF, CSV, JSON, DOCX...) và đồng bộ chỉ mục.

        Args:
            file_path: Đường dẫn tệp đầu vào (hỗ trợ cả 8 định dạng).
            excel_path: Bí danh tương thích ngược cho file_path.
            mode: 'append'/'add' (bổ sung / update theo ID) hoặc 'replace' (làm mới toàn bộ).
            progress_callback: Hàm nhận callback (tiến_độ_0_đến_1, thông_điệp).

        Returns:
            IngestionResult: Chi tiết kết quả nạp dữ liệu.
        """
        start_time = time.perf_counter()
        target_path = Path(file_path or excel_path or settings.RAW_EXCEL_PATH)
        norm_mode = mode.lower()
        is_replace = (norm_mode == "replace")

        def _notify(pct: float, msg: str):
            logger.info("[%d%%] %s", int(pct * 100), msg)
            if progress_callback:
                progress_callback(pct, msg)

        _notify(0.05, f"Bắt đầu đọc và giải mã tệp dữ liệu: {target_path.name}...")

        # 1. Đọc và chuẩn hóa bản ghi
        try:
            ext = target_path.suffix.lower().lstrip(".")
            if ext == "xlsx":
                incoming_records = self.loader.load_from_excel(target_path)
            else:
                incoming_records = self.router.load_file(target_path)
        except Exception as err:
            return IngestionResult(
                status="FAILED",
                total_incoming=0,
                newly_added=0,
                duplicates_skipped=0,
                total_active=0,
                elapsed_seconds=round(time.perf_counter() - start_time, 2),
                mode=mode,
                message=f"Lỗi đọc dữ liệu từ '{target_path.name}': {err}"
            )

        if not incoming_records:
            return IngestionResult(
                status="FAILED",
                total_incoming=0,
                newly_added=0,
                duplicates_skipped=0,
                total_active=0,
                elapsed_seconds=round(time.perf_counter() - start_time, 2),
                mode=mode,
                message=f"Không tìm thấy bản ghi câu hỏi - câu trả lời hợp lệ nào trong '{target_path.name}'."
            )

        # Thống kê bản ghi theo từng sheet/nguồn
        sheet_info: Dict[str, int] = {}
        for r in incoming_records:
            sheet_info[r.sheet] = sheet_info.get(r.sheet, 0) + 1

        _notify(0.25, f"Đã trích xuất {len(incoming_records)} bản ghi từ {len(sheet_info)} nguồn.")

        # 2. Xử lý theo chế độ (Mode: ADD / REPLACE)
        if not is_replace:
            _notify(0.35, "Đang kiểm tra trùng lặp và Stable ID với dữ liệu hiện có...")
            existing_records = []
            if self.loader.processed_jsonl_path.exists():
                existing_records = self.loader.load_from_jsonl()

            # Hợp nhất theo Stable ID (Update nếu ID tồn tại, Add nếu mới, Bỏ qua nếu duplicate)
            merged_records, added_count, updated_count, dup_count = self.loader.merge_records(
                existing_records, incoming_records, return_updated=True
            )

            # Lọc danh sách bản ghi cần cập nhật hoặc thêm mới vào ChromaDB
            records_to_upsert = [
                r for r in incoming_records
                if any(m.record_id == r.record_id for m in merged_records)
            ]

            _notify(0.50, f"Bổ sung: {added_count} mới, Cập nhật: {updated_count}, Trùng lặp: {dup_count}.")

            bge_retriever = BGEChromaRetriever(merged_records)
            if records_to_upsert:
                _notify(0.60, f"Đang cập nhật vector BGE-M3 cho {len(records_to_upsert)} bản ghi...")
                bge_retriever.upsert_records(records_to_upsert)

            # Đồng bộ lưu lại vào JSONL
            _notify(0.85, "Đang cập nhật tệp lưu trữ qa_records.jsonl và BM25...")
            self.loader.save_to_jsonl(merged_records)

            # Đồng bộ BM25
            bm25_retriever = BM25Retriever(merged_records)

            final_records = merged_records
            total_active = len(merged_records)
            sample_words = [r.word for r in incoming_records if r.word][:10]

        else:  # mode == "replace"
            _notify(0.40, f"Chế độ làm mới hoàn toàn: Xóa DB cũ và chuẩn bị mã hóa {len(incoming_records)} vector...")
            bge_retriever = BGEChromaRetriever(incoming_records)
            bge_retriever.build_or_load_collection(force_reindex=True)

            _notify(0.85, "Đang cập nhật tệp lưu trữ qa_records.jsonl và BM25...")
            self.loader.save_to_jsonl(incoming_records)

            bm25_retriever = BM25Retriever(incoming_records)

            final_records = incoming_records
            added_count = len(incoming_records)
            dup_count = 0
            total_active = len(incoming_records)
            sample_words = [r.word for r in incoming_records if r.word][:10]

        # 3. Kiểm tra tính đồng bộ
        chroma_count = bge_retriever.collection.count() if bge_retriever.collection else 0
        bm25_count = len(bm25_retriever.records)
        synced = (total_active == chroma_count == bm25_count)

        _notify(1.0, f"Hoàn tất nạp dữ liệu! Tổng cộng: {total_active:,} bản ghi đang hoạt động (Đồng bộ: {synced}).")
        elapsed = round(time.perf_counter() - start_time, 2)

        return IngestionResult(
            status="SUCCESS",
            total_incoming=len(incoming_records),
            newly_added=added_count,
            duplicates_skipped=dup_count,
            total_active=total_active,
            elapsed_seconds=elapsed,
            mode=mode,
            sheets_info=sheet_info,
            sample_words=sample_words,
            message=(
                f"Nạp thành công {added_count} bản ghi mới "
                f"(bỏ qua {dup_count} bản ghi trùng). "
                f"Tổng số bản ghi trong kho: {total_active:,}. "
                f"Thời gian xử lý: {elapsed} giây. "
                f"Trạng thái đồng bộ: {'Đồng bộ 100%' if synced else 'Chưa đồng bộ'}"
            )
        )

    def delete_record(self, record_id: str) -> Dict[str, Any]:
        """Xóa 1 bản ghi và đảm bảo tính đồng bộ tuyệt đối giữa Source JSONL, ChromaDB và BM25."""
        all_records = self.loader.load_from_jsonl() if self.loader.processed_jsonl_path.exists() else []
        found = False
        remaining = []
        for r in all_records:
            if r.record_id == record_id:
                found = True
            else:
                remaining.append(r)

        if not found:
            return {"status": "NOT_FOUND", "message": f"Không tìm thấy bản ghi {record_id}", "deleted": False}

        bge_retriever = BGEChromaRetriever(all_records)
        bge_retriever.delete_records([record_id])

        self.loader.save_to_jsonl(remaining)
        bm25_retriever = BM25Retriever(remaining)

        chroma_count = bge_retriever.collection.count() if bge_retriever.collection else 0
        synced = (len(remaining) == chroma_count == len(bm25_retriever.records))

        return {
            "status": "SUCCESS",
            "message": f"Đã xóa hoàn toàn bản ghi {record_id}.",
            "deleted": True,
            "remaining_count": len(remaining),
            "synced": synced
        }

    def verify_sync(self) -> Dict[str, Any]:
        """Kiểm tra đồng bộ giữa Source Data, BM25 và ChromaDB."""
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

