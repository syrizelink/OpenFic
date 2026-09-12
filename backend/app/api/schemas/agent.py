# -*- coding: utf-8 -*-
"""
Agent API Schemas.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.agent_runtime.types import DEFAULT_AGENT_MAX_ITERATIONS
from app.api.schemas.task import TaskMessage
from app.models.clients.model_params import ReasoningEffort

class AgentSessionCreateRequest(BaseModel):
    """Permintaan pembuatan sesi Agent."""

    project_id: str = Field(..., description="ID proyek")
    model_id: str = Field(..., description="ID model")
    max_iterations: int = Field(
        default=DEFAULT_AGENT_MAX_ITERATIONS,
        ge=1,
        le=DEFAULT_AGENT_MAX_ITERATIONS,
        description="Jumlah iterasi maksimum",
    )
    agent_key: str = Field(
        default="build",
        description="Identitas agen utama, dipakai untuk memilih primary agent yang aktif",
    )
    reasoning_effort: ReasoningEffort | None = Field(
        default=None,
        description="Intensitas penalaran sesi saat ini, hanya tersedia untuk model reasoning",
    )

    model_config = {"extra": "forbid"}


class AgentSessionCreateResponse(BaseModel):
    """Respons pembuatan sesi Agent."""

    session_id: str = Field(..., description="ID sesi")
    project_id: str = Field(..., description="ID proyek")
    status: str = Field(..., description="Status")
    task_id: str = Field(..., description="ID tugas yang dibuat")
    task_title: str = Field(..., description="Judul tugas yang dibuat")
    task_created_at: str = Field(..., description="Waktu pembuatan tugas")
    task_updated_at: str = Field(..., description="Waktu pembaruan tugas")
    agent_key: str = Field(..., description="Identitas agen utama yang dipakai sesi saat ini")


class AgentAttachmentResponse(BaseModel):
    """Metadata lampiran gambar Agent."""

    id: str = Field(..., description="ID lampiran")
    session_id: str = Field(..., description="ID sesi pemilik")
    storage_name: str = Field(..., description="Path relatif penyimpanan di sisi server")
    file_name: str = Field(..., description="Nama berkas asli")
    mime_type: str = Field(..., description="Tipe MIME gambar")
    size_bytes: int = Field(..., description="Ukuran berkas")
    width: int = Field(..., description="Lebar gambar")
    height: int = Field(..., description="Tinggi gambar")
    url: str = Field(..., description="Alamat tampilan gambar")


class AgentSendMessageRequest(BaseModel):
    """Permintaan pengiriman pesan pengguna."""

    message: str = Field(default="", description="Isi pesan pengguna")
    attachments: list[str] = Field(default_factory=list, description="Daftar ID lampiran gambar")
    model_id: str | None = Field(default=None, description="ID model yang dipakai pada eksekusi putaran berikutnya")
    agent_key: str | None = Field(default=None, description="Identitas agen utama yang dipakai pada eksekusi putaran berikutnya")
    reasoning_effort: ReasoningEffort | None = Field(
        default=None,
        description="Intensitas penalaran putaran ini, hanya tersedia untuk model reasoning",
    )


class AgentPendingMessageResponse(BaseModel):
    """Pesan pengguna yang mengantre saat proses berjalan."""

    message_id: str = Field(..., description="ID pesan yang menunggu diproses")
    content: str = Field(..., description="Isi pesan yang menunggu diproses")
    created_at: str = Field(..., description="Waktu masuk ke pending")


class AgentSendMessageResponse(BaseModel):
    """Respons pengiriman pesan pengguna."""

    success: bool = Field(..., description="Apakah berhasil")
    session_id: str = Field(..., description="ID sesi")
    message: str = Field(..., description="Pesan hasil")
    queued: bool = Field(default=False, description="Apakah masuk ke antrean pending")
    model_updated: bool = Field(default=False, description="Apakah model eksekusi putaran berikutnya sudah diperbarui")
    pending_message: AgentPendingMessageResponse | None = Field(
        default=None,
        description="Payload pesan yang masuk ke pending",
    )


class AgentCancelPendingMessageRequest(BaseModel):
    """Permintaan pembatalan pesan pengguna yang menunggu diproses."""

    message_id: str = Field(..., description="ID pending message yang akan dibatalkan")


class AgentCancelPendingMessageResponse(BaseModel):
    """Respons pembatalan pesan pengguna yang menunggu diproses."""

    success: bool = Field(..., description="Apakah berhasil")
    session_id: str = Field(..., description="ID sesi")
    message_id: str = Field(..., description="ID pending message yang dibatalkan")
    restored_message_content: str = Field(..., description="Isi pesan yang dipulihkan ke kotak masukan")


class AgentCompactionResponse(BaseModel):
    """Respons kompresi manual."""

    success: bool = Field(..., description="Apakah berhasil")
    session_id: str = Field(..., description="ID sesi")
    compaction_id: str = Field(..., description="ID catatan kompresi")
    start_seq: int = Field(..., description="Nomor urut pesan awal jendela kompresi")
    end_seq: int = Field(..., description="Nomor urut pesan akhir jendela kompresi")
    source_input_tokens: int = Field(default=0, description="Jumlah token masukan jendela sumber")
    summary_tokens: int = Field(default=0, description="Jumlah token ringkasan")


class AgentQuestionAnswerRequest(BaseModel):
    """Permintaan pengiriman jawaban pertanyaan klarifikasi Agent."""

    action_id: str = Field(..., description="ID permintaan klarifikasi")
    answer: list["AgentQuestionAnswerItem"] = Field(default_factory=list, description="Jawaban pertanyaan klarifikasi")
    skipped: bool = Field(default=False, description="Apakah pertanyaan ini diabaikan")


class AgentQuestionAnswerItem(BaseModel):
    """Jawaban satu pertanyaan klarifikasi."""

    question: str = Field(..., min_length=1, description="Judul pertanyaan")
    answer: str = Field(..., min_length=1, description="Label opsi atau masukan pengguna")


class AgentToolApprovalRequest(BaseModel):
    """Permintaan persetujuan tool Agent."""

    approval_id: str = Field(..., description="ID persetujuan")
    approved: bool = Field(..., description="Apakah disetujui")


class AgentInterruptResponseItem(BaseModel):
    """Respons satu interupsi paralel."""

    interrupt_id: str = Field(..., description="ID interupsi LangGraph")
    action_type: str = Field(..., description="Tipe respons interupsi")
    approval_id: str | None = Field(default=None, description="ID persetujuan tool")
    approved: bool | None = Field(default=None, description="Apakah tool disetujui")
    action_id: str | None = Field(default=None, description="ID permintaan klarifikasi")
    answer: list[AgentQuestionAnswerItem] | None = Field(
        default=None,
        description="Jawaban pertanyaan klarifikasi",
    )
    skipped: bool | None = Field(default=None, description="Apakah pertanyaan ini diabaikan")


class AgentInterruptResumeRequest(BaseModel):
    """Memulihkan seluruh interupsi paralel pada putaran yang sama."""

    batch_id: str = Field(..., description="ID batch interupsi")
    responses: list[AgentInterruptResponseItem] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Seluruh respons interupsi pada batch ini",
    )


class AgentToolMetadataResponse(BaseModel):
    """Metadata izin tool Agent."""

    key: str = Field(..., description="Kunci konfigurasi izin")
    is_readonly: bool = Field(..., description="Apakah hanya baca")


class AgentSessionStateResponse(BaseModel):
    """Respons status sesi."""

    session_id: str = Field(..., description="ID sesi")
    state: dict = Field(..., description="Informasi status")
    is_running: bool = Field(default=False, description="Apakah sesi masih punya tugas yang berjalan di latar belakang")
    interrupts: list[dict] = Field(default_factory=list, description="Interupsi tertunda yang dapat dipulihkan")


class AgentChangeLineResponse(BaseModel):
    """Satu baris perubahan konten Agent."""

    type: str = Field(description="Tipe baris perubahan: context, added, atau removed")
    before_line_number: int | None = Field(default=None, description="Nomor baris sebelum perubahan")
    after_line_number: int | None = Field(default=None, description="Nomor baris setelah perubahan")
    text: str = Field(default="", description="Isi baris perubahan")


class AgentChangeSectionResponse(BaseModel):
    """Perubahan konten Agent."""

    type: str = Field(description="Tipe perubahan: content")
    lines: list[AgentChangeLineResponse] = Field(default_factory=list, description="Baris perubahan konten")


class AgentChangeItemResponse(BaseModel):
    """Satu item perubahan konten Agent."""

    key: str = Field(description="Kunci entitas perubahan")
    kind: str = Field(description="Tipe entitas")
    title: str = Field(description="Judul entitas")
    title_before: str | None = Field(default=None, description="Teks judul sebelum perubahan")
    title_after: str | None = Field(default=None, description="Teks judul setelah perubahan")
    operation: str = Field(description="Operasi perubahan")
    path: list[str] = Field(default_factory=list, description="Path hierarki pemilik entitas")
    sections: list[AgentChangeSectionResponse] = Field(default_factory=list, description="Segmen Diff")
    added: int = Field(default=0, description="Jumlah baris yang ditambahkan")
    removed: int = Field(default=0, description="Jumlah baris yang dihapus")
    source_message_id: str = Field(description="ID pesan tool sumber")
    source: str = Field(description="Sumber perubahan: primary, subagent, atau session")
    child_run_id: str | None = Field(default=None, description="ID sub-run sumber")
    request_id: str | None = Field(default=None, description="ID permintaan sub-run sumber")
    agent_key: str | None = Field(default=None, description="Identitas subagen sumber")
    agent_number: str | None = Field(default=None, description="Nomor subagen sumber")
    revision_id: str | None = Field(default=None, description="ID revision pemilik")


class AgentChangeSummaryResponse(BaseModel):
    """Ringkasan perubahan konten Agent."""

    item_count: int = Field(default=0, description="Jumlah item perubahan")
    added: int = Field(default=0, description="Jumlah baris yang ditambahkan")
    removed: int = Field(default=0, description="Jumlah baris yang dihapus")
    items: list[AgentChangeItemResponse] = Field(default_factory=list, description="Item perubahan")


class AgentSubagentRunChangesResponse(BaseModel):
    """Perubahan yang dihasilkan satu permintaan subagent."""

    child_run_id: str = Field(description="ID sub-run")
    child_thread_id: str = Field(description="ID sub-thread")
    request_id: str | None = Field(default=None, description="ID permintaan sub-run")
    child_user_message_id: str | None = Field(default=None, description="ID pesan pengguna sub-run")
    agent_key: str = Field(description="Identitas subagen")
    agent_number: str | None = Field(default=None, description="Nomor subagen")
    changes: AgentChangeSummaryResponse = Field(description="Perubahan dari permintaan subagent ini")


class AgentTurnChangesResponse(BaseModel):
    """Perubahan satu turn pada sesi utama."""

    revision_id: str = Field(description="ID revision turn ini")
    user_message_id: str | None = Field(default=None, description="ID pesan pengguna yang memicu turn")
    user_message_seq: int | None = Field(default=None, description="Nomor urut pesan pengguna yang memicu turn")
    changes: AgentChangeSummaryResponse = Field(description="Perubahan lengkap pada turn ini")
    subagent_runs: list[AgentSubagentRunChangesResponse] = Field(
        default_factory=list,
        description="Perubahan subagent di bawah turn ini",
    )


class AgentSessionChangesResponse(BaseModel):
    """Perubahan lengkap sesi utama beserta subagent-nya."""

    session_id: str = Field(description="ID sesi Agent")
    turns: list[AgentTurnChangesResponse] = Field(default_factory=list, description="Perubahan yang dikelompokkan per turn")
    session_changes: AgentChangeSummaryResponse = Field(description="Perubahan seluruh sesi")


class ActiveSubagentStateResponse(BaseModel):
    """Baris status hanya-baca subagen aktif di bawah sesi induk."""

    child_run_id: str = Field(..., description="ID sub-run")
    child_thread_id: str = Field(..., description="ID sub-thread")
    agent_key: str = Field(..., description="Identitas subagen")
    agent_number: str | None = Field(default=None, description="Nomor subagen")
    status: str = Field(..., description="Status sub-run")
    queued_messages: int = Field(..., description="Jumlah permintaan yang menunggu diproses")
    is_active: bool = Field(..., description="Apakah sub-run masih aktif")
    pending_approval: dict | None = Field(
        default=None,
        description="Payload persetujuan tool yang sedang menunggu",
    )


class SubagentSessionResponse(BaseModel):
    """Detail sesi subagen."""

    child_run_id: str = Field(..., description="ID sub-run")
    parent_session_id: str = Field(..., description="ID sesi induk")
    parent_task_id: str = Field(..., description="ID tugas induk")
    parent_thread_id: str = Field(..., description="ID thread induk")
    child_thread_id: str = Field(..., description="ID sub-thread")
    agent_key: str = Field(..., description="Identitas subagen")
    agent_number: str | None = Field(default=None, description="Nomor subagen")
    dispatch_id: str = Field(..., description="ID dispatch")
    tool_call_id: str = Field(..., description="ID pemanggilan tool")
    status: str = Field(..., description="Status sub-run")
    queued_messages: int = Field(..., description="Jumlah permintaan yang menunggu diproses")
    is_active: bool = Field(..., description="Apakah sub-run aktif")
    is_running: bool = Field(..., description="Apakah sub-run masih berjalan di latar belakang")
    request: dict = Field(default_factory=dict, description="Payload permintaan sub-run")
    result: dict | None = Field(default=None, description="Payload hasil sub-run")
    pending_approval: dict | None = Field(default=None, description="Payload persetujuan yang menunggu diproses pengguna")
    error: str | None = Field(default=None, description="Pesan error")
    metadata: dict = Field(default_factory=dict, description="Metadata sub-run")
    token_input: int = Field(default=0, description="Token masukan terakhir pada sub-sesi saat ini")
    token_output: int = Field(default=0, description="Token keluaran terakhir pada sub-sesi saat ini")
    token_cache: int = Field(default=0, description="Token cache terakhir pada sub-sesi saat ini")
    cost: float = Field(default=0.0, description="Biaya terakhir pada sub-sesi saat ini (dolar AS)")
    context_input_tokens: int = Field(
        default=0,
        description="Token masukan konteks terakhir pada sub-sesi saat ini",
    )
    context_length: int = Field(default=0, description="Ukuran jendela konteks sub-sesi saat ini")
    started_at: datetime | None = Field(default=None, description="Waktu mulai")
    completed_at: datetime | None = Field(default=None, description="Waktu selesai")
    created_at: datetime = Field(..., description="Waktu pembuatan")
    updated_at: datetime = Field(..., description="Waktu pembaruan")
    messages: list[TaskMessage] = Field(
        default_factory=list,
        description="Pesan transcript sub-thread",
    )


class AgentRollbackRequest(BaseModel):
    """Permintaan rollback Agent."""

    revision_id: str = Field(..., description="ID revision tujuan")

    model_config = {"extra": "forbid"}


class AgentRollbackResponse(BaseModel):
    """Respons rollback Agent."""

    success: bool = Field(..., description="Apakah berhasil")
    session_id: str = Field(..., description="ID sesi")
    revision_id: str | None = Field(None, description="rollback revision ID")
    affected_chapters: list[str] = Field(
        default_factory=list, description="Daftar ID bab yang terpengaruh"
    )
    affected_notes: list[str] = Field(
        default_factory=list, description="Daftar ID catatan yang terpengaruh"
    )
    affected_note_categories: list[str] = Field(
        default_factory=list, description="Daftar ID kategori catatan yang terpengaruh"
    )
    affected_world_entries: list[str] = Field(
        default_factory=list, description="Daftar ID entri buku dunia yang terpengaruh"
    )
    restored_message_content: str = Field(..., description="Isi pesan yang dipulihkan")
    restored_attachments: list[AgentAttachmentResponse] = Field(
        default_factory=list,
        description="Lampiran gambar yang dipulihkan ke kotak masukan",
    )


class AgentForkRequest(BaseModel):
    """Permintaan fork sesi Agent."""

    source_revision_id: str = Field(..., description="ID revision pesan pengguna sumber fork")
    model_id: str = Field(..., description="ID model yang dipakai setelah sesi di-fork")
    reasoning_effort: ReasoningEffort | None = Field(
        default=None,
        description="Intensitas penalaran yang dipakai setelah sesi di-fork",
    )

    model_config = {"extra": "forbid"}


class AgentForkResponse(BaseModel):
    """Respons fork sesi Agent."""

    session_id: str = Field(..., description="ID sesi Agent baru")
    task_id: str = Field(..., description="ID Task baru")
    task_title: str = Field(..., description="Judul Task baru")
    task_created_at: str = Field(..., description="Waktu pembuatan Task baru")
    task_updated_at: str = Field(..., description="Waktu pembaruan Task baru")


class AgentCancelResponse(BaseModel):
    """Respons pembatalan Agent."""

    success: bool = Field(..., description="Apakah berhasil")
    session_id: str = Field(..., description="ID sesi")
    message: str = Field(..., description="Pesan pembatalan")
