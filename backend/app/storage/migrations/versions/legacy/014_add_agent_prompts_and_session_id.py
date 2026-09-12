"""add agent prompts and session id to tasks

Revision ID: 014
Revises: 013
Create Date: 2026-02-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add agent prompts and agent_session_id to tasks table."""
    from datetime import UTC, datetime
    from app.core.ids import generate_id

    conn = op.get_bind()
    now = datetime.now(UTC)

    # 1. Menambahkan kolom agent_session_id ke tabel tasks
    op.add_column(
        "tasks",
        sa.Column("agent_session_id", sa.String(), nullable=True),
    )
    op.create_index("ix_tasks_agent_session_id", "tasks", ["agent_session_id"])

    # 2. Membuat rantai prompt assistant > agent > clarifier
    clarifier_chain_id = generate_id()
    clarifier_version_id = generate_id()
    clarifier_version_hash = generate_id()[:8]

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": clarifier_chain_id,
            "mode_name": "assistant",
            "task_name": "agent",
            "agent_name": "clarifier",
            "created_at": now,
            "updated_at": now,
        },
    )

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": clarifier_version_id,
            "prompt_chain_id": clarifier_chain_id,
            "version_hash": clarifier_version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "Versi awal",
            "created_at": now,
        },
    )

    # Entri prompt Clarifier
    clarifier_entries = [
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": clarifier_version_id,
            "name": "Peran Sistem",
            "role": "system",
            "content": """Anda adalah analis kebutuhan profesional yang menganalisis permintaan kreatif pengguna.

Tugas Anda:
1. Menganalisis permintaan pengguna dengan cermat
2. Menilai apakah permintaan sudah jelas dan lengkap
3. Membuat pertanyaan klarifikasi bila permintaan kabur atau kurang informasi kunci

Kriteria penilaian:
- Bila permintaan pengguna sangat spesifik dan jelas, klarifikasi tidak diperlukan
- Bila permintaan pengguna terlalu umum atau kabur, klarifikasi diperlukan
- Bila informasi kunci soal plot, tokoh, atau adegan kurang, klarifikasi diperlukan""",
            "order_index": 0,
            "is_enabled": True,
            "token_count": 150,
        },
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": clarifier_version_id,
            "name": "Format Keluaran",
            "role": "user",
            "content": """Format keluaran (JSON ketat):
{
    "needs_clarification": true/false,
    "questions": ["Pertanyaan 1", "Pertanyaan 2", ...]
}

Catatan:
- Bila klarifikasi tidak diperlukan, questions harus berupa array kosong
- Pertanyaan harus singkat dan jelas, maksimum 3 pertanyaan sekali waktu
- Bertanya hanya bila benar-benar perlu, jangan berlebihan""",
            "order_index": 1,
            "is_enabled": True,
            "token_count": 100,
        },
    ]

    for entry in clarifier_entries:
        conn.execute(
            sa.text("""
                INSERT INTO prompt_entries 
                (id, uid, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
                VALUES (:id, :uid, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
            """),
            {**entry, "created_at": now, "updated_at": now},
        )

    # 3. Membuat rantai prompt assistant > agent > designer
    designer_chain_id = generate_id()
    designer_version_id = generate_id()
    designer_version_hash = generate_id()[:8]

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": designer_chain_id,
            "mode_name": "assistant",
            "task_name": "agent",
            "agent_name": "designer",
            "created_at": now,
            "updated_at": now,
        },
    )

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": designer_version_id,
            "prompt_chain_id": designer_chain_id,
            "version_hash": designer_version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "Versi awal",
            "created_at": now,
        },
    )

    # Entri prompt Designer
    designer_entries = [
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": designer_version_id,
            "name": "Peran Sistem",
            "role": "system",
            "content": """Anda adalah arsitek cerita senior yang merancang plot memikat.

Tugas Anda:
Rancang kerangka bab yang rinci sesuai kebutuhan pengguna.

Kerangka harus memuat:
1. Latar adegan (waktu, tempat, suasana)
2. Titik plot utama (pembuka, pengembangan, klimaks, penutup)
3. Poin tindakan dan dialog tokoh
4. Nada emosi dan pengaturan tempo
5. Titik sambung dengan teks sebelumnya""",
            "order_index": 0,
            "is_enabled": True,
            "token_count": 150,
        },
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": designer_version_id,
            "name": "Format Keluaran",
            "role": "user",
            "content": """Format keluaran:
Gunakan teks terstruktur yang jelas, uraikan setiap bagian dalam paragraf.
Jangan gunakan JSON, gunakan format teks yang alami.""",
            "order_index": 1,
            "is_enabled": True,
            "token_count": 50,
        },
    ]

    for entry in designer_entries:
        conn.execute(
            sa.text("""
                INSERT INTO prompt_entries 
                (id, uid, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
                VALUES (:id, :uid, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
            """),
            {**entry, "created_at": now, "updated_at": now},
        )

    # 4. Membuat rantai prompt assistant > agent > writer
    writer_chain_id = generate_id()
    writer_version_id = generate_id()
    writer_version_hash = generate_id()[:8]

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": writer_chain_id,
            "mode_name": "assistant",
            "task_name": "agent",
            "agent_name": "writer",
            "created_at": now,
            "updated_at": now,
        },
    )

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": writer_version_id,
            "prompt_chain_id": writer_chain_id,
            "version_hash": writer_version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "Versi awal",
            "created_at": now,
        },
    )

    # Entri prompt Writer
    writer_entries = [
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": writer_version_id,
            "name": "Peran Sistem",
            "role": "system",
            "content": """Anda adalah novelis unggul yang menulis isi cerita memikat.

Tugas Anda:
Tulis isi bab yang lengkap berdasarkan kerangka yang diberikan.

Ketentuan penulisan:
1. Kembangkan secara ketat mengikuti struktur dan titik plot kerangka
2. Perhatikan sambungan dan kesinambungan dengan teks sebelumnya
3. Gambarkan adegan dan tokoh secara hidup
4. Gunakan teknik pengisahan yang tepat (lingkungan, psikologi, tindakan, dialog, dan lain-lain)
5. Jaga tempo dan nada emosi yang sesuai
6. Gaya tulisan lancar dan bahasanya indah""",
            "order_index": 0,
            "is_enabled": True,
            "token_count": 150,
        },
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": writer_version_id,
            "name": "Format Keluaran",
            "role": "user",
            "content": """Format keluaran:
Keluarkan langsung isi teks bab, tanpa memuat judul, kerangka, atau informasi tambahan lain.""",
            "order_index": 1,
            "is_enabled": True,
            "token_count": 30,
        },
    ]

    for entry in writer_entries:
        conn.execute(
            sa.text("""
                INSERT INTO prompt_entries 
                (id, uid, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
                VALUES (:id, :uid, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
            """),
            {**entry, "created_at": now, "updated_at": now},
        )

    # 5. Membuat rantai prompt assistant > agent > reviewer
    reviewer_chain_id = generate_id()
    reviewer_version_id = generate_id()
    reviewer_version_hash = generate_id()[:8]

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": reviewer_chain_id,
            "mode_name": "assistant",
            "task_name": "agent",
            "agent_name": "reviewer",
            "created_at": now,
            "updated_at": now,
        },
    )

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": reviewer_version_id,
            "prompt_chain_id": reviewer_chain_id,
            "version_hash": reviewer_version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "Versi awal",
            "created_at": now,
        },
    )

    # Entri prompt Reviewer
    reviewer_entries = [
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": reviewer_version_id,
            "name": "Peran Sistem",
            "role": "system",
            "content": """Anda adalah editor yang teliti dalam memeriksa mutu dan konsistensi isi novel.

Tugas Anda:
Periksa isi bab yang dihasilkan dan cari apakah ada masalah.

Butir pemeriksaan:
1. Apakah sesuai dengan permintaan awal pengguna
2. Apakah konsisten dengan kerangka
3. Apakah konsisten dengan isi sebelumnya (tokoh, plot, latar, dan lain-lain)
4. Apakah ada konflik plot atau masalah logika
5. Apakah perilaku tokoh masuk akal
6. Apakah gaya tulis dan ungkapannya lancar""",
            "order_index": 0,
            "is_enabled": True,
            "token_count": 150,
        },
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": reviewer_version_id,
            "name": "Format Keluaran",
            "role": "user",
            "content": """Format keluaran (JSON ketat):
{
    "passed": true/false,
    "feedback": "Penjelasan umpan balik yang rinci",
    "suggestions": ["Saran 1", "Saran 2", ...]
}

Catatan:
- Bila mutu isi sudah baik dan tidak ada masalah nyata, pemeriksaan harus lolos (passed: true)
- Hanya bila ada masalah nyata pemeriksaan tidak lolos (passed: false)
- feedback harus menunjukkan letak masalah secara konkret
- suggestions harus memberikan saran perbaikan""",
            "order_index": 1,
            "is_enabled": True,
            "token_count": 120,
        },
    ]

    for entry in reviewer_entries:
        conn.execute(
            sa.text("""
                INSERT INTO prompt_entries 
                (id, uid, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
                VALUES (:id, :uid, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
            """),
            {**entry, "created_at": now, "updated_at": now},
        )


def downgrade() -> None:
    """Remove agent prompts and agent_session_id from tasks table."""
    # Menghapus kolom agent_session_id
    op.drop_index("ix_tasks_agent_session_id", table_name="tasks")
    op.drop_column("tasks", "agent_session_id")

    # Menghapus rantai prompt agent
    conn = op.get_bind()
    
    # Menghapus semua rantai prompt assistant > agent beserta data terkaitnya
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
    
    conn.execute(
        sa.text("""
            DELETE FROM prompt_chains 
            WHERE mode_name = 'assistant' AND task_name = 'agent'
        """)
    )