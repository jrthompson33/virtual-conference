from pathlib import PurePath, Path
import pathlib
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
    
    num_scheduled = 0

    max_n_schedules = 25
    if args.max_n_uploads and args.max_n_uploads < max_n_schedules:
        max_n_schedules = args.max_n_uploads
    num_to_schedule = len(data)
    if num_to_schedule > max_n_schedules:
        num_to_schedule = max_n_schedules
    print(f"{num_to_schedule} broadcasts will be scheduled")
    for broadcast in data:
        l_id :str = broadcast["Livestream ID"]
        title : str = broadcast["Title"]
        description :str = broadcast["Description"]
        thumbnail_path : str = broadcast["Thumbnail File Name"]
        use_thumbnail : bool = False
        if thumbnail_path and len(thumbnail_path) > 0:
            if args.path and len(args.path) > 0:
                thumbnail_path = os.path.join(args.path, thumbnail_path)
            if os.path.isfile(thumbnail_path):
                use_thumbnail = True

        stream_key_id = broadcast["Stream Key ID"]
        captions_enabled = broadcast["Captions Enabled"] == "y"
        start_dt = broadcast["Start DateTime"]
        print(f"\r\nschedule broadcast {l_id} - {title}...")
        if not start_dt or not start_dt.endswith("Z"):
            print(f"ERROR: invalid start date time provided, has to be in ISO format, UTC")
            continue
        dt = datetime.fromisoformat(start_dt.replace('Z', '+00:00'))
        res = yt.schedule_broadcast(title, description, dt, 
                                    enable_captions=captions_enabled, 
                                    thumbnail_path = thumbnail_path if use_thumbnail else None)
        print(json.dumps(res))
        broadcast_id = res["id"]
        broadcast["Video ID"] = broadcast_id
        broadcast["YouTube URL"] = "https://youtu.be/" + broadcast_id
        broadcasts.save()
        num_scheduled += 1
        print(f"\r\nbind stream {stream_key_id} to broadcast {l_id} with id {broadcast_id}...")
        res = yt.bind_stream_to_broadcast(stream_key_id, broadcast_id)
        print(json.dumps(res))

        if num_scheduled >= max_n_schedules:
            print("max num of schedules reached.")
            return

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
        title = f"{ev_title} - Fast Forwards | {args.venue}"
        desc = f"Fast forwards for event '{ev_title}' at {args.venue}"
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
        if s["Track"] == "various":
            continue #not livestreamed
        s_title = s["Session Title"]
        title = f"{s_title} - Fast Forwards | {args.venue}"        
        desc = f"Fast forwards for session '{s_title}' at {args.venue}"
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

def populate_pl_sheet(args : argparse.Namespace):
    """Enrich sheet "Playlists" with playlists to create based on events and sessions
    """
    sessions = GoogleSheets()
    sessions.load_sheet("Sessions")
    events = GoogleSheets()
    events.load_sheet("Events")
    playlists = GoogleSheets()
    playlists.load_sheet("Playlists")

    num_added = 0

    #add playlist rows for each event
    for ev in events.data:
        src_id = ev["Event Prefix"]
        if src_id in playlists.data_by_index:
            continue
        ev_title = ev["Event"]
        title = f"{ev_title} - Presentations | {args.venue}"
        desc = f"Pre-recorded presentations for event '{ev_title}' at {args.venue}"
        item = {}
        item["P Source ID"] = src_id
        item["P ID"] = ""
        item["P Title"] = title
        item["P Description"] = desc
        playlists.data.append(item)
        playlists.data_by_index[src_id] = item
        num_added += 1

    #add playlist rows for each session
    for s in sessions.data:
        src_id = s["Session ID"]
        if src_id in playlists.data_by_index:
            continue
        if s["Track"] == "various":
            continue #not livestreamed

        s_title = s["Session Title"]
        title = f"{s_title} - Presentations | {args.venue}"        
        desc = f"Pre-recorded presentations for session '{s_title}' at {args.venue}"
        item = {}
        item["P Source ID"] = src_id
        item["P ID"] = ""
        item["P Title"] = title
        item["P Description"] = desc
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

def create_playlists(yt : YouTubeHelper):
    """Create youtube playlists based on sheet "Playlists"
    """
    playlists = GoogleSheets()
    playlists.load_sheet("Playlists")

    num_added = 0
    for row in playlists.data:
        ex_id = row["P ID"]
        if ex_id and len(ex_id) > 0:
            continue #playlist already created
        title = row["P Title"]
        desc = row["P Description"]
        print(f"\r\ncreating playlist titled '{title}'...")
        res = yt.create_playlist(title, desc)
        print(json.dumps(res))
        row["P ID"] = res["id"]
        num_added += 1
        playlists.save()

    print(f"{num_added} playlists created.")

