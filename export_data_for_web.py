from calendar import Calendar
from colorsys import yiq_to_rgb
import os
import json
from threading import local
import ics
# from PIL import Image
from datetime import timezone, datetime, timedelta
import argparse

from core.auth import Authentication
from core.google_sheets import GoogleSheets

# Melbourne is in GMT+11, AEDT
conf_tz = timezone(timedelta(hours=11))


def parse_time(t: str):
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def format_time_slot(start: datetime, end: datetime):
    return start.strftime("%H%M") + "-" + end.strftime("%H%M")


def format_time(t: datetime):
    return t.strftime("%a %b %d %H:%M %Z")


def format_time_iso8601_utc(t: datetime):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_time_local(t: datetime):
    localt = t.replace(tzinfo=timezone.utc).astimezone(tz=conf_tz)
    return localt.strftime("%a %b %d %I:%M %p AEDT (UTC+11)")


def make_description_for_session(session_title: str, session_id: str, session_room: str, start_time: datetime, end_time: datetime):
    text = session_title + " [VIS 2023] \n\n"
    # if self.timeslot_entry(0, "Event URL").value:
    #     text += "\nEvent Webpage: {}".format(self.timeslot_entry(0, "Event URL").value)

    # NOTE: You'll want to replace this with the link to your conference session page
    text += f"Session Webpage: https://virtual.ieeevis.org/year/2023/session_{session_id}.html \n"

    text += f"Session Room: {session_room} \n\n"

    # NOTE: include local time here as well
    text += f"Session Start: {format_time_local(start_time)}\n" + \
            f"Session End: {format_time_local(end_time)}"

    # if self.timeslot_entry(0, "Discord Link").value:
    #     text += "\nDiscord Link: " + self.timeslot_entry(0, "Discord Link").value

    # if self.timeslot_entry(0, "Chair(s)").value:
    #     text += "\nSession Chair(s): " + self.timeslot_entry(0, "Chair(s)").value.replace("|", ", ")

    return text


def make_calendar_for_session(session_title: str, session_id: str, session_room: str, start_time: datetime, end_time: datetime) -> ics.Calendar:
    calendar = ics.Calendar()
    event = ics.Event()
    event.begin = start_time
    # Use this for sending events to SVs, Chairs, etc.
    # if with_setup_time:
    #     event.begin -= self.setup_time()
    event.end = end_time
    event.name = session_title + " [VIS 2023]"
    event.location = session_room

    event.description = ""
    # We include the zoom info in the calendar file sent to presenters,
    # put the URL up front in ICS because google calendar limits the length of this
    # if zoom_info:
    #     event.description += "Zoom URL: " + self.timeslot_entry(0, "Zoom URL").value + \
    #             "\nZoom Meeting ID: " + self.timeslot_entry(0, "Zoom Meeting ID").value + \
    #             "\nZoom Password: " + self.timeslot_entry(0, "Zoom Password").value + "\n"

    event.description += make_description_for_session(
        session_title, session_id, session_room, start_time, end_time)
    calendar.events.add(event)
    return calendar


