from core.auth import Authentication
from core.templates import load_templates_dict
from core.aws_email import send_aws_email_paper
from auth0_helper import generate_password, user_update_merge_metadata, retrieve_users_via_export
import argparse
import time

def send_info_to_user(auth: Authentication, auth0_token : str, user : dict, template : dict):
    """
    """
    email = user["email"]
    user["password"] = generate_password(email, auth.auth0["password_secret"])
    user["discord_invite_url"] = auth.discord["discord_invite_url"]
    print(f"sending email to {email}")
    response = send_aws_email_paper(auth, user, template)
    print(f"    {response}")
    print(f"updating metadata...")
    auth0_res = user_update_merge_metadata(auth, auth0_token, user["user_id"], { "invite_email_sent":True})
    
def check_and_send_infos_to_users(auth: Authentication, auth0_token : str, template : dict):
    """
    """
    users = retrieve_users_via_export(auth, auth0_token)
    print(f"{len(users)} users retrieved")
    users = list(filter(lambda u: "user_metadata" not in u or "invite_email_sent" not in u["user_metadata"] or not u["user_metadata"]["invite_email_sent"], users))
    print(f"{len(users)} users that are missing login info")

    i = 0
    for user in users:
        i += 1
        print(f"\r\nprocessing {i}/{len(users)}")
        send_info_to_user(auth, auth0_token, user, template)
        time.sleep(2)

def test_send_info_to_user(auth: Authentication, auth0_token : str, template : dict, email : str):
    """
    """
    users = retrieve_users_via_export(auth, auth0_token)
    print(f"{len(users)} users retrieved")
    user : dict = None
    for u in users:
        if u["email"] == email:
            user = u
            break
    if not user:
        print(f"user with email {email} not found.")
        return
    print(user)
    
    send_info_to_user(auth, auth0_token, user, template)

def monitor_users(auth: Authentication, auth0_token : str, template : dict):
    """
    """
    print("monitoring started...")
    while True:
        try:
            check_and_send_infos_to_users(auth, auth0_token, template)
        except Exception as e:
            print(f"\r\nERROR OCCURRED: {e}\r\n")
        time.sleep(20*60)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to monitor new auth0 users and send out appropriate attendee info.')

    parser.add_argument('--test', help='send email to one particular attendee',
                        action='store_true', default=False)
    parser.add_argument('--monitoring', help='monitor auth0 users and send info',
                        action='store_true', default=False)

    
    parser.add_argument(
        '--token', help='auth0 access token', default=None)
    parser.add_argument(
        '--email', help='send info of auth0 user with that email if in testing mode', default=None)
    parser.add_argument(
        '--email_template', help='template to use for the email (e.g., \"attendee_info\")', default="attendee_info")

    args = parser.parse_args()
    auth = Authentication(email=True, auth0_api=True)
    token = args.token if args.token else auth.get_auth0_token()
    templates = load_templates_dict()
    template_key = args.email_template
    if not template_key or template_key not in templates:
        print(f"could not found template {template_key}")
        exit(-1)
    template : dict = templates[template_key]

    if args.test:
        test_send_info_to_user(auth, token, template, args.email)
    elif args.monitoring:
        monitor_users(auth, token, template)
