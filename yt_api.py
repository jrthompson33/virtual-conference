import sys
import os
import time
import argparse

from core.yt_helper import YouTubeHelper


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to perform various API actions for YouTube.')

    parser.add_argument('--playlists', help='retrieve playlists',
                        action='store_true', default=False)
    parser.add_argument('--playlists_items', help='retrieve playlists and all items',
                        action='store_true', default=False)

    yt = YouTubeHelper()

    if args.playlists:
        playlists = yt.get_all_playlists()
        print(playlists)
    elif args.playlists_items:
        res = yt.get_playlists_and_videos()
        print(res)
