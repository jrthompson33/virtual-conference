from pathlib import PurePath, Path
import sys
import os
import time
import glob
import argparse
import json
from datetime import datetime

from core.yt_helper import YouTubeHelper
from core.google_sheets import GoogleSheets

def schedule_broadcasts(yt : YouTubeHelper, args : argparse.Namespace):
    """schedule broadcasts from sheet, possibly filtered by dow = Day of Week
    """
    broadcasts = GoogleSheets()
    broadcasts.load_sheet("Broadcasts")
    data = broadcasts.data
    print(f"{len(data)} broadcasts loaded")
    data = list(filter(lambda d: d["Video ID"] == None or len(d["Video ID"].strip()) == 0, data))
    if args.dow:
        data = list(filter(lambda d: d["Day of Week"] == args.dow, data))
    print(f"{len(data)} broadcasts will be scheduled")
    for broadcast in data:
        l_id = broadcast["Livestream ID"]
        title = broadcast["Title"]
        description = broadcast["Description"]
        thumbnail_path = broadcast["Thumbnail File Name"]
        stream_key_id = broadcast["Stream Key ID"]
        captions_enabled = broadcast["Captions Enabled"] == "y"
        start_dt = broadcast["Start DateTime"]
        print(f"\r\nschedule broadcast {l_id} - {title}...")
        if not start_dt or not start_dt.endswith("Z"):
            print(f"ERROR: invalid start date time provided, has to be in ISO format, UTC")
            continue
        dt = datetime.fromisoformat(start_dt.replace('Z', '+00:00'))
        res = yt.schedule_broadcast(title, description, dt, enable_captions=captions_enabled)
        print(json.dumps(res))
        broadcast_id = res["id"]
        broadcast["Video ID"] = broadcast_id
        broadcast["YouTube URL"] = "https://youtu.be/" + broadcast_id
        broadcasts.save()
        print(f"\r\nbind stream {stream_key_id} to broadcast {l_id} with id {broadcast_id}...")
        res = yt.bind_stream_to_broadcast(stream_key_id, broadcast_id)
        print(json.dumps(res))

def populate_ffpl_sheet(args : argparse.Namespace):
    """Enrich sheet "FFPlaylists" with playlists to create based on events and sessions
    """
    sessions = GoogleSheets()
    sessions.load_sheet("Sessions")
    events = GoogleSheets()
    events.load_sheet("Events")
    playlists = GoogleSheets()
    playlists.load_sheet("FFPlaylists")

    num_added = 0

    #add playlist rows for each event
    for ev in events.data:
        src_id = ev["Event Prefix"]
        if src_id in playlists.data_by_index:
            continue
        ev_title = ev["Event"]
        title = f"{args.venue}: Fast Forwards - {ev_title}"
        desc = f"Fast forwards for event '{ev_title}'"
        item = {}
        item["FF P Source ID"] = src_id
        item["FF P ID"] = ""
        item["FF P Title"] = title
        item["FF P Description"] = desc
        playlists.data.append(item)
        playlists.data_by_index[src_id] = item
        num_added += 1

    #add playlist rows for each session
    for s in sessions.data:
        src_id = s["Session ID"]
        if src_id in playlists.data_by_index:
            continue
        s_title = s["Session Title"]
        title = f"{args.venue}: Fast Forwards - {s_title}"
        desc = f"Fast forwards for session '{s_title}'"
        item = {}
        item["FF P Source ID"] = src_id
        item["FF P ID"] = ""
        item["FF P Title"] = title
        item["FF P Description"] = desc
        playlists.data.append(item)
        playlists.data_by_index[src_id] = item
        num_added += 1

    playlists.save()
    print(f"{num_added} playlist rows added.")

def create_ff_playlists(yt : YouTubeHelper):
    """Create youtube playlists based on sheet "FFPlaylists"
    """
    playlists = GoogleSheets()
    playlists.load_sheet("FFPlaylists")

    num_added = 0
    for row in playlists.data:
        ex_id = row["FF P ID"]
        if ex_id and len(ex_id) > 0:
            continue #playlist already created
        title = row["FF P Title"]
        desc = row["FF P Description"]
        print(f"\r\ncreating playlist titled '{title}'...")
        res = yt.create_playlist(title, desc)
        print(json.dumps(res))
        row["FF P ID"] = res["id"]
        num_added += 1
        playlists.save()

    print(f"{num_added} playlists created.")

