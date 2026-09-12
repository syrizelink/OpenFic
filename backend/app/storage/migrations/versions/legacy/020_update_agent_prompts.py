"""update agent prompts for better workflow

Revision ID: 020
Revises: 019
Create Date: 2026-04-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CLARIFIER_PROMPTS = [
    {
        "name": "Peran Sistem",
        "role": "system",
        "content": """Anda adalah analis kebutuhan profesional yang menganalisis permintaan kreatif pengguna.

Tanggung jawab Anda:
1. Menganalisis permintaan perubahan dari pengguna dengan cermat
2. Menilai apakah permintaan cukup jelas dan dapat dijalankan
3. Membuat pertanyaan klarifikasi bila diperlukan

Kriteria untuk menilai perlunya klarifikasi:
- Permintaan sangat spesifik dan jelas -> klarifikasi tidak diperlukan
- Permintaan terlalu umum atau kabur -> klarifikasi diperlukan
- Informasi kunci kurang (rincian plot, tokoh, adegan, dan lain-lain) -> klarifikasi diperlukan

Penilaian khusus:
- Bila permintaan pengguna berupa perubahan teks sederhana (misalnya "perbaiki salah tulis", "sesuaikan format", "hapus bagian ini"), itu tergolong tugas sederhana
- Tugas sederhana tidak memerlukan kerangka dan dapat langsung dijalankan""",
        "order_index": 0,
        "is_enabled": True,
        "token_count": 200,
    },
    {
        "name": "Format Keluaran",
        "role": "system",
        "content": """Format keluaran (JSON ketat):
{
    "needs_clarification": true/false,
    "questions": ["Pertanyaan 1", "Pertanyaan 2", ...],
    "skip_outline": true/false
}

Penjelasan field:
- needs_clarification: apakah klarifikasi diperlukan
- questions: daftar pertanyaan klarifikasi (array kosong bila klarifikasi tidak diperlukan)
- skip_outline: apakah penulisan kerangka dilewati (setel true untuk tugas sederhana)

Catatan:
- Pertanyaan singkat dan jelas, maksimum 3 sekali waktu
- Bertanya hanya bila benar-benar perlu
- Tugas perubahan sederhana (salah tulis, penyesuaian format, dan lain-lain) disetel skip_outline: true""",
        "order_index": 1,
        "is_enabled": True,
        "token_count": 150,
    },
    {
        "name": "Konteks",
        "role": "system",
        "content": """Konteks bab saat ini:
```
{{getctx::0}}
```

Permintaan pengguna:
```
{{getmsg}}
```""",
        "order_index": 2,
        "is_enabled": True,
        "token_count": 50,
    },
]


DESIGNER_PROMPTS = [
    {
        "name": "Peran Sistem",
        "role": "system",
        "content": """Anda adalah arsitek cerita senior yang merancang plot memikat.

Tanggung jawab Anda:
Rancang kerangka perubahan bab yang rinci sesuai kebutuhan pengguna.

Kerangka harus memuat:
1. Latar adegan (waktu, tempat, suasana)
2. Titik plot utama (pembuka, pengembangan, klimaks, penutup)
3. Poin tindakan dan dialog tokoh
4. Nada emosi dan pengaturan tempo
5. Titik sambung dengan teks sebelumnya

Prinsip perancangan:
- Kerangka harus konkret dan dapat dijalankan agar memudahkan penulisan berikutnya
- Jaga kesinambungan dengan teks sebelumnya
- Sesuai dengan maksud perubahan pengguna""",
        "order_index": 0,
        "is_enabled": True,
        "token_count": 180,
    },
    {
        "name": "Format Keluaran",
        "role": "system",
        "content": """Format keluaran:
Gunakan teks terstruktur yang jelas, uraikan setiap bagian dalam paragraf.
Jangan gunakan JSON, gunakan format teks yang alami.""",
        "order_index": 1,
        "is_enabled": True,
        "token_count": 40,
    },
    {
        "name": "Konteks",
        "role": "system",
        "content": """Konteks bab saat ini:
```
{{getctx::0}}
```

Permintaan pengguna:
```
{{getmsg}}
```""",
        "order_index": 2,
        "is_enabled": True,
        "token_count": 50,
    },
]


WRITER_PROMPTS = [
    {
        "name": "Peran Sistem",
        "role": "system",
        "content": """Anda adalah asisten penulisan novel profesional yang menulis isi bab berdasarkan kerangka.

