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
    """Quản lý quy trình xác thực, nạp dữ liệu từ Excel và cập nhật chỉ mục tìm kiếm."""

    def __init__(self, loader: Optional[QALoader] = None):
        self.loader = loader or QALoader()

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
        excel_path: Path,
        mode: str = "append",
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> IngestionResult:
        """Thực thi nạp dữ liệu từ tệp Excel và cập nhật các chỉ mục tri thức.

        Args:
            excel_path: Đường dẫn tệp Excel đầu vào.
            mode: 'append' (bổ sung) hoặc 'replace' (làm mới toàn bộ).
            progress_callback: Hàm nhận callback (tiến_độ_0_đến_1, thông_điệp).

        Returns:
            IngestionResult: Chi tiết kết quả nạp dữ liệu.
        """
        start_time = time.perf_counter()

        def _notify(pct: float, msg: str):
            logger.info("[%d%%] %s", int(pct * 100), msg)
            if progress_callback:
                progress_callback(pct, msg)

        _notify(0.05, f"Bắt đầu đọc và giải mã tệp Excel: {excel_path.name}...")

        # 1. Đọc và chuẩn hóa bản ghi từ file Excel
        try:
            incoming_records = self.loader.load_from_excel(excel_path)
        except Exception as err:
            return IngestionResult(
                status="FAILED",
                total_incoming=0,
                newly_added=0,
                duplicates_skipped=0,
                total_active=0,
                elapsed_seconds=round(time.perf_counter() - start_time, 2),
                mode=mode,
                message=f"Lỗi đọc dữ liệu từ Excel: {err}"
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
                message="Không tìm thấy bản ghi câu hỏi - câu trả lời hợp lệ nào trong tệp Excel."
            )

        # Thống kê bản ghi theo từng sheet
        sheet_info: Dict[str, int] = {}
        for r in incoming_records:
            sheet_info[r.sheet] = sheet_info.get(r.sheet, 0) + 1

        _notify(0.25, f"Đã trích xuất {len(incoming_records)} bản ghi từ {len(sheet_info)} sheet.")

        # 2. Xử lý theo chế độ (Mode)
        bge_retriever = BGEChromaRetriever(incoming_records)

        if mode == "append":
            _notify(0.35, "Đang kiểm tra trùng lặp với dữ liệu hiện có...")
            # Lấy dữ liệu hiện tại
            existing_records = []
            if self.loader.processed_jsonl_path.exists():
                existing_records = self.loader.load_from_jsonl()

            # Hợp nhất và loại bỏ trùng lặp
            merged_records, added_count, dup_count = self.loader.merge_records(
                existing_records, incoming_records
            )

            # Lọc ra danh sách bản ghi mới cần bổ sung vector
            existing_sigs = {
                (r.question.strip().lower(), r.answer.strip().lower())
                for r in existing_records
            }
            records_to_add = [
                r for r in incoming_records
                if (r.question.strip().lower(), r.answer.strip().lower()) not in existing_sigs
            ]

            _notify(0.50, f"Phát hiện {added_count} bản ghi mới ({dup_count} bản ghi đã có từ trước).")

            if records_to_add:
                _notify(0.60, f"Đang mã hóa vector BGE-M3 cho {len(records_to_add)} bản ghi mới...")
                bge_retriever.records = merged_records
                bge_retriever.rec_map = {r.record_id: r for r in merged_records}
                bge_retriever.add_records(records_to_add)

            # Lưu lại tập dữ liệu sau khi merge vào JSONL
            _notify(0.85, "Đang cập nhật tệp lưu trữ qa_records.jsonl...")
            self.loader.save_to_jsonl(merged_records)

            final_records = merged_records
            total_active = len(merged_records)
            sample_words = [r.word for r in records_to_add if r.word][:10]

        else:  # mode == "replace"
            _notify(0.40, f"Chế độ làm mới hoàn toàn: Xóa DB cũ và chuẩn bị mã hóa {len(incoming_records)} vector...")
            bge_retriever.records = incoming_records
            bge_retriever.rec_map = {r.record_id: r for r in incoming_records}
            bge_retriever.build_or_load_collection(force_reindex=True)

            _notify(0.85, "Đang cập nhật tệp lưu trữ qa_records.jsonl...")
            self.loader.save_to_jsonl(incoming_records)

            final_records = incoming_records
            added_count = len(incoming_records)
            dup_count = 0
            total_active = len(incoming_records)
            sample_words = [r.word for r in incoming_records if r.word][:10]

        # 3. Hoàn tất
        _notify(1.0, f"Hoàn tất nạp dữ liệu! Tổng cộng: {total_active:,} bản ghi đang hoạt động.")
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
                f"Thời gian xử lý: {elapsed} giây."
            )
        )