def populate_ff_videos(args : argparse.Namespace):
    """populate FFVideos sheet based on videos in specified path
    """
    path = Path(args.path)
    playlists = GoogleSheets()
    playlists.load_sheet("FFPlaylists")
    papers = GoogleSheets()
    papers.load_sheet("PapersDB")
    ff_videos = GoogleSheets()
    ff_videos.load_sheet("FFVideos")
    items1 = GoogleSheets()
    items1.load_sheet("ItemsVISPapers-A")
    items2 = GoogleSheets()
    items2.load_sheet("ItemsVISSpecial")
    items3 = GoogleSheets()
    items3.load_sheet("ItemsEXT")
    
    num_added = 0
    for fp in path.rglob("*.mp4"):        
        print(fp)
        cur_dir = str(fp.parent)
        pure_name = fp.name[:-4] #file name without extension .mp4
        print("pure: " + pure_name)
        id_idx = pure_name.find("_")
        if id_idx == -1:
            print(f"ERROR: file does not begin with id: '{fp.name}'")
            continue
        uid = pure_name[:id_idx]
        if uid in ff_videos.data_by_index:
            continue #already present
        if uid not in papers.data_by_index:
            print(f"ERROR: could not find paper of file: '{fp.name}'")
            continue
        paper = papers.data_by_index[uid]
        session_id = ""
        ref_playlists = []
        item_uid = uid + "-pres"
        if item_uid in items1.data_by_index:
            session_id = items1.data_by_index[item_uid]["Session ID"]
        elif item_uid in items2.data_by_index:
            session_id = items2.data_by_index[item_uid]["Session ID"]
        elif item_uid in items3.data_by_index:
            session_id = items3.data_by_index[item_uid]["Session ID"]
        if session_id and len(session_id) > 0 and session_id in playlists.data_by_index:
            ref_playlists.append(session_id)
        event_title = paper["Event"]
        event = paper["Event Prefix"]
        if event and len(event) > 0 and event in playlists.data_by_index:
            ref_playlists.append(event)
        paper_title = paper["Title"]
        authors :str = paper["Authors"]
        if authors and len(authors) > 0:
            authors = authors.replace("|", ", ")
        title = f"{args.venue}: Fast Forward - {paper_title}"
        desc = f"{event_title} Fast Forward: {paper_title}\r\nAuthors: {authors}"
        subs_fn = ""
        thumb_fn = ""
        prefix = os.path.join(cur_dir, pure_name)
        if os.path.isfile(prefix + ".srt"):
            subs_fn = pure_name + ".srt"
        elif os.path.isfile(prefix + ".sbv"):
            subs_fn = pure_name + ".sbv"
        if os.path.isfile(prefix + ".png"):
            thumb_fn = pure_name + ".png"
        elif os.path.isfile(prefix + ".jpg"):
            thumb_fn = pure_name + ".jpg"
        ffvideo = {          
            "FF Source ID" : uid,
            "FF File Name" : fp.name,
            "FF Subtitles File Name" : subs_fn,
            "FF Thumbnail File Name" : thumb_fn,
            "FF Title" : title,
            "FF Description" : desc,
            "FF Playlists" : "|".join(ref_playlists),
            "FF Video ID" : "",
            "FF Link" : ""
            }
        ff_videos.data.append(ffvideo)
        ff_videos.data_by_index[uid] = ffvideo
        num_added += 1
    ff_videos.save()
    print(f"{num_added} rows added.")


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(
        description='Script to perform various API actions for YouTube.')

    
    parser.add_argument('--playlists', help='retrieve playlists',
                        action='store_true', default=False)
    parser.add_argument('--streams', help='retrieve livestreams',
                        action='store_true', default=False)
    
    parser.add_argument('--videos', help='retrieve videos',
                        action='store_true', default=False)
    parser.add_argument('--video', help='retrieve details of one specified video',
                        action='store_true', default=False)
    parser.add_argument('--channel', help='retrieve details of channel',
                        action='store_true', default=False)
    parser.add_argument('--update_video', help='update details of specified video',
                        action='store_true', default=False)
    parser.add_argument('--playlists_items', help='retrieve playlists and all items',
                        action='store_true', default=False)
    parser.add_argument('--create_playlist', help='create playlist',
                        action='store_true', default=False)
    parser.add_argument('--create_ff_playlists', help='create FF playlists from sheet',
                        action='store_true', default=False)
    
    parser.add_argument('--broadcasts', help='retrieve broadcasts',
                        action='store_true', default=False)
    parser.add_argument('--schedule_broadcast', help='schedule broadcast',
                        action='store_true', default=False)
    parser.add_argument('--schedule_broadcasts', help='schedule and bind broadcasts from sheet',
                        action='store_true', default=False)
    parser.add_argument('--bind', help='bind stream to broadcast',
                        action='store_true', default=False)
    parser.add_argument('--unbind', help='unbind stream from broadcast',
                        action='store_true', default=False)
    parser.add_argument('--start_broadcast', help='start broadcast',
                        action='store_true', default=False)
    parser.add_argument('--stop_broadcast', help='stop broadcast',
                        action='store_true', default=False)
    parser.add_argument('--upload_video', help='upload video',
                        action='store_true', default=False)

    
    parser.add_argument('--populate_ffpl_sheet', help='populate fast forward playlists sheet based on events and sessions',
                        action='store_true', default=False)
    parser.add_argument('--populate_ff_videos', help='populate fast forward videos sheet based on files in specified folder',
                        action='store_true', default=False)
    
    parser.add_argument('--id', help='id of item (e.g., video)', default=None)
    parser.add_argument('--stream_key', help='id of stream key', default=None)
    parser.add_argument('--title', help='title of item (e.g., video)', default=None)
    parser.add_argument('--description', help='description of item (e.g., video)', default=None)
    parser.add_argument('--start_time', help='start time of scheduled broadcast in the "%Y-%m-%d %H:%M" format in your local time zone', default=None)
    parser.add_argument('--path', help='path to file or directory that should be uploaded, e.g. video file', default=None)
    parser.add_argument('--dow', help='day of week for scheduling broadcasts', default=None)
    parser.add_argument('--venue', help='venue title for titles, descriptions', default="VIS 2022")

    
    args = parser.parse_args()

    yt = YouTubeHelper()

    if args.playlists:
        playlists = yt.get_all_playlists()
        print(json.dumps(playlists))
    elif args.streams:        
        res = yt.get_streams()
        print(json.dumps(res))
    elif args.playlists_items:
        res = yt.get_playlists_and_videos()
        print(json.dumps(res))
    elif args.create_playlist:
        pl = yt.create_playlist(args.title)
        print(json.dumps(pl))
    elif args.broadcasts:
        res = yt.get_broadcasts()
        print(json.dumps(res))
    elif args.schedule_broadcast:
        dt = datetime.strptime(args.start_time, "%Y-%m-%d %H:%M")
        res = yt.schedule_broadcast(args.title, args.description, dt)
        print(json.dumps(res))
    elif args.schedule_broadcasts:
        schedule_broadcasts(yt, args)
    elif args.upload_video:
        res = yt.upload_video(args.path, args.title, args.description)
        print(json.dumps(res))
    elif args.channel:
        res = yt.get_channel()
        print(json.dumps(res))
    elif args.videos:
        res = yt.get_videos()
        print(json.dumps(res))
    elif args.video:
        res = yt.get_video(args.id)
        print(json.dumps(res))
    elif args.update_video:
        res = yt.update_video(args.id, args.title, args.description)
        print(json.dumps(res))
    elif args.bind:
        res = yt.bind_stream_to_broadcast(args.stream_key, args.id)
        print(json.dumps(res))
    elif args.unbind:
        res = yt.bind_stream_to_broadcast(None, args.id)
        print(json.dumps(res))
    elif args.start_broadcast:
        res = yt.make_broadcast_live(args.id, args.stream_key)
        print(json.dumps(res))
    elif args.stop_broadcast:
        res = yt.stop_and_unbind_broadcast(args.id)
        print(json.dumps(res))
    elif args.populate_ffpl_sheet:
        populate_ffpl_sheet(args)
    elif args.create_ff_playlists:
        create_ff_playlists(yt)
    elif args.populate_ff_videos:
        populate_ff_videos(args)