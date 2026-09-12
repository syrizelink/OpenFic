"""add entry uid for cross-version tracking

Revision ID: 013
Revises: 012
Create Date: 2025-02-09

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Menambahkan kolom entry_uid untuk melacak entri antarversi.

    Strategi:
    1. Menambahkan kolom uid (mengizinkan NULL)
    2. Membuat uid untuk data yang ada (berdasarkan kecocokan kemiripan isi)
    3. Menyetel kolom uid menjadi NOT NULL
    """
    # 1. Menambahkan kolom uid (mengizinkan NULL)
    op.add_column("prompt_entries", sa.Column("uid", sa.String(), nullable=True))
    op.create_index("ix_prompt_entries_uid", "prompt_entries", ["uid"])

    # 2. Membuat uid untuk data yang ada
    # Strategi: diproses urut versi, entri dengan posisi dan nama sama memakai uid sama
    conn = op.get_bind()

    # Mengambil semua versi (urut nomor versi)
    versions_result = conn.execute(
        text("""
        SELECT id, prompt_chain_id, version_number 
        FROM prompt_chain_versions 
        ORDER BY prompt_chain_id, version_number
    """)
    )
    versions = versions_result.fetchall()

    # Diproses per grup prompt_chain
    from collections import defaultdict

    chains_versions = defaultdict(list)
    for version in versions:
        chains_versions[version[1]].append(version)  # type: ignore[index]

    # Membuat uid untuk entri setiap prompt_chain
    for chain_id, chain_versions in chains_versions.items():
        # Menyimpan informasi entri setiap versi: {order_index: {name: uid}}
        version_entries_map: dict[str, dict[int, dict[str, str]]] = {}

        for version in chain_versions:
            version_id = version[0]

            # Mengambil semua entri versi tersebut
            entries_result = conn.execute(
                text("""
                SELECT id, name, order_index 
                FROM prompt_entries 
                WHERE version_id = :version_id 
                ORDER BY order_index
            """),
                {"version_id": version_id},
            )
            entries = entries_result.fetchall()

            current_entries: dict[int, dict[str, str]] = {}

            for entry in entries:
                entry_id, name, order_index = entry  # type: ignore[misc]

                # Memeriksa apakah ada entri historis yang cocok
                matched_uid = None

                # Mencoba menemukan entri yang cocok dari versi sebelumnya
                matched_uid = None

                # Strategi 1: order_index sama + name sama
                if version_entries_map:
                    prev_version_entries = list(version_entries_map.values())[-1]
                    if (
                        order_index in prev_version_entries
                        and name in prev_version_entries[order_index]
                    ):
                        matched_uid = prev_version_entries[order_index][name]

                # Strategi 2: name sama (posisi berbeda)
                if not matched_uid and version_entries_map:
                    prev_version_entries = list(version_entries_map.values())[-1]
                    for prev_entries in prev_version_entries.values():
                        if name in prev_entries:
                            matched_uid = prev_entries[name]
                            break

                # Bila tidak ada yang cocok, buat uid baru
                if not matched_uid:
                    import uuid

                    matched_uid = str(uuid.uuid4())

                # Memperbarui basis data
                conn.execute(
                    text("""
                    UPDATE prompt_entries 
                    SET uid = :uid 
                    WHERE id = :entry_id
                """),
                    {"uid": matched_uid, "entry_id": entry_id},
                )

                # Mencatat entri saat ini
                if order_index not in current_entries:
                    current_entries[order_index] = {}
                current_entries[order_index][name] = matched_uid

            version_entries_map[version_id] = current_entries

    # 3. Menyetel kolom uid menjadi NOT NULL
    # Catatan: SQLite tidak mendukung perubahan constraint kolom secara langsung, tabel perlu dibangun ulang
    # Namun karena uid sudah diisi untuk semua baris, hal ini dapat diwajibkan di lapisan aplikasi
    # Bila memakai PostgreSQL/MySQL, dapat dijalankan:
    # op.alter_column('prompt_entries', 'uid', nullable=False)


def downgrade() -> None:
    """Menghapus kolom uid"""
    op.drop_index("ix_prompt_entries_uid", table_name="prompt_entries")
    op.drop_column("prompt_entries", "uid")
