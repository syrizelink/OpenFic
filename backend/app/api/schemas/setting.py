# -*- coding: utf-8 -*-
"""
Setting API Schemas - Model permintaan/respons pengaturan.
"""

from pydantic import BaseModel, Field


class AgentToolPermissionItem(BaseModel):
    """Item pengaturan izin tool Agent."""

    tool_name: str = Field(..., description="Nama tool")
    mode: str = Field(..., description="Mode izin: allow / ask / deny")


class AgentSettingsLockResponse(BaseModel):
    """Apakah sesi Agent sedang mengunci pengaturan terkait."""

    is_locked: bool = Field(..., description="Apakah ada sesi Agent atau subagen yang belum berakhir")


class AuditDetailsStorageResponse(BaseModel):
    """Ringkasan penyimpanan detail pemanggilan LLM."""

    detail_records_count: int = Field(description="Jumlah catatan pemanggilan yang memuat detail")
    detail_bytes: int = Field(description="Estimasi jumlah bita UTF-8 field detail")


class ClearAuditDetailsResponse(BaseModel):
    """Hasil pengosongan detail pemanggilan LLM."""

    cleared_records_count: int = Field(description="Jumlah catatan pemanggilan yang detailnya sudah dikosongkan")
    cleared_detail_bytes: int = Field(description="Estimasi jumlah bita UTF-8 field detail yang sudah dikosongkan")


class SettingsResponse(BaseModel):
    """Respons pengaturan."""

    language: str = Field(default="id", description="Bahasa")
    theme: str = Field(default="light", description="Tema")
    font_family: str = Field(default="system-ui", description="Fon")
    code_font_family: str = Field(default="ui-monospace", description="Fon kode")
    base_font_size: int = Field(default=14, description="Ukuran fon dasar (px)")
    editor_font_size: int = Field(default=16, description="Ukuran fon editor (px)")
    default_model: str = Field(default="", description="ID model default")
    light_model: str = Field(default="", description="ID model ringan")
    default_embedding_model: str = Field(default="", description="ID model Embedding default")
    index_mode: str = Field(default="off", description="Mode pengaktifan indeks: off/all/selected")
    index_enabled_projects: list[str] = Field(
        default_factory=list, description="Daftar ID proyek yang mengaktifkan indeks (berlaku saat mode=selected)"
    )
    index_chunk_size: int = Field(default=800, description="Ukuran chunk indeks")
    index_chunk_overlap: int = Field(default=100, description="Tumpang tindih chunk indeks")
    index_auto_strategy: str = Field(
        default="off", description="Strategi indeks otomatis: immediate/agent_decided/off"
    )
    index_rerank_enabled: bool = Field(
        default=False,
        description="Apakah rerank sebagai pengurutan kedua pada pencarian diaktifkan",
    )
    default_rerank_model: str = Field(default="", description="ID model Rerank default")
    agent_bypass_tool_approval: bool = Field(
        default=False,
        description="Apakah persetujuan tool Agent diloloskan secara global",
    )
    agent_tool_permissions: list[AgentToolPermissionItem] = Field(
        default_factory=list, description="Pengaturan izin tool Agent"
    )
    audit_persist_details: bool = Field(default=False, description="Apakah detail pemanggilan LLM dipersistenkan")
    compress_system_prompts: bool = Field(
        default=False,
        description="Apakah pesan system yang berurutan digabung menjadi satu",
    )
    telemetry_enabled: bool = Field(
        default=True,
        description="Apakah telemetri error PostHog diaktifkan",
    )
    editor_auto_indent: bool = Field(
        default=True,
        description=(
            "Saat pindah baris, bila paragraf ini dimulai dengan dua spasi lebar, apakah prefiks "
            "yang sama ditambahkan otomatis ke paragraf berikutnya"
        ),
    )
    editor_auto_convert_punctuation: bool = Field(
        default=False,
        description="Apakah tanda baca setengah lebar yang diketik otomatis diubah menjadi lebar penuh",
    )
    editor_auto_pair_symbols: bool = Field(
        default=False,
        description="Apakah simbol penutup dilengkapi otomatis saat simbol pembuka dari pasangan diketik",
    )
    editor_show_line_numbers: bool = Field(
        default=False,
        description="Apakah nomor baris ditampilkan pada editor bab",
    )


