"""script that provides functions for sending mails with Amazon's Simple Email Service
"""

from functools import cached_property
import boto3
from typing import List, Tuple
from core.auth import Authentication
from email import encoders
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart


def send_aws_email(session : Authentication, sender: str, recipients: List[str], subject : str, body_text : str, body_html : str = None,
                  charset : str = "UTF-8"):
    """send mail using text body and/or html body. .
    session: Authentication instance in which aws ses client was authenticated
    sender: 'Sender Name <sender@mail.com>'
    recipients: ['to@mail.com']
    subject: 'subject line'
    body_text: alternative text if body_html is specified, otherwise main text body
    body_html: optional html body of mail, e.g.
        '<html>
        <head></head>
        <body>
          <h1>Amazon SES Test (SDK for Python)</h1>
          <p>This email was sent with
            <a href='https://aws.amazon.com/ses/'>Amazon SES</a> using the
            <a href='https://aws.amazon.com/sdk-for-python/'>
              AWS SDK for Python (Boto)</a>.</p>
        </body>
        </html>'
    """
    client = session.email
    response = client.send_email(
        Destination={
            'ToAddresses': recipients
        },
        Message={
            'Body': {
                'Html': {
                    'Charset': charset,
                    'Data': body_html,
                },
                'Text': {
                    'Charset': charset,
                    'Data': body_text,
                },
            } if body_html else None,
            'Subject': {
                'Charset': charset,
                'Data': subject,
            },
        },
        Source=sender
        # If you are not using a configuration set, comment or delete the
        # following line
        #ConfigurationSetName=CONFIGURATION_SET,
    )
    return response

def _get_recipients_from_template(paper : dict, template : dict) -> Tuple[list,list]:
    """extract recipient(s) from a single database item and the corresponding template:

    recipients, cc_recipients = _get_recipients_from_template(paper, template)
    """
    attribute = template["recipient_attribute"]
    if attribute and len(attribute) > 0:
        r_str = paper[attribute]
        if type(r_str) != str or len(r_str) == 0:
            return [], [] #empty field
        recipients = r_str.split("|")
    else:
        r_str = template["recipient"]
        if type(r_str) != str or len(r_str) == 0:
            return [], [] #empty field
        recipients = [ r_str.format(**paper) ]   
    return recipients, []


def send_aws_email_paper(session : Authentication, paper : dict, template : dict):
    """send mails to specified recipients of a paper using text body and/or html body.
    Recipients, sender, and mail content will be determined based on specified template dictionary.
    This template dict can use placeholders based on the paper's attributes.

    session: Authentication instance in which aws ses client was authenticated
    paper : db item of PapersDatabase (dict)
    template : template dict to use for generating mails, e.g.:
      {
        "sender": "IEEE VIS <no-reply@ieeevis.org>",
        "recipient": "",
        "recipient_attribute": "Contributor Email(s)",
        "subject": "Some Test Mail for Paper {UID}",
        "body_text": "We regret to inform you that your request for paper {Title} has not been granted",
        "body_html": "<html><head></head><body><h1>Hello</h1><p>We regret to inform you that your request for paper {Title} has not been granted</p></body></html>"
      } 
    """
    recipients, cc_recipients = _get_recipients_from_template(paper, template)
    if len(recipients) == 0 and len(cc_recipients) == 0:
        print(f"skipping paper '{paper['UID']}' with zero recipients")
        return
    sender = template["sender"].format(**paper)
    subject = template["subject"].format(**paper)
    body_text = template["body_text"].format(**paper)
    body_html = template["body_html"].format(**paper)
    return send_aws_email(session, sender, recipients, subject, body_text, body_html)

def send_aws_mime_email(session : Authentication, sender: str, recipients: List[str],
                       subject : str, body : str, alternative_text : str = None, cc_recipients : List[str] =None,
                      attachments : List[any] =None):
    """send MIME-encoded mail using html body, optional alternative text, and optional attachments e.g. calendar entry

    session: Authentication instance in which aws ses client was authenticated
    sender: 'Sender Name <sender@mail.com>'
    recipients: ['to@mail.com']
    subject: 'subject line'    
    body_html: html body of mail, e.g.
        '<html>
        <head></head>
        <body>
          <h1>Amazon SES Test (SDK for Python)</h1>
          <p>This email was sent with
            <a href='https://aws.amazon.com/ses/'>Amazon SES</a> using the
            <a href='https://aws.amazon.com/sdk-for-python/'>
              AWS SDK for Python (Boto)</a>.</p>
        </body>
        </html>'
    alternative_text: alternative raw text content
    cc_recipients: ['cc-to@mail.com']
    """
    message = MIMEMultipart("mixed")
    message.set_charset("utf8")

    if type(recipients) == str:
        recipients = [recipients]
        

    all_recipients = [r.strip() for r in recipients]
    message["to"] = ", ".join(recipients)
    message["from"] = sender

    if cc_recipients:
        if type(cc_recipients) == str:
            cc_recipients = [cc_recipients]
        message["cc"] = ", ".join(cc_recipients)
        all_recipients += [r.strip() for r in cc_recipients]

    message["subject"] = subject
    message_text = MIMEMultipart("alternative")
    if alternative_text:
        message_text.attach(MIMEText(alternative_text, "plain", "utf8"))
    message_text.attach(MIMEText(body, "html", "utf8"))
    message.attach(message_text)

    if attachments:
        for a in attachments:
            encoders.encode_base64(a)
            message.attach(a)

    response = session.email.send_raw_email(
        Source=message["from"],
        Destinations=all_recipients,
        RawMessage={
            "Data": message.as_bytes()
        })
    return response