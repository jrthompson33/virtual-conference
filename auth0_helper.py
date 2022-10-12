import argparse
import sys
from telnetlib import DO
import time
import os
import json
import os.path as path
from typing import List
import string
import secrets
import time
import http.client
import requests
import hashlib
from gzip import decompress

from urllib.parse import urlsplit
from datetime import datetime
from email.mime.image import MIMEImage

from core.auth import Authentication
#import core.schedule as schedule

alphabet = string.ascii_letters + string.digits


def format_to_auth0(email, name, password_hash):
    return {
        "email": email,
        "email_verified": True,
        "name": name,
        "password_hash": password_hash.decode('utf-8'),
    }


def send_to_auth0(session, filename, access_token, connection_id):
    payload = {
        "connection_id": connection_id,
        "external_id": "import_user",
        "send_completion_email": False
    }

    files = {
        "users": open(filename, "rb")
    }

    headers = {
        'authorization': f"Bearer {access_token}"
    }

    domain = "https://" + \
        urlsplit(session.auth0["audience"]).netloc + \
        "/api/v2/jobs/users-imports"
    print(domain)
    response = requests.post(domain, data=payload, files=files,
                             headers=headers)
    print(response.content)

def retrieve_users_via_export(auth: Authentication, access_token: str) -> List[dict]:
    """Retrieve up to 10,000 auth0 users using the export job functionality
    """
    users = []
    connection = auth.auth0["connection_id"]
    headers = {
        'Authorization': f"Bearer {access_token}"
    }
    export_req_body = """{
                  "connection_id": "{conn}",
                  "format": "json",
                  "limit": 10000,
                  "fields": [
                    {
                      "name": "user_id"
                    },
                    {
                      "name": "name"
                    },
                    {
                      "name": "email"
                    },
                    {
                      "name": "identities[0].connection",
                      "export_as": "provider"
                    },
                    {
                      "name": "user_metadata"
                    }
                  ]
                }
                """.replace("{conn}", connection)
    url = "https://" + auth.auth0["domain"] + f"/api/v2/jobs/users-exports"
    print(url)
    exp_response = requests.post(url, data=export_req_body, headers={
        **headers, 
        "Content-Type": "application/json"}).json()
    job_id = exp_response["id"]
    while True:
        time.sleep(2)
        url = "https://" + auth.auth0["domain"] + f"/api/v2/jobs/{job_id}"
        print(url)
        job_res = requests.get(url, headers=headers).json()
        status = job_res["status"] if "status" in job_res else "<missing>"
        if status == "pending":
            continue
        if status != "completed":
            raise Exception(f"unexpected status of job: {job_res.status}")
        url = job_res["location"]
        print(url)
        if not url.startswith("http"):
            raise Exception(f"unexpected location: {url}")
        res_response = requests.get(url).content
        json_lines = decompress(res_response).decode("utf-8").splitlines()
        res = []
        for l in json_lines:
            if len(l.strip()) == 0:
                continue
            res.append(json.loads(l))
        return res
            


def retrieve_users(auth: Authentication, access_token: str) -> List:
    users = []
    db = auth.auth0["connection"]
    cur_page = 0

    headers = {
        'Authorization': f"Bearer {access_token}"
    }

    while True:
        url = "https://" + \
            auth.auth0["domain"] + \
            f"/api/v2/users?page={cur_page}&per_page=100&q=identities.connection%3A%22{db}%22&search_engine=v3"
        print(url)
        response = requests.get(url, headers=headers).json()
        if not response or len(response) == 0:
            break
        users.extend(response)
        cur_page += 1
    return users

def user_update_merge_metadata(auth: Authentication, access_token: str, user_id : str, metadata : dict) -> requests.Response:
    """update the user metadata of the specified user, but be aware that auth0 performs a first-level merge, i.e. existing fields not part of new metadata still remain
    """
    payload = {
        "user_metadata": metadata if metadata else {}
    }

    headers = {
        'Authorization': f"Bearer {access_token}"
    }

    url = "https://" + auth.auth0["domain"] + "/api/v2/users/" + user_id
    print(url)
    response = requests.patch(url, json=payload, headers=headers)
    print(response.content)
    return response

def send_create_user(auth: Authentication, access_token: str, name: str, email: str, password: str, metadata: dict) -> requests.Response:
    """create user in specified database
    """
    payload = {
        "email": email,
        "name": name,
        "verify_email": False,
        "password": password,
        "user_metadata": metadata if metadata else {},
        "connection": auth.auth0["connection"]
    }

    headers = {
        'Authorization': f"Bearer {access_token}"
    }

    url = "https://" + auth.auth0["domain"] + "/api/v2/users"
    print(url)
    response = requests.post(url, json=payload, headers=headers)
    print(response.content)
    return response


def create_user(auth: Authentication, access_token: str, email: str, name: str, metadata: dict):
    """function to create a user on the specified auth0 database
    """
    password = generate_password(email, auth.auth0["password_secret"])
    print(f"Email: {email}")
    print(f"Password: {password}")

    send_create_user(auth, access_token, name, email, password, metadata)

def get_any_password_requests():
    password_requests = []
    for f in os.listdir("./"):
        if f.startswith("password_request"):
            with open(f, "r") as fhandle:
                for l in fhandle.readlines():
                    line = l.strip()
                    if len(line) > 0:
                        password_requests.append(line)
    print(f"Got password requests {password_requests}")
    return password_requests