def find_file(path : str, file_name : str) -> pathlib.Path:
    """find and return file (Path object) with specified name inside folder (recursively)
    """
    if not path or len(path) == 0:
        return None
    for fp in Path(path).rglob("*" + file_name):
        if fp.name == file_name:
            return fp
    return None


def upload_ff_videos(yt : YouTubeHelper, args : argparse.Namespace):
    """upload fast forwards based on FFVideos sheet and specified path
    """
    path = Path(args.path)
    
    channel_id = args.channel_id
    uploads_p_id = "UU" + channel_id[2:]

    playlists = GoogleSheets()
    playlists.load_sheet("FFPlaylists")
    ff_videos = GoogleSheets()
    ff_videos.load_sheet("FFVideos")
    num_playlists_created = 0
    num_videos_uploaded = 0

    max_n_uploads = 100
    if args.max_n_uploads and args.max_n_uploads < max_n_uploads:
        max_n_uploads = args.max_n_uploads
    for row in ff_videos.data:
        ex_id = row["FF Video ID"]
        if ex_id and len(ex_id) > 0:
            continue #already uploaded
        src_id = row["FF Source ID"]
        print(f"\r\nprocessing {src_id}")
        video_path = find_file(args.path, row["FF File Name"])
        subs_path = find_file(args.path, row["FF Subtitles File Name"])
        thumb_path = find_file(args.path, row["FF Thumbnail File Name"])
        if not video_path:
            print(f"ERROR: video not found: {video_path}")
            continue
        
        #upload video
        print(f"\r\nuploading video {video_path}")
        v_res = yt.upload_video(str(video_path), row["FF Title"], row["FF Description"])
        print(json.dumps(v_res))
        video_id = v_res["id"]
        row["FF Video ID"] = video_id
        row["FF Link"] = "https://youtu.be/" + video_id
        
        ff_videos.save()
        num_videos_uploaded += 1

        #make sure all referenced playlists are created
        playlist_refs = row["FF Playlists"].split("|")
        
        for p in playlist_refs:
            if p not in playlists.data_by_index:
                print(f"WARNING: could not find playlist {p}")
                continue
            p_row = playlists.data_by_index[p]
            playlist_id = p_row["FF P ID"]
            if not playlist_id or len(playlist_id) == 0:
                #we first have to create playlist
                title = p_row["FF P Title"]
                desc = p_row["FF P Description"]
                print(f"\r\ncreating playlist titled '{title}'...")
                res = yt.create_playlist(title, desc)
                print(json.dumps(res))
                p_row["FF P ID"] = res["id"]
                playlist_id = res["id"]
                num_playlists_created += 1
                playlists.save()
            
            #add to playlists
            print(f"\r\nadd video to playlist {playlist_id}")
            p_res = yt.add_video_to_playlist(playlist_id, video_id)
            print(json.dumps(p_res))
            if not p_row["FF P Link"] or len(p_row["FF P Link"]) == 0:
                #we can now create proper watch link for playlist because we have uploaded first video
                p_row["FF P Link"] = f"https://www.youtube.com/watch?v={video_id}&list={playlist_id}"
                playlists.save()
                                
        #set thumbnail
        if thumb_path:
            print(f"\r\nsetting thumbnail {thumb_path}")
            t_res = yt.set_thumbnail(video_id, str(thumb_path))
            print(json.dumps(t_res))
        #upload captions
        if subs_path:
            print(f"\r\nuploading captions {subs_path}")
            c_res = yt.upload_subtitles(video_id, str(subs_path))
            print(json.dumps(c_res))

        if num_videos_uploaded >= max_n_uploads:
            print("max num of uploads reached.")
            return
        

