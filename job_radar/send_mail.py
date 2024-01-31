import logging

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.tokens import google_email_config
from log_helpers import log_big_separator
from manage_jobposts import GoogleSheetManager

logger = logging.getLogger(__name__)


def send_mail_with_notification(cool_jobs):
    log_big_separator(logger, "EMAILING COOL JOB")

    # retreive list of jobs already notified about
    # update job to list of jobs already notified
    google_sheet_manager = GoogleSheetManager("Mails_send")
    ws_mails = google_sheet_manager.sheet.worksheets()[0]
    df = google_sheet_manager.get_worksheet_as_dataframe(ws_mails)
    already_send_mails = df["ID"].tolist()

    # Sender's email credentials
    sender_email = google_email_config["email"]
    sender_password = google_email_config["password"]

    # Receiver's email
    receiver_email = sender_email

    # Create a message object
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email

    subject = ""
    body = ""
    if cool_jobs and not any(job[0] in already_send_mails for job in cool_jobs):
        subject += f"Cool jobs found: {str(len(cool_jobs))}"
        body += f"Cool jobs found: \n -------------------"
        for job in cool_jobs:
            if job[0] not in already_send_mails:
                body += f"\n{job}\n"
                already_send_mails.append(job[0])
        body += f"-------------------"

        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Connect to the SMTP server and send the email
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, receiver_email, text)
            server.quit()
            logger.info("Email sent successfully")

            # add sent jobs to mails send list
            df["ID"] = already_send_mails

            google_sheet_manager.update_google_worksheet(ws_mails, df)
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")

    else:
        logger.info("No mail send - no new cool jobs")
