from core.auth import Authentication
import requests
from lxml import html
import time
import json


def get_attendees_json(auth : Authentication):
    return_url = "ReturnUrl=%2fSubscribers%2fEvents2%2fInvitee%2fInviteeSearch%3ffromNav%3d1%26evtstub%3d" + auth.cvent['evtstub']
    login_url = "https://app.cvent.com/subscribers/Login.aspx?" + return_url
    s = requests.Session()
    r = s.get(login_url)
    tree = html.fromstring(r.content)
    viewstate = tree.xpath('//input[@id="__VIEWSTATE"]/@value')[0]
    viewstate_gen = tree.xpath('//input[@id="__VIEWSTATEGENERATOR"]/@value')[0]
    viewstate_enc = tree.xpath('//input[@id="__VIEWSTATEENCRYPTED"]/@value')[0]
    event_val = tree.xpath('//input[@id="__EVENTVALIDATION"]/@value')[0]
    
    time.sleep(1)

    login_data = { "account": auth.cvent['account'],
                 "username": auth.cvent['username'],
                 "password": auth.cvent['password'],
                 "btnLogin": "Log In",
                 "organizationId": "",
                 "__VIEWSTATE": viewstate,
                 "__VIEWSTATEGENERATOR": viewstate_gen,
                 "__VIEWSTATEENCRYPTED": viewstate_enc,
                 "__EVENTVALIDATION": event_val

                  }
    #headers = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.0'}
    
    print("\r\nLogging in...\r\n")
    r = s.post(login_url, data = login_data)
    
    print(r.status_code)
    print(r.content)
    tree = html.fromstring(r.content)

    if "This username is currently logged in" in r.text:
        #we do have to confirm that we want to end other sessions
        viewstate = tree.xpath('//input[@id="__VIEWSTATE"]/@value')[0]
        viewstate_gen = tree.xpath('//input[@id="__VIEWSTATEGENERATOR"]/@value')[0]
        viewstate_enc = tree.xpath('//input[@id="__VIEWSTATEENCRYPTED"]/@value')[0]
        event_val = tree.xpath('//input[@id="__EVENTVALIDATION"]/@value')[0]
        data = {"btnLogin": "Continue",
                "organizationId": "",
                "__VIEWSTATE": viewstate,
                "__VIEWSTATEGENERATOR": viewstate_gen,
                "__VIEWSTATEENCRYPTED": viewstate_enc,
                "__EVENTVALIDATION": event_val
                }
        time.sleep(1)
        
        print("\r\n sending login confirmation...\r\n")
        r = s.post("https://app.cvent.com/Subscribers/LoginConfirmation.aspx?" + return_url, data = data)

        print(r.status_code)
        print(r.content)
        tree = html.fromstring(r.content)

    csrf = tree.xpath('//input[@name="CSRF"]/@value')[0]
    search_id = tree.xpath('//input[@id="InputModel_SearchModel_SearchId"]/@value')[0]
    invitee_search_id = tree.xpath('//input[@id="InputModel_SearchModel_InviteeSearchServiceSearchId"]/@value')[0]
    print("\r\nlogged in.\r\n")

    
    time.sleep(1)
    
    url = "https://app.cvent.com/subscribers/events2/Invitee/InviteeSearch/GetData?evtstub=" + auth.cvent['evtstub'] + "&rsv=2"
    data  ={
          "command": {
            "PageIndex": 1,
            "RecPerPage": 1000,
            "Keyword": "",
            "SortDirection": "Ascending",
            "SortColumn": "FullName",
            "StartIndex": 1
          },
          "searchModel": {
            "Name": {
              "Required": False,
              "FirstNameRequired": False,
              "ShowPrefix": False,
              "ShowMiddleName": False,
              "Mode": "Edit",
              "Prefix": None,
              "FirstName": None,
              "MiddleName": None,
              "LastName": None,
              "LabelResource": "_Global_Name__resx",
              "HelpId": None,
              "PrefixMaxLengthOverride": 30,
              "FirstNameMaxLengthOverride": 30,
              "MiddleNameMaxLengthOverride": 30,
              "LastNameMaxLengthOverride": 50
            },
            "Company": None,
            "Email": None,
            "SourceId": None,
            "TransactionId": None,
            "IsParticipant": None,
            "IsAttendeeTestMode": None,
            "RegistrationStartDate": None,
            "RegistrationEndDate": None,
            "ConfirmationNumber": None,
            "ProductRegistrationStatus": 1,
            "SourcePage": None,
            "SourcePageArea": None,
            "BackButtonText": None,
            "RegisteredProducts": [],
            "SessionsWaitlisted": [],
            "SessionsAttended": [],
            "DiscountId": None,
            "DiscountName": None,
            "InviteeStatuses": [],
            "InviteeStatus": None,
            "SelectedRegistrationTypes": [],
            "AdvancedFilters": {
              "FilterRows": [],
              "SearchMethod": "And"
            },
            "AttendeeTypeId": None,
            "AttendingFormatId": None,
            "SearchId": search_id,
            "InviteeSearchServiceSearchId": invitee_search_id,
            "UsedInviteeSearchServiceResults": True,
            "InvalidateSavedResults": False
          },
          "pagedCheckboxes": {
            "SelectAll": False,
            "Identifiers": []
          },
          "CSRF": csrf
        }
    print("\r\ntrying to retrieve attendees...\r\n")
    headers = {'Content-Type': 'application/json; charset=utf-8', 
               'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.0',
               'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest'
               }
    r = s.post(url, json=data, headers = headers)
    
    print(r.status_code)
    jsonstr = r.content.decode('utf-8')
    #res = json.loads(jsonstr)
    return jsonstr


if __name__ == '__main__':
    auth = Authentication()
    print(get_attendees_json(auth))