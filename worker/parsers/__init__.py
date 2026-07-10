"""SOKOL parsers — common contract and registry."""

from .contract import (
    ParseResult,
    ParsedMessage,
    ParsedEvent,
    ParsedEntity,
    ParsedEntityLink,
    ParseError,
    extract_field,
    extract_participants,
    parse_ts,
)
from .whatsapp import parse_whatsapp
from .sms import parse_sms
from .call import parse_call
from .contact import parse_contact
from .location import parse_location
from .webhistory import parse_webhistory

PARSERS = {
    "Chat": parse_whatsapp,
    "InstantMessage": parse_whatsapp,
    "Call": parse_call,
    "Contact": parse_contact,
    "Location": parse_location,
    "WebBookmark": parse_webhistory,
    "SMS": parse_sms,
}
