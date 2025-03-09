# YouTube Comment Moderator

This project helps moderate YouTube live chat using OpenAI api. The python script should start as soon as the stream started. When the stream is finished, access to live chat is not supported and moderatino will fail.

## Prerequisites

- Python version 3.11 and pip or later should be installed

- Create a Google project for your moderation app here:
    https://console.cloud.google.com/iam-admin/serviceaccounts

- Enable YouTube Data API v3 for your project here:
    https://console.developers.google.com/apis/api/youtube.googleapis.com/overview

- On the same page go to "Credentials" and create "OAuth 2.0 Client IDs". Make sure you select "Deaktop app". Then save the json file as `client_secret.json` and place it into the project folder.

- Obtain an OpenAI key here https://platform.openai.com/settings/organization/api-keys and define it in a variable in yout environment, i.e.:
    ```
    export OPENAI_API_KEY=sk-proj-...
    ```
    Add some money into your account here: https://platform.openai.com/settings/organization/billing/overview

- Run `pip install -r requirements.txt` to install dependencies

## Validate Rules

Read channel_rules.txt and edit if nessessary

## Start livechat moderator like this:

Execute `python moderator.py <youtube lifechat video url>` 

```
python moderator.py https://www.youtube.com/live/...
```
