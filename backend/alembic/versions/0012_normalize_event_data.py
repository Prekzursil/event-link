"""Normalize event cover URLs and tag names

Revision ID: 0012_normalize_event_data
Revises: 0011_add_language_preference
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0012_normalize_event_data"
down_revision = "0011_add_language_preference"
branch_labels = None
depends_on = None


def _dedupe_join_table(conn, table: str, owner_col: str, canonical_id: int, dup_id: int) -> None:
    conn.execute(
        sa.text(
            f"DELETE FROM {table} "
            f"WHERE tag_id = :dup_id "
            f"AND {owner_col} IN (SELECT {owner_col} FROM {table} WHERE tag_id = :canonical_id)"
        ),
        {"dup_id": dup_id, "canonical_id": canonical_id},
    )
    conn.execute(
        sa.text(f"UPDATE {table} SET tag_id = :canonical_id WHERE tag_id = :dup_id"),
        {"dup_id": dup_id, "canonical_id": canonical_id},
    )


def upgrade() -> None:
    conn = op.get_bind()

    trim_fn = "BTRIM" if conn.dialect.name == "postgresql" else "TRIM"

    # Normalize cover_url: trim whitespace; convert empty strings to NULL.
    conn.execute(
        sa.text(
            f"UPDATE events SET cover_url = NULL "
            f"WHERE cover_url IS NOT NULL AND {trim_fn}(cover_url) = ''"
        )
    )
    conn.execute(sa.text(f"UPDATE events SET cover_url = {trim_fn}(cover_url) WHERE cover_url IS NOT NULL"))

    # Normalize tags: trim whitespace and merge duplicates case-insensitively.
    rows = conn.execute(sa.text("SELECT id, name FROM tags")).fetchall()
    groups: dict[str, list[tuple[int, str, str]]] = {}
    empty_tag_ids: list[int] = []
    for tag_id, name in rows:
        raw = str(name or "")
        trimmed = raw.strip()
        if not trimmed:
            empty_tag_ids.append(int(tag_id))
            continue
        groups.setdefault(trimmed.lower(), []).append((int(tag_id), trimmed, raw))

    # Drop empty/whitespace-only tags.
    for tag_id in empty_tag_ids:
        conn.execute(sa.text("DELETE FROM event_tags WHERE tag_id = :tag_id"), {"tag_id": tag_id})
        conn.execute(sa.text("DELETE FROM user_interest_tags WHERE tag_id = :tag_id"), {"tag_id": tag_id})
        conn.execute(sa.text("DELETE FROM tags WHERE id = :tag_id"), {"tag_id": tag_id})

    for normalized, entries in groups.items():
        entries.sort(key=lambda x: x[0])
        canonical_id, canonical_trimmed, canonical_raw = entries[0]

        # Ensure the canonical tag name is trimmed.
        if canonical_raw != canonical_trimmed:
            conn.execute(
                sa.text("UPDATE tags SET name = :name WHERE id = :tag_id"),
                {"name": canonical_trimmed, "tag_id": canonical_id},
            )

        # Merge duplicates into the canonical row.
        for dup_id, dup_trimmed, _dup_raw in entries[1:]:
            _dedupe_join_table(conn, "event_tags", "event_id", canonical_id, dup_id)
            _dedupe_join_table(conn, "user_interest_tags", "user_id", canonical_id, dup_id)
            conn.execute(sa.text("DELETE FROM tags WHERE id = :tag_id"), {"tag_id": dup_id})


def downgrade() -> None:
    # Data normalization is not reversible.
    pass

