# Streamlit Secrets Configuration for Google Sheets Integration

This file documents the secrets you need to configure in Streamlit Cloud for Google Sheets and Google Drive integration.

## Setup Steps

### 1. Create a Google Cloud Project and Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin** > **Service Accounts**
5. Click **Create Service Account**
6. Give it a name (e.g., "streamlit-sheets-writer")
7. Click **Create and Continue**
8. Skip the optional steps and click **Done**
9. Click on the service account you just created
10. Go to the **Keys** tab
11. Click **Add Key** > **Create new key**
12. Choose **JSON** and click **Create**
13. Save the downloaded JSON file securely

### 2. Create a Google Sheet

1. Go to [Google Sheets](https://sheets.google.com/)
2. Create a new spreadsheet
3. Give it a name (e.g., "CWI-HSLU Quality Survey Responses")
4. **Important:** Share the spreadsheet with the service account email (found in the JSON file as `client_email`), giving it **Editor** access

The app creates these worksheets automatically on first save:

| Worksheet | Purpose |
|-----------|---------|
| `responses` | Full trial response data (one row per trial) |
| `responses_analysis` | Compact analysis columns for quick review |
| `demographics` | Participant demographic information |
| `_metadata` | Internal participant counter (cell `A1`) |

### 3. Create a Google Drive Folder (optional but recommended)

1. Go to [Google Drive](https://drive.google.com/)
2. Create a folder (e.g., "CWI-HSLU Survey Participant JSON")
3. Share the folder with the service account email, giving it **Editor** access
4. Copy the folder ID from the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE` 
Each participant gets a `{participant_id}.json` file in this folder, updated after every saved trial.

### 4. Configure Streamlit Cloud Secrets

In your Streamlit Cloud app settings, go to **Secrets** and add the following TOML configuration:

```toml
spreadsheet_name = "CWI-HSLU Quality Survey Responses"
drive_folder_id = "your-google-drive-folder-id"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com"
```

**Note:** Copy the values from the JSON file you downloaded in step 1. `drive_folder_id` is optional; if omitted, only Google Sheets rows are saved.

### 5. Local Development (Optional)

For local testing, create a `.streamlit/secrets.toml` file in your project root with the same content as above.

**Important:** Add `.streamlit/secrets.toml` to your `.gitignore` to avoid committing sensitive credentials!

## Data Structure

### `responses` worksheet

One row per real-study trial, including metadata such as sequence, criterion, chosen method, video paths, and response time.

### `responses_analysis` worksheet

Compact columns used for analysis:

- `app_version`
- `participant_id`
- `index`
- `sequence`
- `video_a`
- `video_b`
- `choice`
- `selected_video`
- `time_used_seconds`
- `timestamp`

### `demographics` worksheet

One row per participant with timestamp, participant ID, app version, age group, sex, occupation, expertise level, and nationality/region.

### Google Drive participant JSON

Each file contains:

```json
{
  "participant_id": "20260722_204900_1",
  "app_version": "participant",
  "demographics": { "...": "..." },
  "responses": [ "... compact analysis rows ..." ]
}
```
