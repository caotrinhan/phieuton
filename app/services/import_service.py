from datetime import datetime
from pathlib import Path

import pandas as pd

from ..time_utils import local_now


FILTERED_TYPES = ("fiber", "mytv")


def _required_columns(frame: pd.DataFrame, columns: list[str], source: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"File {source} thiếu cột: {', '.join(missing)}")


def _is_report_type(series: pd.Series) -> pd.Series:
    values = series.fillna("").astype(str).str.strip().str.lower()
    return (
        values.isin(FILTERED_TYPES)
        | values.str.contains("mesh", na=False)
        | values.str.contains("camera", na=False)
    )


def _hours_since(values: pd.Series, now: datetime, date_format: str | None = None) -> pd.Series:
    parsed = pd.to_datetime(values, format=date_format, errors="coerce")
    return ((now - parsed).dt.total_seconds() / 3600).round(1)


def load_filtered_tickets(ca_mau_path: Path, bac_lieu_path: Path, now: datetime | None = None) -> tuple[list[dict], int]:
    now = now or local_now()
    ca_mau = pd.read_excel(ca_mau_path, skiprows=1)
    bac_lieu = pd.read_excel(bac_lieu_path, skiprows=1)

    _required_columns(
        ca_mau,
        ["LOAI TB", "TRANGTHAI_HD", "TEN_LOAIHD", "DONVI_XULY_PHIEU", "MA_TB", "TEN_TB", "NGAY LAPPHIEU"],
        "Cà Mau",
    )
    _required_columns(
        bac_lieu,
        ["Loaihinh Tb", "Trangthai Hd", "Ten Loaihd", "Tendv Ld", "Ma Tb", "Ten Tb", "Ngay Yc"],
        "Bạc Liêu",
    )

    ca_mau_mask = (
        _is_report_type(ca_mau["LOAI TB"])
        & (ca_mau["TRANGTHAI_HD"].fillna("").astype(str).str.strip() == "Đã giao thi công")
        & ca_mau["TEN_LOAIHD"].fillna("").astype(str).str.strip().isin(["Lắp đặt mới", "Khôi phục thanh lý", "Dịch chuyển"])
        & ca_mau["DONVI_XULY_PHIEU"].fillna("").astype(str).str.strip().str.startswith("Tổ Kỹ thuật Địa bàn")
    )
    ca_mau = ca_mau.loc[ca_mau_mask].copy()
    ca_mau["age_hours"] = _hours_since(ca_mau["NGAY LAPPHIEU"], now)
    ca_mau["province"] = "Cà Mau"
    ca_mau["unit"] = ca_mau["DONVI_XULY_PHIEU"]
    ca_mau["contract_type"] = ca_mau["TEN_LOAIHD"]
    ca_mau["status"] = ca_mau["TRANGTHAI_HD"]
    ca_mau["equipment_type"] = ca_mau["LOAI TB"]
    ca_mau["subscriber_code"] = ca_mau["MA_TB"]
    ca_mau["subscriber_name"] = ca_mau["TEN_TB"]
    ca_mau["address"] = ""
    ca_mau["phone"] = ""
    ca_mau["request_at"] = pd.to_datetime(ca_mau["NGAY LAPPHIEU"], errors="coerce")

    bac_lieu_mask = (
        _is_report_type(bac_lieu["Loaihinh Tb"])
        & (bac_lieu["Trangthai Hd"].fillna("").astype(str).str.strip() == "Đã giao thi công")
        & bac_lieu["Ten Loaihd"].fillna("").astype(str).str.strip().isin(["Lắp đặt mới", "Khôi phục thanh lý", "Dịch chuyển"])
        & bac_lieu["Tendv Ld"].fillna("").astype(str).str.strip().str.startswith("Tổ Kỹ thuật Địa bàn")
    )
    bac_lieu = bac_lieu.loc[bac_lieu_mask].copy()
    bac_lieu["age_hours"] = _hours_since(bac_lieu["Ngay Yc"], now, "%d/%m/%Y %H:%M:%S")
    bac_lieu["province"] = "Bạc Liêu"
    bac_lieu["unit"] = bac_lieu["Tendv Ld"]
    bac_lieu["contract_type"] = bac_lieu["Ten Loaihd"]
    bac_lieu["status"] = bac_lieu["Trangthai Hd"]
    bac_lieu["equipment_type"] = bac_lieu["Loaihinh Tb"]
    bac_lieu["subscriber_code"] = bac_lieu["Ma Tb"]
    bac_lieu["subscriber_name"] = bac_lieu["Ten Tb"]
    bac_lieu["address"] = bac_lieu["Diachi Ld"]
    bac_lieu["phone"] = bac_lieu["So Dt"]
    bac_lieu["request_at"] = pd.to_datetime(bac_lieu["Ngay Yc"], format="%d/%m/%Y %H:%M:%S", errors="coerce")

    merged = pd.concat([ca_mau, bac_lieu], ignore_index=True)
    merged = merged[merged["age_hours"].notna() & (merged["age_hours"] > 48)]
    records = []
    for row in merged.to_dict("records"):
        records.append(
            {
                "province": str(row["province"]),
                "unit": str(row["unit"]),
                "contract_type": str(row["contract_type"]),
                "status": str(row["status"]),
                "equipment_type": str(row["equipment_type"]),
                "subscriber_code": str(row["subscriber_code"]),
                "subscriber_name": str(row["subscriber_name"]),
                "address": str(row.get("address", "") or ""),
                "phone": str(row.get("phone", "") or ""),
                "request_at": row["request_at"].to_pydatetime() if pd.notna(row["request_at"]) else now,
                "age_hours": float(row["age_hours"]),
            }
        )
    return records, len(ca_mau) + len(bac_lieu)
