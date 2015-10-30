import os
import sys
import signal
import argparse
import configparser
from custom_utils.custom_utils import CustomUtils
from custom_utils.exceptions import *
from custom_utils.sql import *


class QuestionableContent(CustomUtils):

    def __init__(self, base_dir, restart=False, proxies=[], url_header=None):
        super().__init__()
        # Make sure base_dir exists and is created
        self._base_dir = base_dir

        # Do we need to restart
        self._restart = restart

        # Set url_header
        self._url_header = self._set_url_header(url_header)

        # If we have proxies then add them
        if len(proxies) > 0:
            self.set_proxies(proxies)
            self.log("Using IP: " + self.get_current_proxy())

        # Setup database
        self._db_setup()

        # Start parsing the site
        self.start()

    def start(self):
        latest = self.get_latest()

        if self._restart is True:
            progress = 0
        else:
            progress = self.sql.get_progress()

        if latest == progress:
            # Nothing new to get
            self.cprint("Already have the latest")
            return

        for i in range(progress + 1, latest + 1):
            self.cprint("Getting comic: " + str(i))
            if self._restart is True:
                check_data = self._db_session.query(Data).filter(Data.id == i).first()
                if check_data is not None:
                    continue

            if self.parse(i) is not False:
                self.sql.update_progress(i)

    def get_latest(self):
        """
        Parse `http://questionablecontent.net/` and get the id of the newest comic
        :return: id of the newest item
        """
        self.cprint("##\tGetting newest upload id...\n")
        url = "http://questionablecontent.net/archive.php"
        # get the html from the url
        try:
            soup = self.get_site(url, self._url_header)
        except RequestsError as e:
            print("Error getting latest: " + str(e))
            sys.exit(0)

        max_id = int(soup.find("div", {"id": "archive"}).a['href'].split('=')[-1])
        self.cprint("##\tNewest upload: " + str(max_id) + "\n")
        return max_id

    def parse(self, id_):
        """
        Using BeautifulSoup, parse the page for the comic and its data
        :param id_: id of the comic on `http://questionablecontent.net/`
        :return:
        """
        # There is no comic 0
        if id_ == 0:
            return

        prop = {}
        prop['id'] = str(id_)
        base_url = "http://questionablecontent.net"
        url = base_url + "/view.php?comic=" + prop['id']

        # get the html from the url
        try:
            soup = self.get_site(url, self._url_header)
        except RequestsError:
            # TODO: do something ore useful here
            return

        src = soup.find("img", {"id": "strip"})['src']
        prop['img'] = base_url + src

        #####
        # Download comic
        #####
        file_ext = self.get_file_ext(prop['img'])
        file_name = prop['id']

        prop['save_path'] = os.path.join(self._base_dir, prop['id'][-1], self.sanitize(file_name) + file_ext)

        self.download(prop['img'], prop['save_path'], self._url_header)

        # Everything was successful
        return True

    def _set_url_header(self, url_header):
        if url_header is None:
            # Use default from CustomUtils
            return self.get_default_header()
        else:
            return url_header

    def _db_setup(self):
        # Version of this database
        db_version = 1
        db_file = os.path.join(self._base_dir, "xkcd.sqlite")
        self.sql = Sql(db_file, db_version)
        is_same_version = self.sql.set_up_db()
        if not is_same_version:
            # Update database to work with current version
            pass
        # Get session
        self._db_session = self.sql.get_session()


def signal_handler(signal, frame):
    print("")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    # Deal with args
    parser = argparse.ArgumentParser(description='Scrape site and archive data')
    parser.add_argument('-c', '--config', help='Config file')
    parser.add_argument('-d', '--dir', help='Absolute path to save directory')
    parser.add_argument('-r', '--restart', help='Set to start parsing at 0', action='store_true')
    args = parser.parse_args()

    # Set defaults
    save_dir = None
    restart = None
    proxy_list = []

    if args.config is not None:
        # Load config values
        if not os.path.isfile(args.config):
            print("No config file found")
            sys.exit(0)

        config = configparser.ConfigParser()
        config.read(args.config)

    # Check config file first
    if 'main' in config:
        if 'save_dir' in config['main']:
            save_dir = config['main']['save_dir']
        if 'restart' in config['main']:
            if config['main']['restart'].lower() == 'true':
                restart = True
            else:
                restart = False

    # Proxies can only be set via config file
    if 'proxy' in config:
        if 'http' in config['proxy']:
            proxy_list = config['proxy']['http'].split('\n')

    # Command line args will overwrite config args
    if args.dir is not None:
        save_dir = args.dir

    if restart is None or args.restart is True:
        restart = args.restart

    # Check to make sure we have our args
    if args.dir is None and save_dir is None:
        print("You must supply a config file with `save_dir` or -d")
        sys.exit(0)

    save_dir = CustomUtils().create_path(save_dir, is_dir=True)

    # Start the scraper
    scrape = QuestionableContent(save_dir, restart=restart, proxies=proxy_list)

    print("")
