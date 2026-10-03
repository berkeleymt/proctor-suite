"""The student roster: who a student ID belongs to (names, school, room, contact).

Only source: ContestDojo's API, on demand from the Roster tab.
Nothing here runs on the event-day critical path (invariant 6): a roster is loaded once, kept in
memory, and room devices only ever look one student up in memory (invariant 1).
"""

from dataclasses import dataclass

import requests

SYNC_TIMEOUT_S = 20
CONTESTDOJO_URL = "https://api.contestdojo.com"


@dataclass(frozen=True)
class Student:
    id: str  # what a proctor types, normalised like bathroom student ids
    name: str = ""
    school: str = ""
    team: str = ""
    room: str = ""  # the room name as written in the source ("" = unknown)
    contact: str = ""  # parent / coach: admins only, never sent to proctors


class RosterError(Exception):
    """Something an admin can fix; the message is shown as-is."""


def norm_id(raw: str) -> str:
    return " ".join(str(raw).split()).upper()


def _get(base: str, token: str, path: str) -> list[dict]:
    try:
        r = requests.get(
            base.rstrip("/") + path,
            headers={"Authorization": f"Bearer {token}"},
            timeout=SYNC_TIMEOUT_S,
        )
    except requests.RequestException:
        raise RosterError("Couldn't reach ContestDojo. Check the address and try again.") from None
    if r.status_code in (401, 403):
        raise RosterError("ContestDojo refused the token. Ask for a new API token.")
    if r.status_code == 404:
        raise RosterError("ContestDojo doesn't know that event. Check the event ID.")
    if not r.ok:
        raise RosterError(f"ContestDojo answered {r.status_code}. Try again in a minute.")
    try:
        data = r.json()
    except ValueError:
        raise RosterError(
            "ContestDojo sent something that isn't data. Check the address."
        ) from None
    if not isinstance(data, list):
        raise RosterError("ContestDojo sent an unexpected answer. Check the address.")
    return data


def _get_opt(base: str, token: str, path: str) -> list[dict]:
    """Orgs and teams only add detail: if they fail, students are still imported."""
    try:
        return _get(CONTESTDOJO_URL, token, path)
    except RosterError:
        return []


def fetch_contestdojo(token: str, event_id: str) -> tuple[list[Student], list[str]]:
    """Blocking (run it in a thread). Joins `/events/{id}/students|teams|orgs/` (students carry
    `org` and `team` ids). Imports EVERY student returned: the ID is `number` when set, else the
    ContestDojo user id, so a proctor can still find them. School = org name, else the
    `customFields.school` text. Also returns notes (what ContestDojo sent) so an admin can sanity-check."""
    ev = f"/events/{event_id}"
    students = _get(CONTESTDOJO_URL, token, f"{ev}/students/")
    teams = {t.get("id"): t for t in _get_opt(CONTESTDOJO_URL, token, f"{ev}/teams/")}
    orgs = {o.get("id"): o for o in _get_opt(CONTESTDOJO_URL, token, f"{ev}/orgs/")}
    out: dict[str, Student] = {}
    clashes = 0
    for n, s in enumerate(students, start=1):
        sid = norm_id(s.get("number") or s.get("id") or s.get("user") or f"ROW{n}")
        if sid in out:  # never drop a student because of an ID clash
            clashes += 1
            sid = norm_id(f"{sid} {s.get('id') or n}")
        t = teams.get(s.get("team")) or {}
        o = orgs.get(s.get("org")) or {}
        cf = s.get("customFields") or {}
        out[sid] = Student(
            sid,
            " ".join(f"{s.get('fname') or ''} {s.get('lname') or ''}".split()),
            str(o.get("name") or cf.get("school") or ""),
            str(t.get("name") or t.get("number") or ""),
            "",  # room: not synced; ContestDojo has no room data yet
            s.get("email") or "",
        )
    numbered = sum(1 for s in students if s.get("number"))
    notes = [
        f"ContestDojo sent {len(students)} students, {len(teams)} teams, {len(orgs)} orgs; {numbered} have a number."
    ]
    if clashes:
        notes.append(f"{clashes} students shared an ID, so theirs got a suffix.")
    return list(out.values()), notes