def create_data_for_web(auth: Authentication, output_dir: str, export_ics: bool, export_img: bool, export_pdf: bool):
    """create data for virtual website.
    authentication: Authentication instance in which aws ses client, & google sheets was authenticated
    conference_db: Google Sheet identifier for Conference Database Sheet. TODO add more info about that sheet
    output_dir: output directory for data

    """
    # Check for output path
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if export_ics and not os.path.exists(os.path.join(output_dir, "ics")):
        os.makedirs(os.path.join(output_dir, "ics"), exist_ok=True)
    full_calendar = ics.Calendar()
    event_calendars = {}

    all_posters = {}
    all_papers = {}
    all_events = {}

    sheet_events = GoogleSheets()
    sheet_events.load_sheet("Events")

    sheet_sessions = GoogleSheets()
    sheet_sessions.load_sheet("Sessions")

    sheet_papers = GoogleSheets()
    sheet_papers.load_sheet("ItemsVIS-A")

    sheet_ext = GoogleSheets()
    sheet_ext.load_sheet("ItemsEXT")

    sheet_ff_playlists = GoogleSheets()
    sheet_ff_playlists.load_sheet("FFPlaylists")

    sheet_ff_videos = GoogleSheets()
    sheet_ff_videos.load_sheet("FFVideos")

    sheet_pre_videos = GoogleSheets()
    sheet_pre_videos.load_sheet("Videos")

    sheet_bunny = GoogleSheets()
    sheet_bunny.load_sheet("BunnyContent")

    sheet_posters = GoogleSheets()
    sheet_posters.load_sheet("Posters")

    # All paper types, full, short, workshop
    sheet_db_papers = GoogleSheets()
    sheet_db_papers.load_sheet("PapersDB")

    # All tracks/rooms of the conference, create dict based on "Track"
    sheet_tracks = GoogleSheets()
    sheet_tracks.load_sheet("Tracks")

    db_papers_dict = dict()
    for db_p in sheet_db_papers.data:
        db_papers_dict[db_p["UID"]] = db_p

    ff_videos_dict = dict()
    for ff in sheet_ff_videos.data:
        ff_videos_dict[ff["FF Source ID"]] = ff

    ff_playlists_dict = dict()
    for ff in sheet_ff_playlists.data:
        ff_playlists_dict[ff["FF P Source ID"]] = ff

    pre_videos_dict = dict()
    for v in sheet_pre_videos.data:
        pre_videos_dict[v["Video Source ID"]] = v

    bunny_dict = dict()
    for bc in sheet_bunny.data:
        bunny_dict[bc["UID"]] = bc

    tracks_dict = dict()
    for t in sheet_tracks.data:
        tracks_dict[t["Track"]] = t

    for e in sheet_events.data:
        e_data = {
            "event": e["Event"],
            "long_name": e["Event"],
            "event_type": e["Event Type"],
            "event_prefix": e["Event Prefix"],
            "event_description": e["Event Description"],
            "event_url": e["Event URL"],
            "organizers": [o.strip() for o in e["Organizers"].split("|")] if e["Organizers"] else [],
            "sessions": []
        }

        if not e_data["event_prefix"] in all_events:
            all_events[e_data["event_prefix"]] = e_data
        else:
            print('Error, duplicate event_prefix')
            print(e_data)

    # Create session data
    for s in sheet_sessions.data:
        sid = s["Session ID"]
        t = tracks_dict[s["Track"]] if s["Track"] in tracks_dict else None
        s_ff = ff_videos_dict[sid] if sid in ff_videos_dict else None

        s_data = {
            "title": s["Session Title"],
            "session_id": sid,
            "event_prefix": s["Event Prefix"],
            "track": s["Track"],
            "session_image": f'{s["Session ID"]}.png',
            "chair": [c.strip() for c in s["Session Chairs"].split("|")] if s["Session Chairs"] else [],
            # "organizers": [], does this need to be filled in?
            "time_start": format_time_iso8601_utc(parse_time(s["DateTime Start"])) if "DateTime Start" in s and s["DateTime Start"] != "" else "",
            "time_end": format_time_iso8601_utc(parse_time(s["DateTime End"])) if "DateTime End" in s and s["DateTime End"] != "" else "",
            "discord_category": "",
            "discord_channel": t["Discord Channel"] if t else "",
            "discord_channel_id": t["Discord Channel ID"] if t else "",
            "discord_link": t["Discord URL"] if t else "",
            # TODO should we create Zooms for some sessions? I think we need this for the CC
            "zoom_private_meeting": "",
            "zoom_private_password": "",
            "zoom_private_link": "",
            "zoom_broadcast_link": "",
            "ff_link": s_ff["FF Link"] if s_ff is not None else (s["Session FF URL"] if s else ""),
            "time_slots": [],
        }

        if export_ics:
            calendar = make_calendar_for_session(s["Session Title"], s["Session ID"], t["Room Name"] if t else "", parse_time(
                s["DateTime Start"]), parse_time(s["DateTime End"]))

            full_calendar.events |= calendar.events

            if s["Event Prefix"] not in event_calendars:
                event_calendars[s["Event Prefix"]] = ics.Calendar()
            event_calendars[s["Event Prefix"]].events |= calendar.events

            # Create the session ics file
            with open(os.path.join(output_dir, "ics", s["Session ID"] + ".ics"), "w", encoding="utf8") as f:
                f.write(calendar.serialize())

        filtered_papers = list(
            filter(lambda p: p["Session ID"] == s_data["session_id"], sheet_papers.data))

        filtered_ext = list(
            filter(lambda e: e["Session ID"] == s_data["session_id"], sheet_ext.data))

        for p in filtered_papers + filtered_ext:
            # Find the corresponding entry by Paper UID in PapersDB
            uid = p["Paper UID"]
            p_db = db_papers_dict[uid] if uid in db_papers_dict else None
            ff = ff_videos_dict[uid] if uid in ff_videos_dict else None
            pv = pre_videos_dict[uid] if uid in pre_videos_dict else None
            bc = bunny_dict[uid] if uid in bunny_dict else None

            p_event_prefix = p_db["Event Prefix"] if p_db else ""

            paper_type = ""
            if p_event_prefix.startswith("v-spotlights"):
                paper_type = "spotlight"
            elif p_event_prefix.startswith("v-panels"):
                paper_type = "panel"
            elif p_event_prefix.startswith("v-short"):
                paper_type = "short"
            elif p_event_prefix.startswith("s-vds"):
                paper_type = "associated"
            elif p_event_prefix.startswith("v-"):
                paper_type = "full"
            elif p_event_prefix.startswith("a-"):
                paper_type = "associated"
            elif p_event_prefix.startswith("w-"):
                paper_type = "workshop"
            elif p_event_prefix.startswith("t-"):
                paper_type = "tutorial"

            p_data = {
                "slot_id": p["Item ID"],
                "session_id": p["Session ID"],
                "title": p["Slot Title"],
                "contributors": [c.strip() for c in p["Slot Contributors"].split("|")] if p["Slot Contributors"] else [],
                "authors": [a.strip() for a in p_db["Authors"].split("|")] if (p_db and "Authors" in p_db and p_db["Authors"]) else [],
                "abstract": p_db["Abstract"] if p_db else "",
                "uid": p["Paper UID"],
                "time_stamp": format_time_iso8601_utc(parse_time(p["Slot DateTime Start"])) if (p and "Slot DateTime Start" in p and p["Slot DateTime Start"] != "") else "",
                "time_start": format_time_iso8601_utc(parse_time(p["Slot DateTime Start"])) if (p and "Slot DateTime Start" in p and p["Slot DateTime Start"] != "") else "",
                "time_end": format_time_iso8601_utc(parse_time(p["Slot DateTime End"])) if (p and "Slot DateTime End" in p and p["Slot DateTime End"] != "") else "",
                "paper_type": paper_type,
                "keywords": [k.strip() for k in p_db["Keywords"].split("|")] if p_db and p_db["Keywords"] else [],
                "doi": p_db["DOI"] if p_db else "",
                "fno": p_db["FNO"] if p_db else "",
                "has_image": p_db["Has Image"] == "1" if p_db else False,
                "has_pdf": p_db["Has PDF"] == "1" if p_db else False,
                "paper_award": p_db["Award"] if p_db else "",
                "image_caption": p_db["Image Caption"] if p_db else "",
                "external_paper_link": "",
                # This comes from FFVideos Sheet
                "youtube_ff_link": ff["FF Link"] if ff else "",
                "youtube_ff_id": ff["FF Video ID"] if ff else "",
                "bunny_ff_link": bc["FF Video Bunny URL"] if bc else "",
                "bunny_ff_subtitles": bc["FF Video Subtitles Bunny URL"] if bc else "",
                # This comes from Videos Sheet
                "youtube_prerecorded_link": pv["Video Link"] if pv else "",
                "youtube_prerecorded_id": pv["Video ID"] if pv else "",
                "bunny_prerecorded_link": bc["Video Bunny URL"] if bc else "",
                "bunny_prerecorded_subtitles": bc["Video Subtitles Bunny URL"] if bc else "",
            }

            s_data["time_slots"].append(p_data)

            if p_db and p_data and p_data["uid"]:
                all_papers[p_data["uid"]] = p_data
            else:
                print(
                    f"MISSING: data for paper UID = {uid}. Items* {('Valid' if p else 'Missing')}. PapersDB is {('Valid' if p_db else 'Missing')}.")

        if s_data["event_prefix"] in all_events:
            all_events[s_data["event_prefix"]]["sessions"].append(s_data)
        else:
            print(
                f"MISSING: event prefix of {s_data['event_prefix']} in all_events.")

    for p in sheet_posters.data:
        p_data = {
            "event": p["Event"],
            "event_prefix": p["Event Prefix"],
            "title": p["Title"],
            "uid": p["UID"],
            "discord_channel": "",
            "authors": [a.strip() for a in p["Authors"].split("|")] if p["Authors"] else [],
            "author_affiliations": [a.strip() for a in p["ACM Author Affiliations"].split(";")] if p["ACM Author Affiliations"] else [],
            "presenting_author_name": p["Presenting Author (name)"],
            "presenting_author_email": p["Presenting Author (email)"],
            "abstract": p["Abstract"],
            "has_summary_pdf": p["Has Summary PDF"] == "1" if p else False,
            "has_poster_pdf": p["Has Poster PDF"] == "1" if p else False,
            "has_image": p["Has Image"] == "1" if p else False,
        }
        if p_data["uid"]:
            all_posters[p_data["uid"]] = p_data

    if export_ics:
        with open(os.path.join(output_dir, "ics", "VIS2023.ics"), "w", encoding="utf8") as f:
            f.write(full_calendar.serialize())

        for k, v in event_calendars.items():
            with open(os.path.join(output_dir, "ics", k + ".ics"), "w", encoding="utf8") as f:
                f.write(v.serialize())

    with open(os.path.join(output_dir, "session_list.json"), "w", encoding="utf8") as f:
        json.dump(all_events, f, indent=4)

    with open(os.path.join(output_dir, "paper_list.json"), "w", encoding="utf8") as f:
        json.dump(all_papers, f, indent=4)

    with open(os.path.join(output_dir, "poster_list.json"), "w", encoding="utf8") as f:
        json.dump(all_posters, f, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to export json, ics, image, and pdf files for web from Conference Database on Google Sheets.')
    # make it possible to use xlsx file?

    parser.add_argument('--img', help='include image files in data output directory',
                        action='store_true', default=False)
    parser.add_argument('--ics', help='include ICS Calendar files in data output directory',
                        action='store_true', default=False)
    parser.add_argument('--pdf', help='include PDF files in data output directory',
                        action='store_true', default=False)

    parser.add_argument(
        '--output_dir', help='output directory for all the web data', default="./")
    args = parser.parse_args()
    auth = Authentication(email=True)

    if args.output_dir:
        # create output data for web
        create_data_for_web(
            auth=auth, output_dir=args.output_dir,
            export_ics=args.ics, export_img=args.img, export_pdf=args.pdf)
