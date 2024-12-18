# -*- coding: utf-8 -*-
"""DataMatics.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/10Rz3kJrujpq6G8dru7J5BD__zo3NAd_I
"""



!pip install pytesseract

!sudo apt install tesseract-ocr

!pip install easyocr
!pip install invoice2data

import os
import re
import cv2
import pytesseract
import easyocr
from invoice2data import extract_data
from openpyxl import Workbook
import email
import imaplib

# Preprocess image for better OCR results
def preprocess_image(image_path):
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
    preprocessed_image_path = "preprocessed_image.png"
    cv2.imwrite(preprocessed_image_path, thresh)
    return preprocessed_image_path

# Extract text using EasyOCR and Tesseract
def extract_text_from_image(image_path):
    try:
        preprocessed_image_path = preprocess_image(image_path)

        reader = easyocr.Reader(['en'])
        easyocr_results = reader.readtext(preprocessed_image_path)
        easyocr_text = " ".join([result[1] for result in easyocr_results])

        config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz./:'
        tesseract_text = pytesseract.image_to_string(preprocessed_image_path, config=config)

        combined_text = easyocr_text + " " + tesseract_text
        return combined_text
    except Exception as e:
        print(f"Error extracting text from {image_path}: {e}")
        return ""

# Extract key data using regex
def extract_additional_data(text):
    patterns = {
        "date": r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b\d{1,2}\b)',
        "time": r'(\b\d{1,2}:\d{2}\s*[AP]M\b|\b\d{1,2}[\s:]?\d{2}\b)',
        "bill_number": r'\b(Bill Number|Invoice No|Invoice Number|No)\s*:? ?(\w+)',
        "rate": r'\bRate\s*:? ?([\d,.]+)',
        "volume": r'\bVolume\s*:? ?([\d,.]+)',
        "amount": r'\b(?:Total|Amount|Due)\s*:? ?([\d,.]+)'
    }

    extracted_data = {key: "Not found" for key in patterns}

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            extracted_data[key] = match.group(1)

    return extracted_data

# Extract data from PDF invoices
def extract_data_from_invoice(pdf_path):
    try:
        return extract_data(pdf_path)
    except Exception as e:
        print(f"Error extracting data from {pdf_path}: {e}")
        return {}

# Handle email attachments
def handle_attachment(part):
    filename = part.get_filename()
    attachment_data = {key: "Not found" for key in ["date", "time", "bill_number", "rate", "volume", "amount"]}

    if filename:
        print(f"Processing attachment: {filename}")
        file_extension = os.path.splitext(filename)[1].lower()
        with open(filename, 'wb') as f:
            f.write(part.get_payload(decode=True))

        try:
            if file_extension == ".pdf":
                attachment_data = extract_data_from_invoice(filename)
            elif file_extension in [".png", ".jpg", ".jpeg"]:
                text = extract_text_from_image(filename)
                print(f"Extracted Text:\n{text}")
                attachment_data = extract_additional_data(text)
        except Exception as e:
            print(f"Error processing {filename}: {e}")
        finally:
            os.remove(filename)

    return attachment_data

# Connect to the email server
def connect_to_email_server(email_user, email_pass):
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_user, email_pass)
        mail.select('inbox')
        print("Connected to email server.")
        return mail
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None

# Fetch emails from the inbox
def fetch_emails(mail):
    result, data = mail.search(None, 'ALL')
    data_list = []

    for num in data[0].split():
        result, email_data = mail.fetch(num, '(RFC822)')
        raw_email = email_data[0][1].decode('utf-8')
        email_message = email.message_from_string(raw_email)
        data_list.append(extract_email_data(email_message))

    return data_list

# Extract data from email
def extract_email_data(email_message):
    from_email = email_message['From']
    date_ = email_message['Date']
    attachment_flag = "No"
    attachment_data = {key: "Not found" for key in ["date", "time", "bill_number", "rate", "volume", "amount"]}

    for part in email_message.walk():
        if part.get_content_disposition() == "attachment":
            attachment_flag = "Yes"
            attachment_data = handle_attachment(part)
            break

    return [
        from_email, date_, attachment_flag,
        attachment_data['date'], attachment_data['time'],
        attachment_data['bill_number'], attachment_data['rate'],
        attachment_data['volume'], attachment_data['amount']
    ]

# Save extracted data to Excel
def save_to_excel(data_list, filename):
    wb = Workbook()
    ws = wb.active
    ws.append(["Sender Email", "Date", "Attachment", "Attachment Date", "Attachment Time",
               "Bill Number", "Rate", "Volume", "Amount"])

    for data in data_list:
        ws.append(data)

    wb.save(filename)

# Main function to execute the script
if __name__ == "__main__":
    email_user = "yashbharambe.ai@gmail.com"
    email_pass = "nimnfwucjibjapby"  # App-specific password
    mail = connect_to_email_server(email_user, email_pass)

    if mail:
        data_list = fetch_emails(mail)
        save_to_excel(data_list, "extracted_data.xlsx")
        mail.logout()