import json
import os
import sys
import boto3
import pickle
import requests
#import eventbrite
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

from urllib.parse import urlsplit
from google.auth.transport.requests import Request

# The SUPERMINISTREAM_AUTH_FILE file should be a JSON file with the authentication
# information for the APIs to be used. For Zoom, the JWT token should be for the
# admin account, so that it can schedule meetings for the technician accounts.
# For example:
# {
#    "aws": {
#        "access_key": "",
#        "secret_key": "",
#        "region": ""
#    },
#    "discord": {...},
#    "dropbox" : {
#       "access_token" : ""
#    },
#    "google": {
#        "installed": {...}
#    },
#    "zoom": {
#        "jwt_token": ""
#    },
#    "eventbrite": "",
#    "eventbrite_event_id": <number>,
#    "auth0": {
#        "client_id": "",
#        "client_secret": "",
#        "audience": "",
#        "connection_id": ""
#    },
#    "cvent": {
#       "account": "",
#       "username": "",
#       "password": "",
#       "evtstub": ""
#    },
#    "gsheets": {
#       "db_link": ""
#    },
#   "asn": {
#       "username": "",
#       "password": "",
#    },
#   "pmu": {
#       "items_url": ""
#    }
# }


class Authentication:
    def __init__(self, youtube=False, email=False, use_pickled_credentials=False,
                 eventbrite_api=False,
                 auth0_api=False):
        # Setup API clients
        auth_file = ""
        if "SUPERMINISTREAM_AUTH_FILE" in os.environ:
            auth_file = os.environ["SUPERMINISTREAM_AUTH_FILE"]
        else:
            auth_file = "./SUPERMINISTREAM_AUTH_FILE.json"

        if not os.path.isfile(auth_file):
            print("Could not find the SUPERMINISTREAM_AUTH_FILE.json file containing the authentication credentials. Put the file in the working directory or provide its path by setting the env variable $SUPERMINISTREAM_AUTH_FILE")
            sys.exit(1)

        yt_pickle_file = "YOUTUBE_AUTH_PICKLE_FILE.bin"
        if "YOUTUBE_AUTH_PICKLE_FILE" in os.environ:
            yt_pickle_file = os.environ["YOUTUBE_AUTH_PICKLE_FILE"]

        with open(auth_file, "r") as f:
            auth = json.load(f)
            self.discord = auth["discord"]
            self.dropbox = auth["dropbox"]
            self.cvent = auth["cvent"]
            self.gsheets = auth["gsheets"]
            self.asn = auth["asn"]
            self.zoom = auth["zoom"]
            
            self.email = None
            self.youtube = None

            if email:
                self.email = boto3.client("ses",
                                          aws_access_key_id=auth["aws"]["access_key"],
                                          aws_secret_access_key=auth["aws"]["secret_key"],
                                          region_name=auth["aws"]["region"])

            if youtube:
                self.youtube = self.authenticate_youtube(
                    auth, use_pickled_credentials, yt_pickle_file)

            if eventbrite_api:
                self.eventbrite = eventbrite.Eventbrite(
                    auth["eventbrite"])  # does not work
            self.eventbrite_event_id = auth["eventbrite_event_id"]
            self.eventbrite_token = auth["eventbrite"]
            if "auth0" in auth:
                self.auth0 = auth["auth0"]
            if "pmu" in auth:
                self.pmu = auth["pmu"]

    def authenticate_youtube(self, auth, use_pickled_credentials, yt_pickle_file):
        yt_scopes = ["https://www.googleapis.com/auth/youtube",
                     "https://www.googleapis.com/auth/youtube.readonly",
                     "https://www.googleapis.com/auth/youtube.force-ssl"]

        credentials = None
        if use_pickled_credentials and os.path.exists(yt_pickle_file):
            with open(yt_pickle_file, "rb") as f:
                credentials = pickle.load(f)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                # Get credentials and create an API client
                credentials = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
                    auth["google"], yt_scopes).run_local_server()
            # Save the credentials
            if use_pickled_credentials:
                with open(yt_pickle_file, "wb") as f:
                    pickle.dump(credentials, f)

        return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

    def get_auth0_token(self):
        auth0_payload = {
            "client_id": self.auth0["client_id"],
            "client_secret": self.auth0["client_secret"],
            "audience": self.auth0["audience"],
            "grant_type": "client_credentials"
        }
        # "https://" + urlsplit(self.auth0["audience"]).netloc
        domain = self.auth0["domain"]
        resp = requests.post("https://" + domain +
                             "/oauth/token", json=auth0_payload).json()
        print(resp)
        return resp["access_token"]
