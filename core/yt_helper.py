import sys
import os
import http.client
import httplib2
import time
from apiclient.http import MediaFileUpload
from apiclient.errors import HttpError
import argparse
from typing import List

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

    def upload_video(self, path : str, title : str, description : str):
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

    def update_video(self, video_id : str, title : str, description : str):
        print("Updating\ntitle = {}\nvideo = {}".format(title, video_id))
        upload_response = self.auth.youtube.videos().update(
            part="id,snippet,status",
            body = {
                "id": video_id,
                "snippet": {
                    "title": title,
                    "description": description,
                    "categoryId": 27 # Category 27 is "education"
                }
            }
        ).execute()
        return upload_response

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

