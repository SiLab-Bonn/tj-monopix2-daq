#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# BGNet (Background prediction with neural nets for Belle II at SuperKEKB)
# Author: The BGNet developers
#
# See git log for contributors and copyright holders.
# This file is licensed under MIT licence, see LICENSE.md.

import getpass
import time
import traceback
import requests
import datetime
import pytz
from bs4 import BeautifulSoup
import logging


class elog():
    """
    Class to manage the upload of reports to the elog.

    Usage:
    elog('Year', 'Month', 'Day', 'Type of Report', attachments=['path/to/file',], credFile='path/to/credFile').uploadToElog()

    Parameters
    ----------
    year : str
        Year of report as YYYY.
    month : str
        Month of report as MM.
    day : str
        Day of report as DD.
    type : str
        Type of report to be submitted. Displayed in elog.
    attachments : list of str, default []
        List of paths to files to attach to elog report.
    username : str, default None
        Desy username to log in to elog.
    password : str, default None
        Desy password to log in to elog.
    credFile : str, default None
        Path to textfile with Desy credentials.

    See Also
    -------
    goReporter.py : Calls this class, member functions.
    """

    def __init__(
            self,
            year,
            month,
            day,
            type,
            postMessageOfReport=False,
            attachments=[],
            username=None,
            password=None,
            credFileElog=None,
            credFileb2rc=None):
        '''Constructor.'''
        super(elog, self).__init__()
        self.type = type
        # parameters for URL
        self.prefix = 'https'
        self.hostname = 'elog.belle2.org'
        self.port = '443'
        self.logbook = 'Bkg+analysis'
        if not self.logbook.startswith('elog/'):
            self.logbook = 'elog/' + self.logbook
        # 3 Options to give login credentials: text file, command prompt, keyword
        self.author = ''
        if username is None or password is None:
            if credFileElog:
                with open(credFileElog) as file:
                    lines = [line.rstrip() for line in file]
                self.username = lines[0]
                self.password = lines[1]
                try:
                    self.author = lines[2]
                except BaseException:
                    self.author = ''
            else:
                print("ELOG user credentials (DESY Account):")
                self.username = input("Username:")
                self.password = getpass.getpass("Password:")

        if self.author == '':
            self.author = self.username

        self.jsttime = datetime.datetime.now(pytz.timezone('Asia/Tokyo')).strftime("%Y/%m/%d %H:%M JST")  # Time of upload
        self.subject = ''  # Subject line in elog report
        self.starttime = '{}/{}/{} 00:00 JST'.format(year, month, day)  # Provided by goReporter.py
        # Figure out endtime
        start = datetime.datetime.strptime('{}/{}/{} 00:00'.format(year, month, day), "%Y/%m/%d %H:%M")
        timedelta_day = datetime.timedelta(days=1)
        timedelta_minute = datetime.timedelta(minutes=1)
        start = start+timedelta_day-timedelta_minute
        self.endtime = start.strftime("%Y/%m/%d %H:%M")

        self.file_text = ''  # Placeholder in case we want to write something in the report
        self.attachments = attachments  # Option to use shutil to validate path

        # possible way to build different reports/define which function is used for which report
        # self.createElog = getattr(self, "create%s" % self.type)
        self.postMessageOfReport = postMessageOfReport
        self.alias = 'BGNet Bot'
        self._b2rc_url = 'https://b2rc.kek.jp'
        self._b2rc_userid = ''
        self._b2rc_username = ''
        self._b2rc_token = ''
        self._resume = False
        self._b2rc_session = None
        self.usernameb2rc = ''
        self.passwordb2rc = ''
        self.avatar = 'https://owncloud.gwdg.de/index.php/apps/files_sharing/ajax/publicpreview.php?x=1848&y=593&a=true&file=Selection_111.png&t=WiMaxhyNuewsmMy&scalingup=0'
        if self.postMessageOfReport:
            self._b2rc_session = requests.Session()
            self._b2rc_session.auth = requests.auth.HTTPBasicAuth('cosmic', 'running')
            if credFileb2rc:
                with open(credFileb2rc) as file:
                    lines = [line.rstrip() for line in file]
                self.usernameb2rc = lines[0]
                self.passwordb2rc = lines[1]
                try:
                    self.alias = lines[2]
                except BaseException:
                    self.alias = 'BGNet Bot'
            else:
                self.usernameb2rc = input("Username:")
                self.passwordb2rc = getpass.getpass("Password:")

    def buildRequest(self):
        """
        Build requests.Request object for report.

        Put together the elog address.
        Collect data and attachments for the elog report. Data fills strings in elog.
        Attachments are media files attached to elog report.

        Returns
        -------
        request.Request
            Request object to use to open a session.
        """
        req_address = "{}://{}:{}/{}".format(self.prefix, self.hostname, self.port, self.logbook)
        auth = requests.auth.HTTPBasicAuth(self.username, self.password)
        data = {
            'cmd': 'Submit',
            'Type': self.type,
            'Author': self.author,
            'JSTTime': self.jsttime,
            'Subject': self.subject,
            'StartTime': self.starttime,
            'EndTime': self.endtime
        }
        files = [
            ('Text', self.file_text)
        ]
        for attachment in self.attachments:
            files.append(
                ('attfile', open(attachment, 'rb'))
            )
        return requests.Request('POST', req_address, auth=auth, data=data, files=files)

    def uploadToElog(self):
        """
        Open session and uploads report to elog.

        Call function to upload a report to the elog

        Returns
        -------
        bool
            True when upload successful, False if upload unsuccessful.
        """
        time.sleep(3)
        requestToElog = self.buildRequest()
        if isinstance(requestToElog, requests.Request):
            with requests.Session() as s:
                s.auth = requestToElog.auth
                try:
                    s.request("GET", requestToElog.url)
                    prep = s.prepare_request(requestToElog)
                    settings = s.merge_environment_settings(prep.url, {}, None, None, None)
                    resp = s.send(prep, **settings)
                except Exception as e:
                    logging.error(traceback.format_exc())
                    return False
            if resp.ok:
                print("Elog Entry successfully transmitted to:")
                print("{}".format(requestToElog.url))
                print('Attachments uploaded:')
                for attachment in self.attachments:
                    print(attachment)
                if self.postMessageOfReport:
                    print('Post message to rocket chat')
                    self.rocketChat()
            else:
                print("Error during transmitting Elog.")
                print('Reason: {}'.format(resp.reason))
                return False
            return True
        else:
            print('No valid instance of requests.Request')
            return False

