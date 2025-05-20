import streamlit as st
import requests
import time
import pandas as pd
import io
import zipfile

# === Load Secrets ===
CLIENT_ID = st.secrets["LWA_CLIENT_ID"]
CLIENT_SECRET = st.secrets["LWA_CLIENT_SECRET"]
REFRESH_TOKEN = st.secrets["REFRESH_TOKEN"]
MARKETPLACE_ID = st.secrets["MARKETPLACE_ID"]
SELLER_ID = st.secrets["SELLER_ID"]

st.set_page_config(page_title="Amazon Listing Manager", layout="wide")
st.title("📦 Amazon Listing Manager - SP-API")

# === Function to get access token ===
def get_access_token():
    url = "https://api.amazon.com/auth/o2/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    response = requests.post(url, data=payload)
    response.raise_for_status()
    return response.json()["access_token"]

# === Function to request listings report ===
def request_listings_report(access_token):
    url = "https://sellingpartnerapi-na.amazon.com/reports/2021-06-30/reports"
    headers = {
        "x-amz-access-token": access_token,
        "Content-Type": "application/json"
    }
    payload = {
        "reportType": "GET_MERCHANT_LISTINGS_ALL_DATA",
        "marketplaceIds": [MARKETPLACE_ID]
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["reportId"]

# === Poll for report completion ===
def poll_report_status(report_id, access_token):
    url = f"https://sellingpartnerapi-na.amazon.com/reports/2021-06-30/reports/{report_id}"
    headers = {"x-amz-access-token": access_token}
    for i in range(20):
        time.sleep(15)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        status = data.get("processingStatus")
        st.write(f"⏳ Polling attempt {i+1}: {status}")
        if status == "DONE":
            return data.get("reportDocumentId")
    raise Exception("Report timed out")

# === Download report ===
def download_report(document_id, access_token):
    url = f"https://sellingpartnerapi-na.amazon.com/reports/2021-06-30/documents/{document_id}"
    headers = {"x-amz-access-token": access_token}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    report_url = response.json()["url"]
    report_response = requests.get(report_url)
    report_response.raise_for_status()
    return report_response.content

# === Button to begin ===
if st.button("📥 Download All Listings"):
    try:
        st.info("Authenticating with Amazon SP-API...")
        token = get_access_token()

        st.info("Requesting listings report...")
        report_id = request_listings_report(token)

        st.info("Waiting for report to finish...")
        document_id = poll_report_status(report_id, token)

        st.info("Downloading report contents...")
        content = download_report(document_id, token)

        df = pd.read_csv(io.StringIO(content.decode('utf-8')), sep='\t')
        st.success("✅ Report downloaded and parsed")
        st.dataframe(df.head(100))

        # Export to Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Listings')
        st.download_button("⬇️ Download Excel", data=output.getvalue(), file_name="amazon_listings.xlsx")

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

