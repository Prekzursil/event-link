"""Normalize event cover URLs and tag names.

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

_EVENT_TAGS = sa.table(
    "event_tags",
    sa.column("event_id"),
    sa.column("tag_id"),
)
_USER_INTEREST_TAGS = sa.table(
    "user_interest_tags",
    sa.column("user_id"),
    sa.column("tag_id"),
)
_TAGS = sa.table(
    "tags",
    sa.column("id"),
    sa.column("name"),
)
_EVENTS = sa.table("events", sa.column("cover_url"))


def _dedupe_join_table(
    conn,
    join_table: sa.TableClause,
    owner_col: str,
    canonical_id: int,
    dup_id: int,
) -> None:
    """Retarget duplicate join-table rows to the canonical tag id."""
    owner_column = join_table.c[owner_col]
    tag_column = join_table.c.tag_id
    canonical_owners = sa.select(owner_column).where(
        tag_column == canonical_id
    )
    conn.execute(
        sa.delete(join_table)
        .where(tag_column == dup_id)
        .where(owner_column.in_(canonical_owners))
    )
    conn.execute(
        sa.update(join_table)
        .where(tag_column == dup_id)
        .values(tag_id=canonical_id)
    )


def _trim_expression(conn) -> sa.Function:
    """Return a dialect-aware SQL trim expression for cover URLs."""
    if conn.dialect.name == "postgresql":
        return sa.func.btrim(_EVENTS.c.cover_url)
    return sa.func.trim(_EVENTS.c.cover_url)


def upgrade() -> None:
    """Apply the event-data normalization migration."""
    conn = op.get_bind()
    trimmed_cover_url = _trim_expression(conn)

    conn.execute(
        sa.update(_EVENTS)
        .where(_EVENTS.c.cover_url.is_not(None))
        .where(trimmed_cover_url == "")
        .values(cover_url=None)
    )
    conn.execute(
        sa.update(_EVENTS)
        .where(_EVENTS.c.cover_url.is_not(None))
        .values(cover_url=trimmed_cover_url)
    )

    rows = conn.execute(sa.select(_TAGS.c.id, _TAGS.c.name)).fetchall()
    groups: dict[str, list[tuple[int, str, str]]] = {}
    empty_tag_ids: list[int] = []
    for tag_id, name in rows:
        raw = str(name or "")
        trimmed = raw.strip()
        if not trimmed:
            empty_tag_ids.append(int(tag_id))
            continue
        groups.setdefault(trimmed.lower(), []).append(
            (int(tag_id), trimmed, raw)
        )

    for tag_id in empty_tag_ids:
        conn.execute(
            sa.delete(_EVENT_TAGS).where(_EVENT_TAGS.c.tag_id == tag_id)
        )
        conn.execute(
            sa.delete(_USER_INTEREST_TAGS).where(
                _USER_INTEREST_TAGS.c.tag_id == tag_id
            )
        )
        conn.execute(sa.delete(_TAGS).where(_TAGS.c.id == tag_id))

    for _normalized, entries in groups.items():
        entries.sort(key=lambda item: item[0])
        canonical_id, canonical_trimmed, canonical_raw = entries[0]

        if canonical_raw != canonical_trimmed:
            conn.execute(
                sa.update(_TAGS)
                .where(_TAGS.c.id == canonical_id)
                .values(name=canonical_trimmed)
            )

        for dup_id, _dup_trimmed, _dup_raw in entries[1:]:
            _dedupe_join_table(
                conn, _EVENT_TAGS, "event_id", canonical_id, dup_id
            )
            _dedupe_join_table(
                conn, _USER_INTEREST_TAGS, "user_id", canonical_id, dup_id
            )
            conn.execute(sa.delete(_TAGS).where(_TAGS.c.id == dup_id))


def downgrade() -> None:
    """Revert the event-data normalization migration where possible."""
    # Normalization merged duplicate tags and trimmed stored values
    # in place; downgrade cannot reconstruct the original data.
    pass
