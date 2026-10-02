"""The student roster: who a student ID belongs to (names, school, room, contact).

Two ways in, both produce the same `Student` rows:
  - `parse_csv`: an export pasted or uploaded by an admin (works with no network, no API).
  - `fetch_contestdojo`: optional, on demand, only when CONTESTDOJO_* is configured.
Nothing here runs on the event-day critical path (invariant 6): a roster is loaded once, kept in
memory, and room devices only ever look one student up in memory (invariant 1).
"""

import csv
import io
from dataclasses import dataclass

import requests

MAX_STUDENTS = 20_000
SYNC_TIMEOUT_S = 20


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


def _key(h: str) -> str:
    return "".join(ch for ch in h.lower() if ch.isalnum())


# Header spellings we accept, compared with spaces, case and punctuation ignored.
_ALIASES = {
    "id": ("id", "studentid", "student", "number", "studentnumber", "participantid", "studentno"),
    "name": ("name", "fullname", "studentname"),
    "first": ("firstname", "fname", "first", "givenname"),
    "last": ("lastname", "lname", "last", "surname", "familyname"),
    "school": ("school", "org", "organization", "organisation", "schoolteam", "schoolname"),
    "team": ("team", "teamname", "teamnumber"),
    "room": ("room", "roomname", "roomassignment", "testroom", "location"),
    "contact": ("contact", "parentcoachcontact", "parentcontact", "coachcontact", "coach",
                "parent", "parentemail", "coachemail", "email"),
}  # fmt: skip


def parse_csv(text: str) -> tuple[list[Student], list[str]]:
    """Rows -> students, plus short notes about rows that were skipped. Raises RosterError if
    the file has no usable header. Comma, semicolon and tab all work (Excel exports vary)."""
    text = text.lstrip("\ufeff")
    if not text.strip():
        raise RosterError("That file is empty.")
    first = text.splitlines()[0]
    delim = max(",\t;", key=first.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    header = [_key(h) for h in rows[0]]
    col: dict[str, int] = {}
    for field, names in _ALIASES.items():
        for i, h in enumerate(header):
            if h in names and i not in col.values():
                col[field] = i
                break
    if "id" not in col or not ({"name", "first", "last"} & col.keys()):
        raise RosterError(
            "I need a column for the student ID (like 054A) and one for the name. "
            "Check the first row has headers such as ID, Name, School, Room."
        )

    def cell(r: list[str], f: str) -> str:
        i = col.get(f)
        return " ".join(r[i].split()) if i is not None and i < len(r) else ""

    out: dict[str, Student] = {}
    notes: list[str] = []
    for n, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        sid = norm_id(cell(r, "id"))
        if not sid or len(sid) > 20:
            notes.append(f"Row {n}: no usable ID, skipped.")
            continue
        name = cell(r, "name") or f"{cell(r, 'first')} {cell(r, 'last')}".strip()
        if sid in out:
            notes.append(f"Row {n}: {sid} appears twice, the later row wins.")
        out[sid] = Student(
            sid, name, cell(r, "school"), cell(r, "team"), cell(r, "room"), cell(r, "contact")
        )
        if len(out) > MAX_STUDENTS:
            raise RosterError(f"That is more than {MAX_STUDENTS:,} students. Split the file.")
    if not out:
        raise RosterError("I found the headers but no students under them.")
    return list(out.values()), notes


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


def fetch_contestdojo(base: str, token: str, event_id: str, room_key: str = "") -> list[Student]:
    """Blocking (run it in a thread). Reads `/events/{id}/students|teams|orgs/` of the
    ContestDojo API (github.com/contestdojo/api). The student's `number` is the ID; the school
    is the org's name; the room comes from `roomAssignments[room_key]` when a key is set."""
    ev = f"/events/{event_id}"
    students = _get(base, token, f"{ev}/students/")
    teams = {
        t.get("id"): t.get("name") or t.get("number") or ""
        for t in _get(base, token, f"{ev}/teams/")
    }
    orgs = {o.get("id"): o.get("name") or "" for o in _get(base, token, f"{ev}/orgs/")}
    out: dict[str, Student] = {}
    for s in students:
        sid = norm_id(s.get("number") or "")
        if not sid or len(sid) > 20:
            continue  # not assigned a number yet: can't be typed by a proctor
        room = (s.get("roomAssignments") or {}).get(room_key, "") if room_key else ""
        out[sid] = Student(
            sid,
            " ".join(f"{s.get('fname') or ''} {s.get('lname') or ''}".split()),
            orgs.get(s.get("org"), ""),
            str(teams.get(s.get("team"), "")),
            str(room or ""),
            s.get("email") or "",
        )
    if not out:
        raise RosterError("ContestDojo has no students with a number for that event yet.")
    return list(out.values())
