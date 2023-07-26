from core.auth import Authentication

import requests
from lxml import html
import time
import pandas as pd

def get_attendees_json(auth: Authentication):
    login_url = "https://members.asnevents.com.au/login"
    export_url = "https://members.asnevents.com.au/event/1856/committee/report?Organisation=&EventAddon=&Export=Export"
    s = requests.Session()
    r = s.get(login_url)
    tree = html.fromstring(r.content)
    csrf_token = tree.xpath('//input[@name="csrf_token"]/@value')[0]

    time.sleep(1)

    login_data = {"Email": auth.asn["username"],
                "Password": auth.asn["password"],
                "Login": "Login",
                "csrf_token": csrf_token,
                }

    print("\r\nLogging in...\r\n")
    r = s.post("https://members.asnevents.com.au/login/do", data=login_data)

    if (r.status_code != 200):
        print("Error: " + str(r.status_code))
        return None

    tree = html.fromstring(r.content)

    # http get the export url - this should return an bit excel file
    # TODO: might need to add Headers to this request
    r = s.get(export_url)
    
    if (r.status_code != 200):
        print("Error: " + str(r.status_code))
        return None

    # Only use the columns we need, there are a lot more in the excel file
    columns_to_use = [
        "ID", "Email", "Title", "Name", "First Name", "Last Name",
        "Name Tag", "Gender", "Position", "Department", "Organisation",
        "Date Added", "Date Modified", "Checked", "Completed At",
        "App Login Token Create Date", "Student", "Trade", "Bio",
        "Head Shot File", "Dietary Requirements", "Special Requirements",
        "App Login Token", "App Login Short URL"
    ]

    # Read in the excel file using pandas
    df = pd.read_excel(r.content, sheet_name="Worksheet", header=0, usecols=columns_to_use)

    # Return as json
    return df.to_json(orient="records")