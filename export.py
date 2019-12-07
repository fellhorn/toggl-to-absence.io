#!/usr/bin/env python3
import argparse
import configparser
import getpass
import json
import keyring
import requests

from datetime import datetime, timedelta
from dateutil import parser, tz
from mohawk import Sender
from requests.auth import HTTPBasicAuth

# For detecting breaks between two toggl entries
BREAK_MIN_MINUTES = 10
BREAK_MAX_MINUTES = 120

config = configparser.ConfigParser(
    interpolation=configparser.BasicInterpolation())
config.read('config.ini')

absence_user_id = config['ABSENCE']['user_id']
toggl_workspace_id = config['TOGGL']['workspace_id']

absence_key = keyring.get_password('Absence.io', absence_user_id)
toggl_key = keyring.get_password('toggl.com', toggl_workspace_id)

# used to determine breaks
previous_toggl_entry_start = None

if absence_key is None:
    keyring.set_password("Absence.io", absence_user_id, getpass.getpass(prompt="Absence.io key? "))
    absence_key = keyring.get_password('Absence.io', absence_user_id)

if toggl_key is None:
    keyring.set_password("toggl.com", toggl_workspace_id, getpass.getpass(prompt="toggl.com key? "))
    toggl_key = keyring.get_password('toggl.com', toggl_workspace_id)


def get_toggl_data_page(since, until, page):
    url = f'https://toggl.com/reports/api/v2/details?workspace_id={toggl_workspace_id}&since={since}&until={until}&user_agent=absence_exporter&page={page}'

    response = requests.get(url, auth=HTTPBasicAuth(toggl_key, 'api_token'))
    return response.json()


def get_toggl_data(since, until):
    """
    Get the data out of toggl in a paginated manner
    """
    max_retrieved = 0
    data = []
    total_count = 1  # initial value to start
    page = 1

    while max_retrieved < total_count:
        result = get_toggl_data_page(since, until, page)
        data.extend(result['data'])
        max_retrieved += result['per_page']
        total_count = result['total_count']
        page += 1

    return data


def toggl_datetime_to_absence_io(datetime_string: str):
    dt = parser.parse(datetime_string).astimezone(tz.UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def get_timezone(datetime_string: str):
    # TODO: there must be a better way for this?
    timezone = "+" + datetime_string.split("+")[-1]
    timezone = timezone.replace(":", "")

    if timezone == "+0100":
        timezone_name = "CET"
    elif timezone == "+0200":
        timezone_name = "CEST"
    else:
        raise Exception(f"Unknown timezone: {timezone}")

    return timezone, timezone_name


def save_in_absence_io(start: str, end: str, type="work", comment=""):
    timezone, timezone_name = get_timezone(start)

    entry = {
        "userId": absence_user_id,
        "start": toggl_datetime_to_absence_io(start),
        "end": toggl_datetime_to_absence_io(end),
        "type": type,
        "timezone": timezone,
        "timezoneName": timezone_name,
        "commentary": comment,
    }

    print(entry)

    url = 'https://app.absence.io/api/v2/timespans/create'
    method = 'POST'
    content = json.dumps(entry)
    content_type = 'application/json'

    sender = Sender({'id': absence_user_id,
                     'key': absence_key,
                     'algorithm': 'sha256'},
                    url,
                    method,
                    content=content,
                    content_type=content_type)
    response = requests.post(url, data=content, headers={
        'Authorization': sender.request_header, 'Content-Type': content_type})
    return response


def this_weeks_day(days=0):
    """
    Gives the n-th day of this week as yyyy-mm-dd string
    """
    day = datetime.today()
    day = day - timedelta(days=day.weekday()) + timedelta(days=days, weeks=0)

    return day.strftime("%Y-%m-%d")


def was_break(last_start: str, this_end: str):
    """
    Determiens whether there has been a break between the last start and this end
    (toggl entries are iterated from newest to oldest)
    """
    break_end = parser.parse(last_start)
    break_start = parser.parse(this_end)

    duration = break_end - break_start

    minutes = duration.seconds / 60

    if BREAK_MAX_MINUTES >= minutes >= BREAK_MIN_MINUTES:
        return True
    else:
        return False


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='Get you some polls')
    argparser.add_argument('--since',
                           help='Startdate in yyyy-mm-dd. Default: this weeks Monday',
                           default=this_weeks_day(0)
                           )
    argparser.add_argument('--till',
                           help='Enddate in yyyy-mm-dd. Default: this weeks Sunday',
                           default=this_weeks_day(6)
                           )

    argparser.add_argument('--ignore',
                           help='Ignore errors',
                           action='store_true'
                           )

    args = argparser.parse_args()
    print(f"Getting toggl data from {args.since} till {args.till}...")

    data = get_toggl_data(args.since, args.till)
    # dur is in ms
    sum_hours = sum([elem['dur'] for elem in data]) / 1000 / 60 / 60

    print(f'Got {len(data)} toggl entries totaling {sum_hours} hours.')

    for entry in data:
        comment = f"{entry['description']} in project {entry['project']}"
        response = save_in_absence_io(entry['start'], entry['end'], comment=comment)

        if previous_toggl_entry_start and was_break(previous_toggl_entry_start, entry['end']):
            save_in_absence_io(entry['end'], previous_toggl_entry_start, 'break', comment="Autogenerated")

        if response is not None and not response.ok:
            print('Could not upload entry:')
            print(entry)
            print(response.status_code)
            print(response.reason)

            if args.ignore:
                print("Continue...")
            else:
                exit(1)

        previous_toggl_entry_start = entry['start']

    print('Done')