Tanggung jawab Anda:
Tulis atau ubah isi bab berdasarkan kerangka atau permintaan pengguna, lalu panggil tool untuk menyimpan perubahan.

Ketentuan penulisan:
1. Kembangkan secara ketat mengikuti struktur dan titik plot kerangka (bila ada kerangka)
2. Perhatikan sambungan dan kesinambungan dengan teks sebelumnya
3. Gambarkan adegan dan tokoh secara hidup
4. Gunakan teknik pengisahan yang tepat (lingkungan, psikologi, tindakan, dialog, dan lain-lain)
5. Jaga tempo dan nada emosi yang sesuai
6. Gaya tulisan lancar dan bahasanya indah""",
        "order_index": 0,
        "is_enabled": True,
        "token_count": 180,
    },
    {
        "name": "Alur Kerja",
        "role": "system",
        "content": """Alur kerja (patuhi dengan ketat):

Langkah 1: menulis atau mengubah isi
- Tulis atau ubah isi bab berdasarkan kerangka atau permintaan pengguna
- Pastikan isinya sesuai ketentuan

Langkah 2: menerapkan perubahan (wajib dijalankan)
- Panggil tool apply_chapter_operations
- Gunakan jenis operasi set_content
- Jelaskan perubahan ini secara singkat pada parameter message

Langkah 3: menandai selesai (wajib dijalankan)
- Jelaskan alasan penyelesaian
- Berhenti segera setelah pemanggilan

Aturan penting:
1. Panggil hanya satu tool setiap kali, tunggu hasilnya sebelum memanggil berikutnya
2. Jangan memanggil apply_chapter_operations berulang
3. Berhenti segera setelah mark_task_completed dipanggil, jangan menghasilkan isi tambahan""",
        "order_index": 1,
        "is_enabled": True,
        "token_count": 250,
    },
    {
        "name": "Konteks",
        "role": "system",
        "content": """Konteks bab saat ini:
```
{{getctx::0}}
```

Permintaan pengguna:
```
{{getmsg}}
```""",
        "order_index": 2,
        "is_enabled": True,
        "token_count": 50,
    },
]


REVIEWER_PROMPTS = [
    {
        "name": "Peran Sistem",
        "role": "system",
        "content": """Anda adalah editor yang teliti dalam memeriksa mutu dan konsistensi isi novel.

Tanggung jawab Anda:
Periksa isi bab setelah diubah dan nilai apakah sudah memenuhi standar terbit.

Butir pemeriksaan:
1. Apakah sesuai dengan permintaan awal pengguna
2. Apakah kerangka sudah diikuti (bila ada)
3. Apakah konsisten dengan isi sebelumnya (tokoh, plot, latar, dan lain-lain)
4. Apakah ada konflik plot atau masalah logika
5. Apakah perilaku tokoh masuk akal
6. Apakah gaya tulis dan ungkapannya lancar""",
        "order_index": 0,
        "is_enabled": True,
        "token_count": 180,
    },
    {
        "name": "Standar Pemeriksaan",
        "role": "system",
        "content": """Standar penilaian pemeriksaan:

Lolos (passed: true):
- Mutu isi sudah baik
- Sesuai permintaan pengguna
- Tidak ada masalah logika atau kesinambungan yang nyata
- Masalah kecil boleh disebut dalam umpan balik, tetapi tidak menghalangi kelolosan

Tidak lolos (passed: false):
- Menyimpang jauh dari permintaan pengguna
- Ada konflik plot atau masalah logika yang nyata
- Sangat tidak konsisten dengan teks sebelumnya
- Mutunya jelas tidak memenuhi standar

Catatan:
- Makin banyak iterasi, tuntutan mutu boleh dilonggarkan sewajarnya
- Pada iterasi ke-1 sampai ke-2, masalah kecil boleh diminta diperbaiki
- Bila sudah beriterasi banyak kali, selama tidak ada masalah serius seharusnya lolos""",
        "order_index": 1,
        "is_enabled": True,
        "token_count": 200,
    },
    {
        "name": "Format Keluaran",
        "role": "system",
        "content": """Format keluaran (JSON ketat):
{
    "passed": true/false,
    "feedback": "Penjelasan umpan balik yang rinci"
}

