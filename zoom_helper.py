import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any, List
import requests
import string
import secrets

from core.google_sheets import GoogleSheets
from core.auth import Authentication


def generate_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(6))

def delete_meeting(auth : Authentication, meeting_id : str) -> requests.Response:
    """delete a scheduled Zoom meeting
    """
    resp = requests.delete(f"https://api.zoom.us/v2/meetings/{meeting_id}", headers=auth.zoom).json()
    return resp
    

def get_meeting(auth : Authentication, meeting_id : str) -> requests.Response:
    """get info of a scheduled Zoom meeting such as start_url
    """
    resp = requests.get(f"https://api.zoom.us/v2/meetings/{meeting_id}", headers=auth.zoom).json()
    return resp
    

def schedule_zoom_meeting(auth : Authentication, title : str, password : str, start : datetime, end : datetime, 
                          agenda : str, host : str , alternative_hosts : List[str] = [], use_dialin : bool = True):
    """Schedule a zoom meeting
    """
    # Max Zoom meeting topic length is 200 characters
    if len(title) > 200:
        title = title[0:199]
    # Max agenda length is 2000 characters
    if len(agenda) > 2000:
        agenda = agenda[0:1999]
    
    meeting_info = {
        "topic": title,
        "type": 2,
        "start_time": start.astimezone(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone": "UTC",
        "duration": int((end - start).total_seconds() / 60.0),
        "password": password,
        "agenda": agenda,
        "settings": {
            "host_video": False,
            "participant_video": False,
            "join_before_host": True,
            "mute_upon_entry": True,
            "waiting_room": False,
            "audio": "both",
            "alternative_hosts": ",".join(alternative_hosts),
            "global_dial_in_countries": [
                # NOTE: Fill in dial in countries as appropriate for your conference
                "DE",
                "SE",
                "JP",
                "KR",
                "GB",
                "US",
                "CA"
            ] if use_dialin else []
        }
    }

    zoom_info = requests.post(f"https://api.zoom.us/v2/users/{host}/meetings",
            json=meeting_info, headers=auth.zoom).json()
    return zoom_info

def schedule_meetings(args : argparse.Namespace):
    """Schedule meetings based on Sessions sheet in Data spreadsheet
    """
    auth = Authentication()
    sessionsSheet = GoogleSheets()
    sessionsSheet.load_sheet("Sessions")
    tracks = GoogleSheets()
    tracks.load_sheet("Tracks")
    tracks_dict : dict[dict[str, Any], Any] = {}
    for row in tracks.data:
        tracks_dict[row["Track"]] = row
    sessions = list(filter(lambda row: row["Zoom Meeting ID"] is None or len(row["Zoom Meeting ID"].strip()) == 0, sessionsSheet.data))
    if args.event_prefix and len(args.event_prefix) > 0:
        sessions = list(filter(lambda it: it["Event Prefix"] == args.event_prefix, sessions))
    if args.track and len(args.track) > 0:
        sessions = list(filter(lambda it: it["Track"] == args.track, sessions))

    num_to_schedule = len(sessions)
    if num_to_schedule > args.max_n_schedules:
        num_to_schedule = args.max_n_schedules

    print(f"{num_to_schedule} meetings will be scheduled")
    use_dialin = True
    if args.disable_dialin:
        use_dialin = False
    for i in range(num_to_schedule):
        session : dict[str, Any] = sessions[i]
        title = session["Session Title"]
        track = tracks_dict[session["Track"]]
        start = datetime.fromisoformat(session["DateTime Start"].replace('Z', '+00:00'))
        end = datetime.fromisoformat(session["DateTime End"].replace('Z', '+00:00'))
        start = start - timedelta(minutes=args.time_before)
        end = end + timedelta(minutes=args.time_after)
        room = track["Room Name"]
        host = track["Zoom Host ID"]
        password = generate_password()
        print(f"\r\n{i+1}/{num_to_schedule}: {title} - {room} | {start} - {end} | {host}")
        resp = schedule_zoom_meeting(auth, f"Session: {title}", password, start, end, "Conference Session for Hosts and Presenter", host, use_dialin=use_dialin)
        print(f"\r\n{json.dumps(resp, indent=4)}")
        session["Zoom Meeting ID"] = str(resp["id"])
        session["Zoom Password"] = password
        session["Zoom URL"] = resp["join_url"]
        sessionsSheet.save()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Schedule zoom meetings')
    parser.add_argument('--schedule', action="store_true", help='schedule zoom meetings for sessions in sheet')
    parser.add_argument('--delete', action="store_true", help='delete specified meeting')
    parser.add_argument('--get', action="store_true", help='get info of specified meeting')
    parser.add_argument('--start_url', action="store_true", help='retrieve start url of a meeting')
    
    parser.add_argument("--max_n_schedules", default=200, type=int, help='Maximum number of meetings to schedule in a call')
    parser.add_argument("--time_before", default=15, type=int, help='Time to start meeting earlier than session time, in minutes')
    parser.add_argument("--time_after", default=5, type=int, help='Scheduled end time of meeting after official session end, in minutes')

    parser.add_argument("--id", default=None, type=str, help='meeting id')
    parser.add_argument("--event_prefix", default=None, type=str, help='Event prefix to filter for')
    parser.add_argument("--track", default=None, type=str, help='Track id to filter for')
    parser.add_argument("--disable_dialin", action="store_true", help='Enable dial-in for meetings (requires Pro account)')

    args = parser.parse_args()

    if args.schedule:
        schedule_meetings(args)
    elif args.delete:
        resp = delete_meeting(Authentication(), args.id)
        print(resp)
    elif args.get:
        resp = get_meeting(Authentication(), args.id)
        print(json.dumps(resp, indent=4))
