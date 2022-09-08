from pydoc import describe
import sys
import io
import os
import http.client
import httplib2
import time
from apiclient.http import MediaFileUpload
from apiclient.errors import HttpError
import argparse
from typing import List
from datetime import timezone, datetime, timedelta

import core.auth as conf_auth

RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, http.client.NotConnected,
        http.client.IncompleteRead, http.client.ImproperConnectionState,
        http.client.CannotSendRequest, http.client.CannotSendHeader,
        http.client.ResponseNotReady, http.client.BadStatusLine)

class YouTubeHelper:
    def __init__(self):
        """YouTube helper class to perform various actions, will immediately authenticate upon class instantiation
        """
        self.auth = conf_auth.Authentication(youtube=True, use_pickled_credentials=True)

    def make_youtube_title(self, title : str) -> str:
        """Make sure title is valid for Youtube: <= 100 characters and no '<' or '>' symbols
        """
        if title is None:
            return None
            
        title = title.replace("<", " ").replace(">", " ")
        if len(title) > 100:
            title = title[0:99]
        return title

    def make_youtube_description(self, description : str) -> str:
        """Similar rules for the description as the title, but max length of 5000 characters
        """
        if description is None:
            return None
        description = description.replace("<", " ").replace(">", " ")
        if len(description) > 5000:
            description = description[0:4999]
        return description

    def create_playlist(self, title : str):
        """Create playlist.

        Returns something like {
                  "kind": "youtube#playlist",
                  "etag": "7s-K....",
                  "id": "PL...",
                  "snippet": {
                    "publishedAt": "2022-09-06T13:48:25Z",
                    "channelId": "UCBJ....",
                    "title": "This is a test playlist automatically generated",
                    "description": "",
                    "thumbnails": {
                      "default": {
                        "url": "https://i.ytimg.com/img/no_thumbnail.jpg",
                        "width": 120,
                        "height": 90
                      },
                      "medium": {
                        "url": "https://i.ytimg.com/img/no_thumbnail.jpg",
                        "width": 320,
                        "height": 180
                      },
                      "high": {
                        "url": "https://i.ytimg.com/img/no_thumbnail.jpg",
                        "width": 480,
                        "height": 360
                      }
                    },
                    "channelTitle": "IEEE Visualization Conference",
                    "localized": {
                      "title": "This is a test playlist automatically generated",
                      "description": ""
                    }
                  },
                  "status": {
                    "privacyStatus": "unlisted"
                  }
                }
        """
        title = self.make_youtube_title(title)
        resp = self.auth.youtube.playlists().insert(
            part="id,status,snippet",
            body={
                "snippet": {
                    "title": title
                },
                "status": {
                    "privacyStatus": "unlisted"
                }
            }).execute()
        return resp

    def add_video_to_playlist(self, playlist_id : str, video_id : str):
        """Add existing video to existing playlist
        """
        resp = self.auth.youtube.playlistItems().insert(
                part="id,status,snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }).execute()
        return resp
        
    def upload_video(self, path : str, title : str, description : str):
        title = self.make_youtube_title(title)
        description = self.make_youtube_description(description)
        upload_request = self.auth.youtube.videos().insert(
            part="id,status,snippet",
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "categoryId": 27 # Category 27 is "education"
                },
                "status": {
                    "privacyStatus": "unlisted",
                    "selfDeclaredMadeForKids": False,
                    "embeddable": True
                }
            },
            # MediaFileUpload('cow.png', mimetype='image/png', chunksize=1024*1024, resumable=True)
            #Depending on the platform you are working on, you may pass -1 as the
            #chunksize, which indicates that the entire file should be uploaded in a single
            #request.
            media_body=MediaFileUpload(path, chunksize=-1, resumable=True)
        )

        httplib2.RETRIES = 1
        response = None
        error = None
        retries = 0
        while not response:
            try:
                print(f"Uploading Video:\ntitle = {title}\nvideo = {path}")
                status, response = upload_request.next_chunk()
                if response:
                    if "id" in response:
                        print(f"Uploaded\ntitle = {title}\nvideo = {path}")
                        return response
                    else:
                        print("Upload failed with an unexpected response")
                        return None
            except HttpError as e:
                if e.resp.status in RETRIABLE_STATUS_CODES:
                    error = f"Retriable HTTP error {e.resp.status}: {e.content}"
                else:
                    raise e
            except RETRIABLE_EXCEPTIONS as e:
                error = f"A retriable exception occured {e}"

            if error:
                print(error)
                retries += 1
                if retries > 10:
                    print("Reached max retries, aborting")
                    break
                time.sleep(1)

        return None

    def update_video(self, video_id : str, title : str, description : str, privacy : str = "unlisted"):
        #print("Updating\ntitle = {}\nvideo = {}".format(title, video_id))
        title = self.make_youtube_title(title)
        description = self.make_youtube_description(description)
        resp = self.auth.youtube.videos().update(
            part="id,snippet,status",
            body = {
                "id": video_id,
                "snippet": {
                    "title": title,
                    "description": description,
                    "categoryId": 27 # Category 27 is "education"
                },
                "status": {
                    "selfDeclaredMadeForKids": False,
                    "embeddable": True,
                    "privacyStatus": privacy
                }
            }
        ).execute()
        return resp

    def set_video_embeddable(self, video_id : str):
        """Make sure that 'embeddable' is set to True of specified video
        (e.g., after live broadcast has stoppped)
        """
        resp = self.auth.youtube.videos().update(
            part="id,contentDetails,status",
            body={
                "id": video_id,
                "status": {
                    "embeddable": True,
                }
            }
        ).execute()
        return resp

    def upload_subtitles(self, video_id : str, subtitles_path : str, name : str = "English Subtitles",
                        language : str = "en-us"):
        """Upload subtitles file to specified video
        """
        resp = self.auth.youtube.captions().insert(
                    part="id,snippet",
                    body={
                        "snippet": {
                            "videoId": video_id,
                            "language": language,
                            "name": name
                        }
                    },
                    media_body=MediaFileUpload(subtitles)
                ).execute()
        return resp

    def schedule_broadcast(self, title : str, description : str, start_time : datetime, enable_captions : bool = False,
                           thumbnail_png_bytes : io.BytesIO = None, thumbnail_path : str = None):
        """Schedule a broadcast

        enable_captions: if True, "closedCaptionsHttpPost" will be used and latencyPreference will be set to "low" instead of "ultraLow"
        thumbnail_png_bytes: optional thumbnail image provided as rendered image bytes
        thumbnail_path: optional thumbnail image, path to file
        """
        title = self.make_youtube_title(title)
        description = self.make_youtube_description(description)
        broadcast_info = self.auth.youtube.liveBroadcasts().insert(
            part="id,snippet,contentDetails,status",
            body={
                "contentDetails": {
                    "closedCaptionsType": "closedCaptionsHttpPost" if enable_captions else "closedCaptionsDisabled",
                    "enableContentEncryption": False,
                    "enableDvr": True,
                    # Note: YouTube requires you to have 1k subscribers and 4k public watch hours
                    # to enable embedding live streams. You can set this to true if your account
                    # meets this requirement and you've enabled embedding live streams
                    "enableEmbed": True,
                    "enableAutoStart": False,
                    "enableAutoEnd": False,
                    "recordFromStart": True,
                    "startWithSlate": False,
                    # We must use a low latency only stream if using live captions
                    "latencyPreference": "low" if enable_captions else "ultraLow",
                    "monitorStream": {
                        "enableMonitorStream": False,
                        "broadcastStreamDelayMs": 0
                    }
                },
                "snippet": {
                    "title": title,
                    "scheduledStartTime": start_time.astimezone(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0Z"),
                    "description": description,
                },
                "status": {
                    "privacyStatus": "unlisted"
                }
            }
        ).execute()

        # Due to a bug in the Youtube Broadcast API we have to set the made for
        # kids and embeddable flags through the videos API separately
        update_resp = self.auth.youtube.videos().update(
            part="id,contentDetails,status",
            body={
                "id": broadcast_info["id"],
                "status": {
                    "selfDeclaredMadeForKids": False,
                    "embeddable": True
                }
            }
        ).execute()

        # Render the thumbnail for the session and upload it
        if thumbnail_png_bytes:
            self.auth.youtube.thumbnails().set(
                videoId=broadcast_info["id"],
                media_body=MediaIoBaseUpload(thumbnail_png_bytes, mimetype="image/png")
            ).execute()
        elif thumbnail_path:
            self.auth.youtube.thumbnails().set(
                videoId=broadcast_info["id"],
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()


        return broadcast_info

    def get_broadcasts(self) -> List:
        """get all broadcasts of associated channel (mine)
        """
        all_items = []
        page_token = None
        while True:
            items = self.auth.youtube.liveBroadcasts().list(
                part="id,snippet,contentDetails,status",
                maxResults=50,
                mine=True,
                pageToken=page_token
            ).execute()
            all_items += items["items"]
            if "nextPageToken" not in items:
                break
            page_token = items["nextPageToken"]
        return all_items

    def get_videos(self) -> List:
        """get all videos of associated channel (mine)
        """
        all_items = []
        page_token = None
        while True:
            items = self.auth.youtube.search().list(
                part="id,snippet",
                maxResults=50,
                forMine=True,
                type = "video",
                pageToken=page_token
            ).execute()
            all_items += items["items"]
            if "nextPageToken" not in items:
                break
            page_token = items["nextPageToken"]
        return all_items

    def get_channel(self) -> List:
        """get all broadcasts of associated channel (mine)
        """
        all_items = []
        page_token = None
        while True:
            items = self.auth.youtube.channels().list(
                part="id,snippet,contentDetails,status",
                maxResults=50,
                mine=True,
                pageToken=page_token
            ).execute()
            all_items += items["items"]
            if "nextPageToken" not in items:
                break
            page_token = items["nextPageToken"]
        return all_items

    def get_video(self, video_id : str):
        """get details of a specific video by id
        """
        resp = self.auth.youtube.videos().list(
                part="id,snippet,contentDetails,fileDetails,liveStreamingDetails,player,processingDetails,recordingDetails,statistics,status,suggestions,topicDetails",
                id = video_id
            ).execute()
        if resp['items'] is None or len(resp['items']) != 1:
            return None
        return resp['items'][0]

    def get_all_playlists(self) -> List:
        """get all playlists of current user
        returns array of the like [
                {
                  "kind": "youtube#playlist",
                  "etag": "own...",
                  "id": "PLjHCT....",
                  "snippet": {
                      "publishedAt": datetime,
                      "channelId": string,
                      "title": string,
                      "description": string,
                      "thumbnails": {
                        (key): {
                          "url": string,
                          "width": unsigned integer,
                          "height": unsigned integer
                        }
                      },
                      "channelTitle": string,
                      "defaultLanguage": string,
                      "localized": {
                        "title": string,
                        "description": string
                      }
                  },
                  "contentDetails": {
                    "itemCount": unsigned integer
                  },
                },
              ]
        """
        all_playlists = []
        page_token = None
        """{
              "kind": "youtube#playlistListResponse",
              "etag": "m5paS...",
              "nextPageToken": "CAU...",
              "pageInfo": {
                "totalResults": 127,
                "resultsPerPage": 5
              },
              "items": [
                ...
              ]
            }
        """
        while True:
            playlists = self.auth.youtube.playlists().list(
                part="snippet,contentDetails",
                maxResults=50,
                mine=True,
                pageToken=page_token
            ).execute()
            all_playlists += playlists["items"]
            if "nextPageToken" not in playlists:
                break
            page_token = playlists["nextPageToken"]
        return all_playlists

    def get_playlist_items(self, playlist_id : str) -> List:
        """get all items of a playlists
        returns array of the like [
                {
                  "kind": "youtube#playlistItem",
                  "etag": etag,
                  "id": string,
                  "snippet": {
                    "publishedAt": datetime,
                    "channelId": string,
                    "title": string,
                    "description": string,
                    "thumbnails": {
                      (key): {
                        "url": string,
                        "width": unsigned integer,
                        "height": unsigned integer
                      }
                    },
                    "channelTitle": string,
                    "videoOwnerChannelTitle": string,
                    "videoOwnerChannelId": string,
                    "playlistId": string,
                    "position": unsigned integer,
                    "resourceId": {
                      "kind": string,
                      "videoId": string,
                    }
                  },
                  "contentDetails": {
                    "videoId": string,
                    "startAt": string,
                    "endAt": string,
                    "note": string,
                    "videoPublishedAt": datetime
                  },
                  "status": {
                    "privacyStatus": string
                  }
                },
        ]
        """
        all_items = []
        page_token = None
        while True:
            items = self.auth.youtube.playlistItems().list(
                part="id,snippet,contentDetails,status",
                maxResults=50,
                playlistId=playlist_id,
                pageToken=page_token
            ).execute()
            all_items += items["items"]
            if "nextPageToken" not in items:
                break
            page_token = items["nextPageToken"]
        return all_items

    def get_playlists_and_videos_compact(self) -> dict:
        """retrieves all playlists and their corresponding items (id only)
        returns dict (with playlist title as key):
        {
            "title": {
                "id" : "",
                "videos": [ "videoId", ]
            },
        }
        """
        yt_playlists = self.get_all_playlists()
        res = {}
        for pl in yt_playlists:
            title = pl["snippet"]["title"]
            res[title] = {
                "id": pl["id"],
                "videos": []
            }
            items = self.get_playlist_items(pl["id"])
            videos = res[title]["videos"]
            for i in items:
                videos.append(i["snippet"]["resourceId"]["videoId"])
        return res

    def get_playlists_and_videos(self) -> List:
        """retrieves all playlists and their corresponding items
        returns list of the like:
        [
            {
                "playlist" : { /* see get_all_playlists */ },
                "items" : [{ /* see get_playlist_items */},]
            }, ...
        ]
        """
        yt_playlists = self.get_all_playlists()
        res = []
        for pl in yt_playlists:
            items = self.get_playlist_items(pl["id"])
            res_item = {
                    "playlist": pl,
                    "items": items
                }
            res.append(res_item)
        return res

    def get_stream_status(self, stream_key_id : str):
        """get streamStatus ("active", "created", "error", "inactive", "ready"), healthStatus ("good", "ok", "bad", "noData") of specified stream
        """
        response = self.auth.youtube.liveStreams().list(
            id=stream_key_id,
            part="status"
        ).execute()
        return response["items"][0]["status"]["streamStatus"], response["items"][0]["status"]["healthStatus"]["status"]

    def get_broadcast_status(self, broadcast_id : str):
        """return broadcast lifeCycleStatus of specified broadcast, e.g. "ready", "live" or "complete" or "testing"
        """
        response = self.auth.youtube.liveBroadcasts().list(
            id=broadcast_id,
            part="status"
        ).execute()
        return response["items"][0]["status"]["lifeCycleStatus"]
        
    def set_broadcast_status(self, broadcast_id : str, status : str):
        """set status of specified broadcast, e.g. to "live" or "complete" or "testing"
        """
        resp = self.auth.youtube.liveBroadcasts().transition(
            broadcastStatus=status,
            id=broadcast_id,
            part="status"
        ).execute()
        return resp

    def get_broadcast_statistics(self, broadcast_id : str):
        """return liveStreamingDetails of specified broadcast
        """
        response = self.auth.youtube.videos().list(
            id=broadcast_id,
            part="liveStreamingDetails"
        ).execute()
        return response["items"][0]["liveStreamingDetails"]

    def bind_stream_to_broadcast(self, stream_key_id : str, broadcast_id : str):
        """attach specified stream to specified broadcast or remove it by setting stream_key_id to None
        """
        resp = self.auth.youtube.liveBroadcasts().bind(
            id=broadcast_id,
            part="status",
            streamId=stream_key_id,
        ).execute()
        return resp