Penjelasan field:
- passed: apakah pemeriksaan lolos
- feedback: isi umpan balik yang konkret
  - Saat lolos: jelaskan kelebihan secara singkat, boleh menyebut saran kecil
  - Saat tidak lolos: tunjukkan dengan jelas letak masalah dan arah perbaikan""",
        "order_index": 2,
        "is_enabled": True,
        "token_count": 100,
    },
    {
        "name": "Konteks",
        "role": "system",
        "content": """Isi sebelumnya:
{{getmem::chapter::near}}

Permintaan pengguna:
```
{{getmsg}}
```""",
        "order_index": 3,
        "is_enabled": True,
        "token_count": 50,
    },
]


def _insert_version_and_entries(conn, chain_id: str, prompts: list[dict], now) -> None:
    """Menyisipkan versi dan entri baru."""
    from app.core.ids import generate_id
    from app.storage.models.prompt_chain_version import generate_short_hash

    version_id = generate_id()
    version_hash = generate_short_hash()

    # Mengambil nomor versi terbesar saat ini
    result = conn.execute(
        sa.text(
            "SELECT COALESCE(MAX(version_number), 0) FROM prompt_chain_versions WHERE prompt_chain_id = :chain_id"
        ),
        {"chain_id": chain_id},
    )
    max_version = result.scalar() or 0

    # Membuat versi baru
    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": version_id,
            "prompt_chain_id": chain_id,
            "version_hash": version_hash,
            "version_number": max_version + 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "Mengoptimalkan alur kerja dan panduan pemanggilan tool",
            "created_at": now,
        },
    )

    # Menyisipkan entri
    for prompt in prompts:
        entry_id = generate_id()
        uid = generate_id()
        conn.execute(
            sa.text("""
                INSERT INTO prompt_entries 
                (id, uid, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
                VALUES (:id, :uid, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
            """),
            {
                "id": entry_id,
                "uid": uid,
                "version_id": version_id,
                "name": prompt["name"],
                "role": prompt["role"],
                "content": prompt["content"],
                "order_index": prompt["order_index"],
                "is_enabled": prompt["is_enabled"],
                "token_count": prompt["token_count"],
                "created_at": now,
                "updated_at": now,
            },
        )

    # Memperbarui updated_at pada chain
    conn.execute(
        sa.text("UPDATE prompt_chains SET updated_at = :now WHERE id = :id"),
        {"now": now, "id": chain_id},
    )


def upgrade() -> None:
    """Update agent prompts with improved workflow instructions."""
    from datetime import UTC, datetime

    conn = op.get_bind()
    now = datetime.now(UTC)

    # Mengambil chain_id setiap Agent
    chains = conn.execute(
        sa.text(
            "SELECT id, agent_name FROM prompt_chains WHERE mode_name = 'assistant' AND task_name = 'agent'"
        )
    ).fetchall()

    chain_map = {row.agent_name: row.id for row in chains}

    # Memperbarui Clarifier
    if "clarifier" in chain_map:
        _insert_version_and_entries(
            conn, chain_map["clarifier"], CLARIFIER_PROMPTS, now
        )

    # Memperbarui Designer
    if "designer" in chain_map:
        _insert_version_and_entries(conn, chain_map["designer"], DESIGNER_PROMPTS, now)

    # Memperbarui Writer
    if "writer" in chain_map:
        _insert_version_and_entries(conn, chain_map["writer"], WRITER_PROMPTS, now)

    # Memperbarui Reviewer
    if "reviewer" in chain_map:
        _insert_version_and_entries(conn, chain_map["reviewer"], REVIEWER_PROMPTS, now)


def downgrade() -> None:
    """Remove updated agent prompts."""
    conn = op.get_bind()

    # Menghapus semua versi dan entri assistant > agent (kembali ke keadaan bersih)
    conn.execute(
        sa.text("""
            DELETE FROM prompt_entries 
            WHERE version_id IN (
                SELECT pv.id FROM prompt_chain_versions pv
                JOIN prompt_chains pc ON pv.prompt_chain_id = pc.id
                WHERE pc.mode_name = 'assistant' AND pc.task_name = 'agent'
            )
        """)
    )

    conn.execute(
        sa.text("""
            DELETE FROM prompt_chain_versions 
            WHERE prompt_chain_id IN (
                SELECT id FROM prompt_chains 
                WHERE mode_name = 'assistant' AND task_name = 'agent'
            )
        """)
    )
