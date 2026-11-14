"""Bounded tabular ingestion. No executable formulas, macros, or inferred units."""

import csv
import hashlib
import io
import re
import zipfile
from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20_000
MAX_COLUMNS = 50
FIELDS = ("station", "timestamp", "pollutant", "value", "unit", "duration_hours")
ALIASES = {
    "station": {"station", "location", "site", "ward", "stationname", "monitor", "area"},
    "timestamp": {"timestamp", "datetime", "date", "time", "observedat", "samplingdate"},
    "pollutant": {"pollutant", "parameter", "species"},
    "value": {"value", "concentration", "reading", "measurement"},
    "unit": {"unit", "units", "measurementunit"},
    "duration_hours": {"durationhours", "averaginghours", "averagingperiodhours"},
}


def key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def infer_mapping(columns: list[str]) -> dict:
    return {
        field: next((c for c in columns if key(c) in aliases), "")
        for field, aliases in ALIASES.items()
    }


def parse_table(content: bytes, filename: str) -> dict:
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Provide a nonempty table no larger than 5 MB.")
    extension = Path(filename).suffix.lower()
    if extension == ".xlsx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(x.file_size for x in archive.infolist()) > 30 * 1024 * 1024:
                    raise ValueError("Workbook expands beyond the 30 MB safety limit.")
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
            if len(workbook.worksheets) != 1:
                workbook.close()
                raise ValueError("Upload a single worksheet; export the intended sheet separately.")
            sheet = workbook.worksheets[0]
            matrix = []
            for row in sheet.iter_rows():
                if len(matrix) > MAX_ROWS or len(row) > MAX_COLUMNS:
                    raise ValueError("Limit: 20,000 data rows and 50 columns.")
                if any(cell.data_type == "f" for cell in row):
                    raise ValueError(
                        "Formula cells are not accepted. Export calculated values first."
                    )
                matrix.append(["" if c.value is None else str(c.value) for c in row])
            workbook.close()
        except (
            zipfile.BadZipFile,
            KeyError,
            OSError,
            ParseError,
            InvalidFileException,
            DefusedXmlException,
        ) as exc:
            raise ValueError("The workbook is unreadable.") from exc
    elif extension in {".csv", ".tsv", ".txt"}:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Save the table as UTF-8 CSV or TSV.") from exc
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        matrix = []
        try:
            for row in csv.reader(io.StringIO(text), dialect, strict=True):
                if len(matrix) > MAX_ROWS or len(row) > MAX_COLUMNS:
                    raise ValueError("Limit: 20,000 data rows and 50 columns.")
                matrix.append(row)
        except csv.Error as exc:
            raise ValueError("Malformed delimited table; check quoting and separators.") from exc
    else:
        raise ValueError("Supported formats: CSV, TSV, TXT, and single-sheet XLSX.")
    if len(matrix) < 2:
        raise ValueError("A header and at least one data row are required.")
    columns = [str(c).strip() for c in matrix[0]]
    if not all(columns) or len(set(columns)) != len(columns):
        raise ValueError("Column names must be nonempty and unique.")
    rows = []
    for number, row in enumerate(matrix[1:], 2):
        if not any(str(c).strip() for c in row):
            continue
        if len(row) != len(columns):
            raise ValueError(f"Source row {number} has {len(row)} cells; expected {len(columns)}.")
        if any(len(str(c)) > 500 for c in row):
            raise ValueError(f"Source row {number} contains a cell longer than 500 characters.")
        rows.append({"source_row": number, "cells": dict(zip(columns, row))})
    if not rows:
        raise ValueError("No nonempty data rows found.")
    return {
        "filename": Path(filename).name[:120],
        "sha256": hashlib.sha256(content).hexdigest(),
        "columns": columns,
        "rows": rows,
        "mapping": infer_mapping(columns),
    }