def upload_videos(yt : YouTubeHelper, args : argparse.Namespace):
    """upload presentation videos based on Videos sheet and specified path
    """
    path = Path(args.path)
    
    channel_id = args.channel_id
    uploads_p_id = "UU" + channel_id[2:]

    playlists = GoogleSheets()
    playlists.load_sheet("Playlists")
    videos = GoogleSheets()
    videos.load_sheet("Videos")
    num_playlists_created = 0
    num_videos_uploaded = 0

    max_n_uploads = 100
    if args.max_n_uploads and args.max_n_uploads < max_n_uploads:
        max_n_uploads = args.max_n_uploads
    for row in videos.data:
        ex_id = row["Video ID"]
        if ex_id and len(ex_id) > 0:
            continue #already uploaded
        src_id = row["Video Source ID"]
        print(f"\r\nprocessing {src_id}")
        video_path = find_file(args.path, row["Video File Name"])
        subs_path = find_file(args.path, row["Video Subtitles File Name"])
        thumb_path = find_file(args.path, row["Video Thumbnail File Name"])
        if not video_path:
            print(f"ERROR: video not found: {video_path}")
            continue
        
        #upload video
        print(f"\r\nuploading video {video_path}")
        v_res = yt.upload_video(str(video_path), row["Video Title"], row["Video Description"])
        print(json.dumps(v_res))
        video_id = v_res["id"]
        row["Video ID"] = video_id
        row["Video Link"] = "https://youtu.be/" + video_id
        
        videos.save()
        num_videos_uploaded += 1

        #make sure all referenced playlists are created
        playlist_refs = row["Playlists"].split("|")
        
        for p in playlist_refs:
            if p not in playlists.data_by_index:
                print(f"WARNING: could not find playlist {p}")
                continue
            p_row = playlists.data_by_index[p]
            playlist_id = p_row["P ID"]
            if not playlist_id or len(playlist_id) == 0:
                #we first have to create playlist
                title = p_row["P Title"]
                desc = p_row["P Description"]
                print(f"\r\ncreating playlist titled '{title}'...")
                res = yt.create_playlist(title, desc)
                print(json.dumps(res))
                p_row["P ID"] = res["id"]
                playlist_id = res["id"]
                num_playlists_created += 1
                playlists.save()
            
            #add to playlists
            print(f"\r\nadd video to playlist {playlist_id}")
            p_res = yt.add_video_to_playlist(playlist_id, video_id)
            print(json.dumps(p_res))
            if not p_row["P Link"] or len(p_row["P Link"]) == 0:
                #we can now create proper watch link for playlist because we have uploaded first video
                p_row["P Link"] = f"https://www.youtube.com/watch?v={video_id}&list={playlist_id}"
                playlists.save()
                                
        #set thumbnail
        if thumb_path:
            print(f"\r\nsetting thumbnail {thumb_path}")
            t_res = yt.set_thumbnail(video_id, str(thumb_path))
            print(json.dumps(t_res))
        #upload captions
        if subs_path:
            print(f"\r\nuploading captions {subs_path}")
            c_res = yt.upload_subtitles(video_id, str(subs_path))
            print(json.dumps(c_res))

        if num_videos_uploaded >= max_n_uploads:
            print("max num of uploads reached.")
            return
        
        

