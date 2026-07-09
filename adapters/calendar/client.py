"""
adapters/calendar/client.py
Google Calendar API client — CRUD operations for events.
All methods return typed dicts or raise CalendarClientError.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from adapters.calendar.auth import CalendarAuth, CalendarAuthError

logger = logging.getLogger(__name__)


class CalendarClientError(Exception):
    """Raised on any Google Calendar API failure."""


class CalendarEvent:
    """Lightweight wrapper around a raw Google Calendar event dict."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw

    @property
    def id(self) -> str:
        return self._raw.get("id", "")

    @property
    def summary(self) -> str:
        return self._raw.get("summary", "(No title)")

    @property
    def start(self) -> Optional[datetime]:
        start = self._raw.get("start", {})
        dt_str = start.get("dateTime") or start.get("date")
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None

    @property
    def end(self) -> Optional[datetime]:
        end = self._raw.get("end", {})
        dt_str = end.get("dateTime") or end.get("date")
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None

    @property
    def description(self) -> str:
        return self._raw.get("description", "")

    @property
    def location(self) -> str:
        return self._raw.get("location", "")

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw

    def __repr__(self) -> str:
        return f"<CalendarEvent id={self.id!r} summary={self.summary!r} start={self.start}>"


class CalendarClient:
    """
    Wraps the Google Calendar API v3.

    Usage:
        client = CalendarClient()
        events = client.list_upcoming_events(max_results=5)
    """

    CALENDAR_ID = "primary"

    def __init__(self, auth: Optional[CalendarAuth] = None) -> None:
        self._auth = auth or CalendarAuth()
        self._service = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Authenticate and build the API service object."""
        try:
            creds = self._auth.get_credentials()
            self._service = build("calendar", "v3", credentials=creds)
            logger.info("Google Calendar client connected.")
        except CalendarAuthError as exc:
            raise CalendarClientError(f"Authentication failed: {exc}") from exc

    def _ensure_connected(self) -> None:
        if self._service is None:
            self.connect()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def list_upcoming_events(
        self,
        max_results: int = 10,
        calendar_id: str = CALENDAR_ID,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
    ) -> list[CalendarEvent]:
        """
        Return upcoming calendar events ordered by start time.

        Args:
            max_results: Maximum number of events to return.
            calendar_id: Which calendar to query (default: 'primary').
            time_min: Start of the search window (default: now).
            time_max: End of the search window (default: no limit).
        """
        self._ensure_connected()
        now = datetime.now(timezone.utc)
        time_min = time_min or now
        params: dict[str, Any] = {
            "calendarId": calendar_id,
            "timeMin": time_min.isoformat(),
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_max:
            params["timeMax"] = time_max.isoformat()

        try:
            result = self._service.events().list(**params).execute()
            raw_events = result.get("items", [])
            events = [CalendarEvent(e) for e in raw_events]
            logger.debug("Fetched %d upcoming events.", len(events))
            return events
        except HttpError as exc:
            raise CalendarClientError(f"Failed to list events: {exc}") from exc

    def list_events_today(self) -> list[CalendarEvent]:
        """Convenience: return all events for the current day."""
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        return self.list_upcoming_events(
            max_results=50, time_min=start_of_day, time_max=end_of_day
        )

    def get_event(self, event_id: str, calendar_id: str = CALENDAR_ID) -> CalendarEvent:
        """Fetch a single event by ID."""
        self._ensure_connected()
        try:
            raw = self._service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            return CalendarEvent(raw)
        except HttpError as exc:
            raise CalendarClientError(f"Failed to get event {event_id}: {exc}") from exc

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = "",
        location: str = "",
        calendar_id: str = CALENDAR_ID,
        reminders_minutes: Optional[list[int]] = None,
    ) -> CalendarEvent:
        """
        Create a new calendar event.

        Args:
            summary: Event title.
            start: Start datetime (timezone-aware recommended).
            end: End datetime.
            description: Optional event description.
            location: Optional location string.
            calendar_id: Target calendar.
            reminders_minutes: List of reminder offsets in minutes before event.
        """
        self._ensure_connected()

        body: dict[str, Any] = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        }

        if reminders_minutes is not None:
            body["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": m} for m in reminders_minutes
                ],
            }
        else:
            body["reminders"] = {"useDefault": True}

        try:
            raw = (
                self._service.events()
                .insert(calendarId=calendar_id, body=body)
                .execute()
            )
            event = CalendarEvent(raw)
            logger.info("Created event %r (id=%s)", summary, event.id)
            return event
        except HttpError as exc:
            raise CalendarClientError(f"Failed to create event: {exc}") from exc

    def update_event(
        self,
        event_id: str,
        updates: dict[str, Any],
        calendar_id: str = CALENDAR_ID,
    ) -> CalendarEvent:
        """
        Partially update an existing event.

        Args:
            event_id: ID of the event to update.
            updates: Dict of fields to patch (e.g. {'summary': 'New title'}).
        """
        self._ensure_connected()
        try:
            raw = (
                self._service.events()
                .patch(calendarId=calendar_id, eventId=event_id, body=updates)
                .execute()
            )
            logger.info("Updated event %s.", event_id)
            return CalendarEvent(raw)
        except HttpError as exc:
            raise CalendarClientError(f"Failed to update event {event_id}: {exc}") from exc

    def delete_event(self, event_id: str, calendar_id: str = CALENDAR_ID) -> None:
        """Delete an event by ID."""
        self._ensure_connected()
        try:
            self._service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            logger.info("Deleted event %s.", event_id)
        except HttpError as exc:
            raise CalendarClientError(f"Failed to delete event {event_id}: {exc}") from exc

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def check_availability(self, start: datetime, end: datetime) -> bool:
        """
        Return True if there are no events overlapping the given window.
        Simple check using free/busy API.
        """
        self._ensure_connected()
        body = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": self.CALENDAR_ID}],
        }
        try:
            result = self._service.freebusy().query(body=body).execute()
            busy = result.get("calendars", {}).get(self.CALENDAR_ID, {}).get("busy", [])
            return len(busy) == 0
        except HttpError as exc:
            raise CalendarClientError(f"Free/busy query failed: {exc}") from exc

    def next_event(self) -> Optional[CalendarEvent]:
        """Return the very next upcoming event, or None."""
        events = self.list_upcoming_events(max_results=1)
        return events[0] if events else None