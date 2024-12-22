import os
import os.path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import base64
import email
from email import policy
from email.parser import BytesParser
from datetime import datetime


# Scopes for accessing Gmail
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Directory to save attachments and email content
SAVE_DIR = 'attachments'

# Ensure the save directory exists
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# Keywords for detecting relevant emails
INCLUDE_KEYWORDS = ["invoice", "receipt", "bill", "payment confirmation", "purchase", "order summary"]
EXCLUDE_KEYWORDS = ["promo", "special offer", "advertisement", "newsletter", "learn more"]

def is_relevant_email(subject, snippet):
    """
    Determines if an email is relevant based on the subject and snippet.
    """
    # Check if any of the include keywords are present
    contains_include_keywords = any(
        keyword.lower() in subject.lower() or keyword.lower() in snippet.lower()
        for keyword in INCLUDE_KEYWORDS
    )

    # Check if any of the exclude keywords are present
    contains_exclude_keywords = any(
        keyword.lower() in subject.lower() or keyword.lower() in snippet.lower()
        for keyword in EXCLUDE_KEYWORDS
    )

    # Email is relevant if it contains include keywords and does not contain exclude keywords
    return contains_include_keywords and not contains_exclude_keywords



def get_attachment(service, user_id, message_id, attachment_id):
    try:
        # Make the API call to fetch the attachment
        attachment = service.users().messages().attachments().get(
            userId=user_id, messageId=message_id, id=attachment_id
        ).execute()

        # Decode the base64 attachment data
        attachment_data = base64.urlsafe_b64decode(attachment['data'])
        return attachment_data

    except Exception as e:
        print(f"An error occurred while fetching the attachment: {e}")
        return None


def save_attachment(attachment_data, filename):
    pdf_saved = False
    
    if filename and filename.endswith('.pdf'):
        filepath = os.path.join(SAVE_DIR, f"{filename}")
        with open(filepath, 'wb') as f:
            f.write(attachment_data)
        print(f"Attachment saved: {filepath}")
        pdf_saved = True
    return pdf_saved


# def save_email_as_pdf(subject, sender, body, msg_id):
#     # Escape any special characters in variables
#     subject = html.escape(subject)
#     sender = html.escape(sender)
#     body = html.escape(body).replace('\n', '<br>')

#     html_content = f"""
#     <html>
#     <head>
#         <style>
#             body {{ font-family: Arial, sans-serif; }}
#             h1 {{ font-size: 18px; }}
#             p {{ font-size: 12px; }}
#         </style>
#     </head>
#     <body>
#         <h1>Subject: {subject}</h1>
#         <p>From: {sender}</p>
#         <hr>
#         <p>{body}</p>
#     </body>
#     </html>
#     """
#     pdf_filename = os.path.join(SAVE_DIR, f"{msg_id}_email.pdf")
#     HTML(string=html_content).write_pdf(pdf_filename)
#     print(f"Email content saved as PDF: {pdf_filename}")


def main():
    creds = None
    # Token file to store user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # Connect to Gmail
    service = build('gmail', 'v1', credentials=creds)

    # Define your date range (e.g., past month)
    start_date = "2023-11-01"
    end_date = "2023-11-30"


    # Call the Gmail API and search for messages
    query = f"after:{start_date} before:{end_date}"
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        print('No messages found.')
    else:
        print('Scanning messages:')
        for message in messages:  # Check the first 20 messages
            msg = service.users().messages().get(userId='me', id=message['id']).execute()

            # Extract subject and snippet
            headers = msg.get("payload", {}).get("headers", [])
            subject = next((header['value'] for header in headers if header['name'] == 'Subject'), "No Subject")
            snippet = msg.get('snippet', '')

            # Check if the email contains any invoices/receipts/etc. -YES? -> SAVE
            if is_relevant_email(subject, snippet):
                print(f"Relevant Email Found: {subject}")

                
                parts = msg.get("payload", {}).get("parts", [])
                # Does it have an attachment? -YES? -> SAVE
                for part in parts:
                    if part.get("mimeType") == "application/pdf":  # Check for the PDF
                        attachment_id = part.get("body", {}).get("attachmentId")
                        filename = part["filename"] or msg["id"]

                        user_id = 'me'  # Authenticated user
                        message_id = message['id']    # Message containing the attachment
                
                        # Get the attachment
                        attachment_data = get_attachment(service, user_id, message_id, attachment_id)

                        # Save the attachment to a file
                        if attachment_data:
                            save_attachment(attachment_data, filename)



if __name__ == '__main__':
    main()