class SettingsUpdateRequest(BaseModel):
    """Permintaan pembaruan pengaturan."""

    language: str | None = Field(default=None, description="Bahasa")
    theme: str | None = Field(default=None, description="Tema")
    font_family: str | None = Field(default=None, description="Fon")
    code_font_family: str | None = Field(default=None, description="Fon kode")
    base_font_size: int | None = Field(default=None, description="Ukuran fon dasar (px)")
    editor_font_size: int | None = Field(default=None, description="Ukuran fon editor (px)")
    default_model: str | None = Field(default=None, description="ID model default")
    light_model: str | None = Field(default=None, description="ID model ringan")
    default_embedding_model: str | None = Field(
        default=None,
        description="ID model Embedding default",
    )
    index_mode: str | None = Field(default=None, description="Mode pengaktifan indeks")
    index_enabled_projects: list[str] | None = Field(
        default=None, description="Daftar ID proyek yang mengaktifkan indeks"
    )
    index_chunk_size: int | None = Field(default=None, description="Ukuran chunk indeks")
    index_chunk_overlap: int | None = Field(default=None, description="Tumpang tindih chunk indeks")
    index_auto_strategy: str | None = Field(default=None, description="Strategi indeks otomatis")
    index_rerank_enabled: bool | None = Field(
        default=None,
        description="Apakah rerank sebagai pengurutan kedua pada pencarian diaktifkan",
    )
    default_rerank_model: str | None = Field(
        default=None,
        description="ID model Rerank default",
    )
    agent_bypass_tool_approval: bool | None = Field(
        default=None,
        description="Apakah persetujuan tool Agent diloloskan secara global",
    )
    agent_tool_permissions: list[AgentToolPermissionItem] | None = Field(
        default=None, description="Pengaturan izin tool Agent"
    )
    audit_persist_details: bool | None = Field(
        default=None, description="Apakah detail pemanggilan LLM dipersistenkan"
    )
    compress_system_prompts: bool | None = Field(
        default=None,
        description="Apakah pesan system yang berurutan digabung menjadi satu",
    )
    telemetry_enabled: bool | None = Field(
        default=None,
        description="Apakah telemetri error PostHog diaktifkan",
    )
    editor_auto_indent: bool | None = Field(
        default=None,
        description=(
            "Saat pindah baris, bila paragraf ini dimulai dengan dua spasi lebar, apakah prefiks "
            "yang sama ditambahkan otomatis ke paragraf berikutnya"
        ),
    )
    editor_auto_convert_punctuation: bool | None = Field(
        default=None,
        description="Apakah tanda baca setengah lebar yang diketik otomatis diubah menjadi lebar penuh",
    )
    editor_auto_pair_symbols: bool | None = Field(
        default=None,
        description="Apakah simbol penutup dilengkapi otomatis saat simbol pembuka dari pasangan diketik",
    )
    editor_show_line_numbers: bool | None = Field(
        default=None,
        description="Apakah nomor baris ditampilkan pada editor bab",
    )


class WebSearchProviderField(BaseModel):
    """Definisi field tambahan untuk provider pencarian web."""

    key: str = Field(..., description="Kunci parameter tambahan (disimpan ke extras)")
    field_type: str = Field(..., description="Tipe field: text / select")
    required: bool = Field(default=False, description="Apakah wajib diisi")
    options: list[str] = Field(default_factory=list, description="Nilai pilihan untuk tipe select")


class WebSearchProviderInfo(BaseModel):
    """Metadata provider pencarian web."""

    name: str = Field(..., description="Nama provider")
    requires_api_key: bool = Field(..., description="Apakah memerlukan API Key")
    fields: list[WebSearchProviderField] = Field(
        default_factory=list, description="Definisi field tambahan"
    )


class WebSearchSettingsResponse(BaseModel):
    """Respons pengaturan pencarian web (tanpa API Key teks terang)."""

    enabled: bool = Field(..., description="Apakah pencarian web diaktifkan")
    provider: str = Field(..., description="Nama provider saat ini")
    has_api_keys: dict[str, bool] = Field(
        default_factory=dict, description="Apakah API Key setiap provider sudah dikonfigurasi"
    )
    max_results: int = Field(..., description="Batas jumlah hasil pencarian")
    domain_filters: list[str] = Field(default_factory=list, description="Daftar filter nama domain")
    extras: dict[str, str] = Field(default_factory=dict, description="Parameter tambahan")
    trust_proxy_environment: bool = Field(
        default=True,
        description="Apakah variabel lingkungan proxy dipercaya",
    )
    bypass_ssrf_protection: bool = Field(
        default=False,
        description="Apakah proteksi SSRF pada pembacaan halaman web dilewati",
    )


class WebSearchSettingsUpdateRequest(BaseModel):
    """Permintaan pembaruan pengaturan pencarian web."""

    enabled: bool | None = Field(default=None, description="Apakah pencarian web diaktifkan")
    provider: str | None = Field(default=None, description="Nama provider")
    api_key: str | None = Field(
        default=None,
        description=(
            "API Key provider saat ini: tidak dikirim berarti tetap; string kosong berarti dihapus; "
            "nilai non-kosong berarti diperbarui"
        ),
    )
    extras: dict[str, str] | None = Field(
        default=None, description="Parameter tambahan (diganti seluruhnya, tidak dikirim berarti tetap)"
    )
    max_results: int | None = Field(
        default=None, ge=1, le=20, description="Batas jumlah hasil pencarian (1-20)"
    )
    domain_filters: list[str] | None = Field(
        default=None, description="Daftar nama domain yang perlu dikecualikan dari hasil pencarian"
    )
    trust_proxy_environment: bool | None = Field(
        default=None,
        description="Apakah variabel lingkungan proxy dipercaya",
    )
    bypass_ssrf_protection: bool | None = Field(
        default=None,
        description="Apakah proteksi SSRF pada pembacaan halaman web dilewati",
    )
