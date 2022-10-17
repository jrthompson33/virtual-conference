import argparse


from eventbrite_helper import get_attendees
from auth0_helper import create_user, retrieve_users_via_export
from core.auth import Authentication

# Get eventbrite list


def get_eventbrite_attendees(auth: Authentication) -> list:
    eventbrite_attendees = get_attendees(auth)
    return eventbrite_attendees


def get_auth0_users(auth: Authentication) -> list:
    auth0_users = retrieve_users_via_export(auth, auth.get_auth0_token())
    return auth0_users


def sync_attendees(auth: Authentication):
    eventbrite_attendees = get_eventbrite_attendees(auth)
    auth0_users = get_auth0_users(auth)
    for ea in eventbrite_attendees:
        if ea['profile'] and ea['profile']['name'] and ea['profile']['email'] and not ea['cancelled']:
            # Check if ea is in auth0_users
            au = next(
                filter(lambda a: a['email'] == ea['profile']['email'], auth0_users), None)
            if au == None:
                create_user(auth, auth.get_auth0_token(),
                            ea['profile']['email'], ea['profile']['name'], {'invite_email_sent': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Sync attendees from EventBrite and CVENT with Auth0')

    auth = Authentication(auth0_api=True)
    sync_attendees(auth)

# Things to do in this script

# Get cvent list

# Get list of currently on auth0

# Loop through eventbrite list and see if already in auth0 list
# If not create user with password, set user data email_sent false

# Loop through cvent list and see if already in auth0
# If not create user with password, set user data email_sent false

# Wait some time, get the updated list from auth0 - this seems like a race condition?
# Send emails for all the auth0 users that have `invite_email_sent` == False