def populate_videos(args : argparse.Namespace):
    """populate FFVideos or Videos sheet based on videos in specified path
    """
    path = Path(args.path)
    is_ff : bool = args.populate_ff_videos
    playlists = GoogleSheets()
    playlists.load_sheet("FFPlaylists" if is_ff else "Playlists")
    papers = GoogleSheets()
    papers.load_sheet("PapersDB")
    sessions = GoogleSheets()
    sessions.load_sheet("Sessions")
    ff_videos = GoogleSheets()
    ff_videos.load_sheet("FFVideos" if is_ff else "Videos")
    items1 = GoogleSheets()
    items1.load_sheet("ItemsVISPapers-A")
    items2 = GoogleSheets()
    items2.load_sheet("ItemsVISSpecial")
    items3 = GoogleSheets()
    items3.load_sheet("ItemsEXT")
    events = GoogleSheets()
    events.load_sheet("Events")
    
    num_added = 0
    to_add = []
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

        session_id = ""
        ref_playlists = []
        start_time = ""
        title = ""
        desc = ""

        is_session_video = False
        if uid in sessions.data_by_index:
            is_session_video = True            
        else:
            is_session_video = False
            if uid not in papers.data_by_index:
                print(f"ERROR: could not find paper of file: '{fp.name}'")
                continue
        
        
        if is_session_video:
            session_id = uid
            session = sessions.data_by_index[uid]
            start_time = session["DateTime Start"]
            if session_id in playlists.data_by_index:
                ref_playlists.append(session_id)
            event_title = ""
            event = session["Event Prefix"]
            if event and len(event) > 0:
                if event in playlists.data_by_index:
                    ref_playlists.append(event)
                for event_row in events.data:
                    if event_row["Event Prefix"] == event:
                        event_title = event_row["Event"]
                        break
            session_title = session["Session Title"]
            title = f"{session_title} Session - Fast Forward | {args.venue}" if is_ff else f"{session_title} Session | {args.venue}"
            desc = f"{event_title} Fast Forward for session {session_title}" if is_ff else f"{event_title}: {session_title}"

        else:
            paper = papers.data_by_index[uid]
            item_uid = uid + "-pres"
            
            items_by_index = None
            if item_uid in items1.data_by_index:
                items_by_index = items1.data_by_index
            elif item_uid in items2.data_by_index:
                items_by_index = items2.data_by_index
            elif item_uid in items3.data_by_index:
                items_by_index = items3.data_by_index

            if items_by_index:
                session_id = items_by_index[item_uid]["Session ID"]
                start_time = items_by_index[item_uid]["Slot DateTime Start"]

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
            title = f"{paper_title} - Fast Forward | {args.venue}" if is_ff else f"{paper_title} | {args.venue}"
            desc = f"{event_title} Fast Forward: {paper_title}\r\nAuthors: {authors}" if is_ff else f"{event_title}: {paper_title}\r\nAuthors: {authors}"


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
        if is_ff:
            ffvideo = {          
                "FF Source ID" : uid,
                "FF File Name" : fp.name,
                "FF Subtitles File Name" : subs_fn,
                "FF Thumbnail File Name" : thumb_fn,
                "FF Title" : title,
                "FF Description" : desc,
                "Session ID" : session_id,
                "Slot DateTime Start": start_time,
                "FF Playlists" : "|".join(ref_playlists),
                "FF Video ID" : "",
                "FF Link" : ""
                }
            to_add.append(ffvideo)
        else:
            video = {          
                "Video Source ID" : uid,
                "Video File Name" : fp.name,
                "Video Subtitles File Name" : subs_fn,
                "Video Thumbnail File Name" : thumb_fn,
                "Video Title" : title,
                "Video Description" : desc,
                "Session ID" : session_id,
                "Slot DateTime Start": start_time,
                "Playlists" : "|".join(ref_playlists),
                "Video ID" : "",
                "Video Link" : ""
                }
            to_add.append(video)
        num_added += 1
    #important to add videos in correct order to playlist based on their scheduled time
    to_add = sorted(to_add, key=lambda it: ( it["Session ID"], it["Slot DateTime Start"]) )
    for it in to_add:        
        ff_videos.data.append(it)
        ff_videos.data_by_index[it["FF Source ID" if is_ff else "Video Source ID"]] = it
    ff_videos.save()
    print(f"{num_added} rows added.")


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(
        description='Script to perform various API actions for YouTube.')

    
    parser.add_argument('--playlists', help='retrieve playlists',
                        action='store_true', default=False)
    parser.add_argument('--playlist', help='retrieve playlist',
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
    parser.add_argument('--playlist_items', help='retrieve all playlist items of a playlist',
                        action='store_true', default=False)
    parser.add_argument('--create_playlist', help='create playlist',
                        action='store_true', default=False)
    parser.add_argument('--create_playlists', help='create video playlists from sheet',
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
    parser.add_argument('--upload_ff_videos', help='upload FF videos in specified path and based on FFVideos sheet',
                        action='store_true', default=False)
    parser.add_argument('--upload_videos', help='upload presentation videos in specified path and based on Videos sheet',
                        action='store_true', default=False)

    
    parser.add_argument('--populate_ffpl_sheet', help='populate fast forward playlists sheet based on events and sessions',
                        action='store_true', default=False)
    parser.add_argument('--populate_ff_videos', help='populate fast forward videos sheet based on files in specified folder',
                        action='store_true', default=False)

    
    parser.add_argument('--populate_pl_sheet', help='populate video playlists sheet based on events and sessions',
                        action='store_true', default=False)
    parser.add_argument('--populate_videos', help='populate videos sheet based on files in specified folder',
                        action='store_true', default=False)
    
    parser.add_argument('--id', help='id of item (e.g., video)', default=None)
    parser.add_argument('--channel_id', help='id of channel', default=None)
    parser.add_argument('--stream_key', help='id of stream key', default=None)
    parser.add_argument('--title', help='title of item (e.g., video)', default=None)
    parser.add_argument('--description', help='description of item (e.g., video)', default=None)
    parser.add_argument('--start_time', help='start time of scheduled broadcast in the "%Y-%m-%d %H:%M" format in your local time zone', default=None)
    parser.add_argument('--path', help='path to file or directory that should be uploaded, e.g. video file', default=None)
    parser.add_argument('--dow', help='day of week for scheduling broadcasts', default=None)
    parser.add_argument('--venue', help='venue title for titles, descriptions', default="VIS 2022")
    parser.add_argument('--max_n_uploads', help='maximum number of video uploads', default=10, type=int)


    
    args = parser.parse_args()

    yt = YouTubeHelper()

    if args.playlists:
        playlists = yt.get_all_playlists()
        print(json.dumps(playlists))
    elif args.playlist:
        playlists = yt.get_playlist(args.id)
        print(json.dumps(playlists))
    elif args.streams:        
        res = yt.get_streams()
        print(json.dumps(res))
    elif args.playlists_items:
        res = yt.get_playlists_and_videos()
        print(json.dumps(res))
    elif args.playlist_items:
        res = yt.get_playlist_items(args.id)
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
    elif args.populate_pl_sheet:
        populate_pl_sheet(args)
    elif args.create_playlists:
        create_playlists(yt)
    elif args.create_ff_playlists:
        create_ff_playlists(yt)
    elif args.populate_ff_videos:
        populate_videos(args)
    elif args.populate_videos:
        populate_videos(args)
    elif args.upload_ff_videos:
        upload_ff_videos(yt, args)
    elif args.upload_videos:
        upload_videos(yt, args)