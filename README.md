# Toggl.com to absence.io

Get reports out of toggl and adds them to absence.io time tracking.
Automatically detects breaks in between toggl entries.

Stores keys securely in your keyring.

## Installation

    pip install -r requirements.txt

You need to provide a absence.io user id and toggl workspace id in the config.ini file.

### Absence.io
Top right user menu -> Show Profile -> Integrations -> API KEY -> ID

You will also be asked for the user key which is securely stored in your keyring.

### Toggl
Bottom left user menu -> Profile settings -> API Token

To get your workspace id simply run:

    curl -v -u YOUR_TOGGL_API_TOKEN:api_token -X GET https://www.toggl.com/api/v8/workspaces

## Usage

    python export.py

    or

    python export.py --since 2019-12-01 --till 2019-12-08

By default the script will export your toggl data of the current week.
