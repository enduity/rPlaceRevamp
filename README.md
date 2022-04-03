# rPlaceRevamp
## About

This is a script to draw r/Eesti imagery to r/place.

## Features

- Support for multiple accounts
- Determines the cooldown time remaining for each account
- Detects existing matching pixels on the r/place map and skips them
- Automatically converts colors to the r/place color palette
- Automatically pulls the most recent r/Eesti png from a configurable URL

## Requirements

- [Python 3](https://www.python.org/downloads/)
- [A Reddit App Client ID and App Secret Key](https://www.reddit.com/prefs/apps)

## How to Get App Client ID and App Secret Key

You need to generate an app client id and app secret key for each account in order to use this script.

Steps:

1. Visit <https://www.reddit.com/prefs/apps>
2. Click "create (another) app" button at very bottom
3. Select the "script" option and fill in the fields with anything

If you don't want to create a development app for each account, you can add each username as a developer in the developer app settings. You will need to duplicate the client ID and secret in .env, though.

## Python Package Requirements

Install requirements from 'requirements.txt' file.

```shell
pip3 install -r requirements.txt
```

## Get Started

Change the filename of `config.json.example` to `config.json`

Fill the following lines with your Reddit App data:

```javascript
  "app": {
        "client_id": "YOUR-CLIENT-ID",
        "secret_key": "YOUR-SECRET-KEY"
    }
```

Each account needs the username and password, optionally you can add an account-specific secret key:
```javascript
"accounts": {
        "reddit_user_1": {
            "pw": "USER-PASSWORD"
        },
        "reddit_user_2": {
            "pw": "USER-PASSWORD",
            "client_id": "OPTIONAL-CLIENT-ID",
            "secret_key": "OPTIONAL-SECRET-KEY"
        }
    }
```
Note: if you add one of the optional values, you must add the other.

## Run the Script

```bash
# Normally
python run.py
# Sometimes
python3 run.py
```


