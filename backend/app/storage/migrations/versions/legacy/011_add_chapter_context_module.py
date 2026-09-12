"""Add chapter context module tables and seed prompt chains

Revision ID: 011
Revises: 010
Create Date: 2026-01-19

Creates:
- chapter_summaries table (unified summary storage for chapter/block types)
- Seed prompt chains for memory/mid_range_summary and memory/far_range_summary
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create chapter context tables and insert seed prompt chains."""
    from datetime import UTC, datetime
    from app.core.ids import generate_id

    # ============ Membuat tabel chapter_summaries ============
    op.create_table(
        "chapter_summaries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("summary_type", sa.String(length=20), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=True),
        sa.Column("start_order", sa.Integer(), nullable=True),
        sa.Column("end_order", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_chapter_summaries_project_id", "chapter_summaries", ["project_id"])
    op.create_index("ix_chapter_summaries_summary_type", "chapter_summaries", ["summary_type"])
    op.create_index("ix_chapter_summaries_chapter_id", "chapter_summaries", ["chapter_id"])

    # ============ Menyisipkan rantai prompt Memory ============
    conn = op.get_bind()
    now = datetime.now(UTC)

    # ---- rantai prompt mid_range_summary ----
    mid_chain_id = generate_id()
    mid_version_id = generate_id()
    mid_version_hash = generate_id()[:8]
    mid_entry_id = generate_id()

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": mid_chain_id,
            "mode_name": "memory",
            "task_name": "mid_range_summary",
            "agent_name": None,
            "created_at": now,
            "updated_at": now,
        }
    )

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": mid_version_id,
            "prompt_chain_id": mid_chain_id,
            "version_hash": mid_version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "Versi awal",
            "created_at": now,
        }
    )

    mid_range_prompt = """Anda adalah pembuat ringkasan bab novel yang profesional. Bacalah isi bab berikut, lalu buat ringkasan yang singkat namun kaya informasi.

Ketentuan:
1. Pertahankan titik plot kunci dan tindakan tokoh penting
2. Rangkum perkembangan peristiwa utama
3. Jaga agar garis waktu tetap jelas
4. Panjang ringkasan dijaga pada 10-15% teks asli

Isi bab:
{{chapter_content}}"""

    conn.execute(
        sa.text("""
            INSERT INTO prompt_entries 
            (id, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
            VALUES (:id, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
        """),
        {
            "id": mid_entry_id,
            "version_id": mid_version_id,
            "name": "Instruksi Pembuatan Ringkasan",
            "role": "system",
            "content": mid_range_prompt,
            "order_index": 0,
            "is_enabled": True,
            "token_count": 80,
            "created_at": now,
            "updated_at": now,
        }
    )

    # ---- rantai prompt far_range_summary ----
    far_chain_id = generate_id()
    far_version_id = generate_id()
    far_version_hash = generate_id()[:8]
    far_entry_id = generate_id()

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": far_chain_id,
            "mode_name": "memory",
            "task_name": "far_range_summary",
            "agent_name": None,
            "created_at": now,
            "updated_at": now,
        }
    )

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": far_version_id,
            "prompt_chain_id": far_chain_id,
            "version_hash": far_version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "Versi awal",
            "created_at": now,
        }
    )

    far_range_prompt = """Anda adalah pemadat plot novel yang profesional. Gabungkan ringkasan beberapa bab berikut menjadi satu ikhtisar yang lebih singkat.

Ketentuan:
1. Ambil alur plot inti
2. Pertahankan titik balik kunci
3. Gabungkan peristiwa yang mirip atau berurutan
4. Panjang keluaran sekitar 30-50% dari masukan

Daftar ringkasan bab:
{{summaries}}"""

    conn.execute(
        sa.text("""
            INSERT INTO prompt_entries 
            (id, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
            VALUES (:id, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
        """),
        {
            "id": far_entry_id,
            "version_id": far_version_id,
            "name": "Instruksi Pembuatan Ringkasan Rentang",
            "role": "system",
            "content": far_range_prompt,
            "order_index": 0,
            "is_enabled": True,
            "token_count": 70,
            "created_at": now,
            "updated_at": now,
        }
    )


def downgrade() -> None:
    """Drop chapter context tables and remove memory prompt chains."""
    conn = op.get_bind()

    # Menghapus rantai prompt terkait memory (penghapusan berantai menangani versions dan entries)
    conn.execute(
        sa.text("DELETE FROM prompt_chains WHERE mode_name = 'memory'")
    )

    # Menghapus tabel
    op.drop_index("ix_chapter_summaries_chapter_id", "chapter_summaries")
    op.drop_index("ix_chapter_summaries_summary_type", "chapter_summaries")
    op.drop_index("ix_chapter_summaries_project_id", "chapter_summaries")
    op.drop_table("chapter_summaries")
