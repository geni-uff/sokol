"""SOKOL API — Graph visualization for entity relationships."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory

router = APIRouter(prefix="/graph", tags=["graph"])


# ── Models ─────────────────────────────────────────────────────────────────
class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # 'person', 'phone', 'chat', 'app', 'location', 'media'
    properties: dict = {}
    size: int = 1


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str  # 'messaged', 'called', 'located_at', 'uses_app', etc.
    weight: int = 1
    properties: dict = {}


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: dict


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.get("/{case_id}", response_model=GraphData)
def get_graph(
    case_id: str,
    max_nodes: int = Query(100, ge=10, le=500),
    node_types: Optional[str] = None,  # comma-separated: person,phone,chat,app
):
    """Get entity relationship graph for a case."""
    factory = get_session_factory()
    with factory() as db:
        nodes = []
        edges = []
        node_ids = set()

        # Get contacts/phone numbers from messages
        contacts = db.execute(
            text("""
                SELECT DISTINCT
                    sender as phone,
                    counterpart as contact
                FROM messages
                WHERE case_id = :case_id
                    AND sender IS NOT NULL
                    AND counterpart IS NOT NULL
                LIMIT :limit
            """),
            {"case_id": case_id, "limit": max_nodes * 2},
        ).fetchall()

        for row in contacts:
            sender_id = f"phone:{row[0]}"
            contact_id = f"phone:{row[1]}"

            if sender_id not in node_ids:
                nodes.append(GraphNode(id=sender_id, label=row[0], type="phone"))
                node_ids.add(sender_id)
            if contact_id not in node_ids:
                nodes.append(GraphNode(id=contact_id, label=row[1], type="phone"))
                node_ids.add(contact_id)

            edges.append(
                GraphEdge(source=sender_id, target=contact_id, relationship="messaged")
            )

        # Get apps used
        apps = db.execute(
            text("""
                SELECT DISTINCT app, COUNT(*) as cnt
                FROM messages
                WHERE case_id = :case_id AND app IS NOT NULL
                GROUP BY app
                ORDER BY cnt DESC
                LIMIT 20
            """),
            {"case_id": case_id},
        ).fetchall()

        for row in apps:
            app_id = f"app:{row[0]}"
            if app_id not in node_ids:
                nodes.append(
                    GraphNode(id=app_id, label=row[0], type="app", size=row[1])
                )
                node_ids.add(app_id)

        # Get chat groups
        chats = db.execute(
            text("""
                SELECT DISTINCT chat_id, app, COUNT(*) as msg_count
                FROM messages
                WHERE case_id = :case_id AND chat_id IS NOT NULL
                GROUP BY chat_id, app
                ORDER BY msg_count DESC
                LIMIT 50
            """),
            {"case_id": case_id},
        ).fetchall()

        for row in chats:
            chat_id = f"chat:{row[0]}"
            if chat_id not in node_ids:
                nodes.append(
                    GraphNode(
                        id=chat_id, label=row[0] or "Chat", type="chat", size=row[2]
                    )
                )
                node_ids.add(chat_id)

        # Get locations
        locations = db.execute(
            text("""
                SELECT DISTINCT
                    meta->>'lat' as lat,
                    meta->>'lon' as lon,
                    meta->>'label' as label
                FROM events
                WHERE case_id = :case_id
                    AND kind = 'location'
                    AND meta->>'lat' IS NOT NULL
                LIMIT 50
            """),
            {"case_id": case_id},
        ).fetchall()

        for i, row in enumerate(locations):
            loc_id = f"location:{i}"
            if loc_id not in node_ids:
                nodes.append(
                    GraphNode(
                        id=loc_id,
                        label=row[2] or f"({row[0]}, {row[1]})",
                        type="location",
                        properties={"lat": row[0], "lon": row[1]},
                    )
                )
                node_ids.add(loc_id)

        # Connect phones to apps and chats
        for edge in edges[:]:
            if edge.source.startswith("phone:"):
                for chat in chats:
                    chat_id = f"chat:{chat[0]}"
                    if chat_id in node_ids:
                        edges.append(
                            GraphEdge(
                                source=edge.source,
                                target=chat_id,
                                relationship="in_chat",
                            )
                        )

        # Stats
        stats = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": {},
        }
        for node in nodes:
            stats["node_types"][node.type] = stats["node_types"].get(node.type, 0) + 1

        return GraphData(
            nodes=nodes[:max_nodes], edges=edges[: max_nodes * 2], stats=stats
        )


@router.get("/{case_id}/shortest-path")
def shortest_path(case_id: str, from_id: str, to_id: str):
    """Find shortest path between two entities."""
    # Simplified BFS implementation
    factory = get_session_factory()
    with factory() as db:
        # For now, return direct connections
        query = """
            SELECT DISTINCT
                sender as source,
                counterpart as target,
                'messaged' as relationship
            FROM messages
            WHERE case_id = :case_id
                AND (
                    (sender = :from_id AND counterpart = :to_id)
                    OR (sender = :to_id AND counterpart = :from_id)
                )
        """
        rows = db.execute(
            text(query), {"case_id": case_id, "from_id": from_id, "to_id": to_id}
        ).fetchall()

        if rows:
            return {
                "path": [from_id, to_id],
                "hops": 1,
                "relationships": [r[2] for r in rows],
            }

        return {"path": [], "hops": 0, "message": "No path found"}


@router.get("/{case_id}/ego/{entity_id}")
def ego_graph(case_id: str, entity_id: str, depth: int = Query(1, ge=1, le=3)):
    """Get ego graph centered on an entity."""
    factory = get_session_factory()
    with factory() as db:
        nodes = []
        edges = []
        visited = set()

        def expand(node_id: str, current_depth: int):
            if current_depth > depth or node_id in visited:
                return
            visited.add(node_id)

            # Get connections
            rows = db.execute(
                text("""
                    SELECT DISTINCT
                        CASE WHEN sender = :node_id THEN counterpart ELSE sender END as connected,
                        'messaged' as relationship
                    FROM messages
                    WHERE case_id = :case_id
                        AND (sender = :node_id OR counterpart = :node_id)
                """),
                {"case_id": case_id, "node_id": node_id},
            ).fetchall()

            for row in rows:
                connected_id = row[0]
                if connected_id not in visited:
                    nodes.append(
                        GraphNode(id=connected_id, label=connected_id, type="phone")
                    )
                    edges.append(
                        GraphEdge(
                            source=node_id, target=connected_id, relationship=row[1]
                        )
                    )
                    expand(connected_id, current_depth + 1)

        # Start from center
        nodes.append(GraphNode(id=entity_id, label=entity_id, type="phone", size=2))
        expand(entity_id, 0)

        return GraphData(
            nodes=nodes,
            edges=edges,
            stats={"center": entity_id, "depth": depth, "nodes_found": len(nodes)},
        )
