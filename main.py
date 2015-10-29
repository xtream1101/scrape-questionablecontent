import os
import sys
from custom_utils.custom_utils import CustomUtils
from custom_utils.exceptions import *
from custom_utils.sql import *


class QuestionableContent(CustomUtils):

    def __init__(self, base_dir, url_header=None):
        super().__init__()
        # Make sure base_dir exists and is created
        self._base_dir = base_dir

        # Set url_header
        self._url_header = self._set_url_header(url_header)

        # Setup database
        self._db_setup()

        # Start parsing the site
        self.start()

    def start(self):
        latest = self.get_latest()
        progress = self.sql.get_progress()
        if latest == progress:
            # Nothing new to get
            self.cprint("Already have the latest")
            return
        for i in range(progress + 1, latest + 1):
            self.cprint("Getting comic: " + str(i))
            self.parse(i)
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("You must pass in the save directory of the scraper")
    save_dir = CustomUtils().create_path(sys.argv[1], is_dir=True)
    # Start the scraper
    scrape = QuestionableContent(save_dir)
    print("")