def get_new_eventbrite(session):
    eventbrite_event_id = session.eventbrite_event_id

    # Get the resource URI for the attendee page since we have to do the paginated
    # requests ourselves
    attendees = session.eventbrite.get_event_attendees(eventbrite_event_id)
    last_page = attendees["pagination"]["page_count"]

    # Note: Eventbrite's python SDK is half written essentially, and
    # doesn't directly support paging properly. So to load the other
    # pages we need to use the raw get call ourselves instead of
    # being able to continue calling get_event_attendees
    # It looks like we can also directly request a page by passing page: <number>

    eventbrite_registrations = []
    # Page indices start at 1 inclusive
    for i in range(1, last_page + 1):
        print(f"Fetching eventbrite registrations page {i} of {last_page}")
        args = {
            'page': i
        }
        attendees = session.eventbrite.get(attendees.resource_uri, args)
        if not "attendees" in attendees:
            print("Error fetching eventbrite response?")
            print(attendees)
            break
        for a in attendees["attendees"]:
            eventbrite_registrations.append((
                a["profile"]["name"],
                a["profile"]["email"]
            ))

    return eventbrite_registrations


def generate_password(email: str, secret: str) -> str:
    """generates password from email using hash with secret
    """
    return hashlib.sha256((email + secret).encode('utf-8')).hexdigest()[:10]


def get_all(transmit_to_auth0, session, logo_attachment, max_new=-1):
    results = get_new_eventbrite(session)
    password_requests = get_any_password_requests()
    all_registered = load_already_registered()

    all_new = []
    for email, x in all_registered.items():
        if "emailed" not in x:
            x["emailed"] = False
        if not x["emailed"]:
            results.append([x["name"], x["email"]])

    now = str(datetime.utcnow())
    for x in results:
        name, email = x
        if max_new > 0 and len(all_new) >= max_new:
            break
        if len(email) == 0:
            continue
        # We use this same process to re-send someone their login info, so they could be
        # already registered
        if email not in all_registered or not all_registered[email]["emailed"]:
            print(f"adding {email}")
            # random password
            password = ""
            if email not in all_registered:
                password = ''.join(secrets.choice(alphabet)
                                   for i in range(10)).encode("utf-8")
            else:
                password = all_registered[email]["password"].encode("utf-8")

            salt = bcrypt.gensalt(rounds=10)
            password_hash = bcrypt.hashpw(password, salt)

            all_new.append(format_to_auth0(
                email, name, password, password_hash))
            all_registered[email] = {"name": name,
                                     "email": email,
                                     "password": password.decode('utf-8'),
                                     "date": now,
                                     "emailed": False}
        elif email in password_requests:
            print(f"Password request for {email}")
        else:
            continue
        password = all_registered[email]["password"]

        if session.email:
            time.sleep(0.1)

        try:
            if session.email:
                send_register_email(
                    email, session, logo_attachment, name, password)
                all_registered[email]["emailed"] = True
        except Exception as e:
            print("Error sending email {}".format(e))

    print(f"Got {len(all_new)} new registrations")

    registration_stats = {}
    registration_stats_file = "registration_stats.json"
    if os.path.isfile(registration_stats_file):
        with open("registration_stats.json", "r") as f:
            registration_stats = json.load(f)
        registration_stats["new_since_last"] += len(all_new)
    else:
        registration_stats["new_since_last"] = len(all_new)

    print(registration_stats)

    with open(registration_stats_file, "w") as f:
        json.dump(registration_stats, f)

    if len(all_new) > 0:
        file_name = f"new_imports_{time.time_ns() / 1000}.json"
        with open(file_name, "w") as f:
            json.dump(all_new, f)
        if transmit_to_auth0:
            print("Sending to Auth0")
            token = session.get_auth0_token()
            send_to_auth0(session, file_name, token,
                          session.auth0["connection_id"])
            with open("registered.json", "w") as f:
                json.dump(all_registered, f, indent=4)
    print(f"New registrations processed at {datetime.now()}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sync Eventbrite with auth0.')
    parser.add_argument('--create_user', action="store_true",
                        help='create user for testing purposes')
    parser.add_argument('--get_users', action="store_true",
                        help='retrieve all users and store them as a json file')
    # parser.add_argument('--mail', action="store_true", help='send email for new users')
    # parser.add_argument('--auth0', action="store_true", help='send new users to auh0')
    # parser.add_argument('--limit', default=-1, type=int, help='maximum number of new users for this run')
    parser.add_argument("--name", default=None, type=str,
                        help='Name of user to create')
    parser.add_argument("--email", default=None,
                        type=str, help='Email of user')
    parser.add_argument("--token", default=None, type=str, help='access token')
    parser.add_argument("--output", default=None, type=str,
                        help='name of output file')

    args = parser.parse_args()

    if args.create_user:
        auth = Authentication(auth0_api=True)
        token = args.token if args.token else auth.get_auth0_token()
        create_user(auth, token, args.email, args.name, {})
    elif args.get_users:
        if not args.output or len(args.output) == 0:
            print("output file name has to be specified.")
            exit(-1)
        auth = Authentication(auth0_api=True)
        token = args.token if args.token else auth.get_auth0_token()
        users = retrieve_users_via_export(auth, token)
        print(f"{len(users)} users retrieved.")
        users_json = json.dumps(users, indent=4)

        with open(args.output, "w", newline='', encoding='utf-8') as f:
            f.write(users_json)

    # else:
    #     session = auth.Authentication(email=args.mail, eventbrite_api=True, auth0_api=True)

    #     logo_attachment = None
    #     if args.logo:
    #         logo_attachment = load_logo_attachment(args.logo)

    #     while True:
    #         print("Checking for new registrations")
    #         get_all(args.auth0, session, logo_attachment, args.limit)
    #         time.sleep(15 * 60)
