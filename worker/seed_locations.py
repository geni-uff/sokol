"""Seed location events with valid geo coordinates for map testing."""

import argparse
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

# São Paulo coordinates
SAO_PAULO_CENTER = (-23.5505, -46.6333)

# Real locations in São Paulo
LOCATIONS = [
    {"lat": -23.5505, "lon": -46.6333, "name": "Avenida Paulista, São Paulo"},
    {"lat": -23.5597, "lon": -46.6560, "name": "Ibirapuera Park, São Paulo"},
    {"lat": -23.5505, "lon": -46.6333, "name": "MASP (Museum of Art)"},
    {"lat": -23.5896, "lon": -46.6789, "name": "Tatuapé, São Paulo"},
    {"lat": -23.4813, "lon": -46.7623, "name": "São Bernardo do Campo"},
    {"lat": -23.4504, "lon": -46.4819, "name": "Diadema"},
    {"lat": -23.6345, "lon": -46.5537, "name": "Vila Mariana, São Paulo"},
    {"lat": -23.5729, "lon": -46.6529, "name": "Pinheiros, São Paulo"},
    {"lat": -23.5521, "lon": -46.6242, "name": "Bela Vista, São Paulo"},
    {"lat": -23.5963, "lon": -46.7032, "name": "Jardins, São Paulo"},
]


def seed_locations(case_id: UUID, database_url: str, count: int = 10):
    """Seed location events for testing geolocation features."""
    engine = create_engine(database_url)

    with engine.connect() as conn:
        # Verify case exists
        result = conn.execute(
            text("SELECT id FROM cases WHERE id = :id"),
            {"id": case_id},
        ).fetchone()

        if not result:
            print(f"❌ Case {case_id} not found")
            return

        print(f"✅ Case {case_id} found, seeding {count} location events...")

        base_time = datetime.now(timezone.utc) - timedelta(days=7)

        for i in range(min(count, len(LOCATIONS))):
            loc = LOCATIONS[i]
            event_id = uuid4()
            ts = base_time + timedelta(hours=i * 6)

            # PostGIS: ST_GeogFromText('SRID=4326;POINT(lon lat)')
            # But using ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography
            query = text("""
                INSERT INTO events (
                    id, case_id, ts, tz_original, kind, actor, counterpart, app,
                    ref_table, ref_id, summary, meta, geo
                )
                VALUES (
                    :id, :case_id, :ts, :tz, :kind, :actor, :counterpart, :app,
                    :ref_table, :ref_id, :summary, :meta,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                )
                ON CONFLICT DO NOTHING
            """)

            meta = {
                "address": loc["name"],
                "confidence": 0.95,
                "source": "synthetic_test",
            }

            conn.execute(
                query,
                {
                    "id": event_id,
                    "case_id": case_id,
                    "ts": ts,
                    "tz": "America/Sao_Paulo",
                    "kind": "location",
                    "actor": None,
                    "counterpart": None,
                    "app": None,
                    "ref_table": "events",
                    "ref_id": str(event_id),
                    "summary": f"Location: {loc['name']}",
                    "meta": json.dumps(meta),
                    "lat": loc["lat"],
                    "lon": loc["lon"],
                },
            )

        conn.commit()

        # Verify
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM events WHERE case_id = :id AND kind = 'location' AND geo IS NOT NULL"
            ),
            {"id": case_id},
        ).scalar()

        print(f"✅ Seeded {result} location events")
        print(f"📍 Events are geolocalized and ready for map visualization")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed location events for geolocation testing")
    parser.add_argument(
        "--case-id",
        type=str,
        required=True,
        help="Case UUID to seed locations into",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default="postgresql://sokol:change_me@localhost:5433/sokol",
        help="Database connection URL",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of location events to create (max 10)",
    )

    args = parser.parse_args()

    try:
        case_id = UUID(args.case_id)
    except ValueError:
        print(f"❌ Invalid UUID: {args.case_id}")
        exit(1)

    seed_locations(case_id, args.database_url, args.count)