# #################################
# B2RC posting
# #################################
    def api_get(self, name, params=None):
        """Send GET request."""
        result = None
        success = False
        retries = 0
        while True:
            try:
                result = self._b2rc_session.get(self._b2rc_url + name, params=params)
                result.raise_for_status()
                success = True
            except Exception as e:
                logging.error(traceback.format_exc())
                time.sleep(10)
                retries += 1
            if success:
                break
            if retries >= 10:
                logging.warning('Elog timeout')
                break
        return result

    def api_post(self, name, data, files=None):
        """Send POST request."""
        result = None
        success = False
        retries = 0
        while True:
            try:
                result = self._b2rc_session.post(self._b2rc_url + name,
                                                 data=data, files=files)
                result.raise_for_status()
                success = True
            except Exception as e:
                logging.error(traceback.format_exc())
                time.sleep(10)
                retries += 1
            if success:
                break
            if retries >= 10:
                logging.warning('Elog timeout')
                break
        return result

    def logout(self):
        '''Logout from API.'''
        if not self._resume:
            self.api_get('/api/v1/logout')

    def authenticate(self, token=None):
        '''Authenticate, manage and test API session.'''
        # clear old authentication
        if self._b2rc_token:
            self.logout()
            self._b2rc_session.headers.update({'X-Auth-Token': None,
                                               'X-User-Id': None})
        if token:
            result = self.api_post('/api/v1/login', data={'resume': token})
        else:
            result = self.api_post('/api/v1/login', data={'user': self.usernameb2rc, 'password': self.passwordb2rc})
        if not result:
            logging.warning('Could not reach b2rc login')
            return False
        if result.status_code != 200 or result.json()['status'] != 'success':
            logging.warning('B2rc api: Invalid authentication')
            return False
        self._resume = (token is not None)
        self._b2rc_token = result.json()['data']['authToken']
        self._b2rc_userid = result.json()['data']['userId']
        self._b2rc_username = result.json()['data']['me']['name']
        self._b2rc_session.headers.update({'X-Auth-Token': self._b2rc_token,
                                           'X-User-Id': self._b2rc_userid})
        return True

    def get_ref_from_html(self, html):
        '''Clean html file to retrieve latest report URL.'''
        if html == []:
            logging.info('Elog empty or not reachable, no URL for b2rc posting')
            return ''
        soup = BeautifulSoup(html, "html.parser")
        hrefs = soup.find_all("a", href=True)
        cleaned_hrefs = []
        for ref in hrefs:
            cleaned_hrefs.append(ref['href'])
        base_ref = cleaned_hrefs[0]
        cleaned_hrefs = sorted(list(set(cleaned_hrefs)))
        cleaned_hrefs = [string for string in cleaned_hrefs if not string.endswith(
            ".pdf") and string.startswith("../Bkg+analysis/")]
        number_of_report = []
        for href in cleaned_hrefs:
            number = href.replace("../Bkg+analysis/", "")
            if number != "":
                number_of_report.append(int(number))
        number_of_report
        latest_report_url = base_ref+'Bkg+analysis'+"/"+str(max(number_of_report))
        return latest_report_url

    def search_elog(self):
        '''GET html file of elog logbook page.'''
        # TODO use params/header for server query, could improve performance and simplify code
        # search_params = {}
        # search_params['mode']='XML'
        # search_params['reverse']='1'
        # search_params['last']=timeFrame
        # search_params['npp']='100'
        # search_params['type'] = '%5EDaily+Report%24'
        with requests.Session() as s:
            s.auth = requests.auth.HTTPBasicAuth(self.username, self.password)
            url_str = "{}://{}:{}/{}/".format(self.prefix, self.hostname, self.port, self.logbook)
            success = False
            retries = 0
            while True:
                try:
                    result = s.get(url_str)
                    result.raise_for_status()
                    success = True
                except Exception as e:
                    logging.error(traceback.format_exc())
                    time.sleep(10)
                    retries += 1
                if success:
                    break
                if retries >= 10:
                    logging.warning('B2rc posting timeout')
                    break
            return result.text

    def postMessage(self, msg, ch, alias=None, avatar=None, emoji=None):
        '''Build and post message to RC.'''
        if not ch.startswith('#') and not ch.startswith('@'):
            raise AssertionError(f'Invalid channel or user name {ch}')
        data = {'channel': ch, 'text': msg}
        if self.alias:
            data['alias'] = self.alias
        if emoji and emoji.startswith(':'):
            data['emoji'] = ':'.join(('', str(emoji).strip(':'), ''))
        if self.avatar and self.avatar.startswith('http'):
            data['avatar'] = self.avatar

        result = self.api_post('/api/v1/chat.postMessage', data)
        if not result:
            logging.warning('Could not reach b2rc login')
            return False

        return result.json()['success']

    def postReport(self, url):
        '''Define message text and channel.'''
        text = '{} {}\n[{}]({})'.format(
            self.starttime, self.type, url, url)
        result = self.postMessage(text, '#bgnet')
        if result is not True:
            raise RuntimeError('postReport: Sending shift report to b2rc failed')
        return result

    def rocketChat(self):
        '''Logs on to b2rc api and creates message wit latest elog entry.'''
        self.authenticate()
        for i in range(5):
            time.sleep(1)
            try:
                html = self.search_elog()
            except Exception as e:
                logging.error(traceback.format_exc())
                continue
            last_report_url = self.get_ref_from_html(html)
            # TODO get time information and reference to uploaded report. Cant be sure that last report is this one
        try:
            self.postReport(last_report_url)
        except Exception as e:
            logging.warning('RocketChat: Sending shift report to b2rc failed: {}'.format(e))
            return False
        return True
