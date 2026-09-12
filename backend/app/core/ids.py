"""
Fungsi bantu pembuatan ID.
"""

from nanoid import generate


def generate_id(size: int = 21) -> str:
    """
    Membuat ID unik.

    Args:
        size: panjang ID, default 21.

    Returns:
        String ID unik.
    """
    return generate(size=size)
