import sys
import os
import time
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
    
    parser.add_argument('--id', help='id of item (e.g., video)', default=None)
    parser.add_argument('--stream_key', help='id of stream key', default=None)
    parser.add_argument('--title', help='title of item (e.g., video)', default=None)
    parser.add_argument('--description', help='description of item (e.g., video)', default=None)
    parser.add_argument('--start_time', help='start time of scheduled broadcast in the "%Y-%m-%d %H:%M" format in your local time zone', default=None)
    parser.add_argument('--path', help='path to file that should be uploaded, e.g. video file', default=None)
    parser.add_argument('--dow', help='day of week for scheduling broadcasts', default=None)

    
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