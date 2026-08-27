from sokol.plate_parse import PLATE_DETECT_PATH, parse_plate_service_payload


def test_plate_detect_path_matches_service() -> None:
    assert PLATE_DETECT_PATH == "/api/plate/detect"


def test_parse_plate_service_payload_reads_detections() -> None:
    rows = parse_plate_service_payload(
        {
            "detections": [
                {
                    "bbox": [1.0, 2.0, 3.0, 4.0],
                    "plate_text": "ABC1D23",
                    "confidence": 0.91,
                }
            ]
        }
    )
    assert rows == [
        {
            "plate_text": "ABC1D23",
            "confidence": 0.91,
            "bbox": [1.0, 2.0, 3.0, 4.0],
        }
    ]


def test_parse_plate_service_payload_ignores_legacy_plates_key() -> None:
    assert parse_plate_service_payload({"plates": [{"plate": "ABC1234"}]}) == []


def test_parse_plate_service_payload_empty() -> None:
    assert parse_plate_service_payload({}) == []
    assert parse_plate_service_payload({"detections": []}) == []
