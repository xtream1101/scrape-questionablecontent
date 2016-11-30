import re
import sys
import time
import json
import cutil
import signal
import logging
from scraper_monitor import scraper_monitor
from models import db_session, Setting, Comic, NoResultFound
from scraper_lib import Scraper, Web

# Create logger for this script
logger = logging.getLogger(__name__)


class Worker:

    def __init__(self, web, comic_id):
        """
        Worker Profile

        Run for each item that needs parsing
        Each thread has a web instance that is used for parsing
        """
        # `web` is what utilizes the profiles and proxying
        self.web = web
        self.comic_id = comic_id

        # Get the sites content as a beautifulsoup object
        logger.info("Getting comic {id}".format(id=self.comic_id))
        url = "http://www.questionablecontent.net/view.php?comic={id}".format(id=self.comic_id)
        response = self.web.get_site(url, page_format='html')
        if response is None:
            logger.warning("Response was None for url {url}".format(url=url))

        else:
            parsed_data = self.parse(response)
            if len(parsed_data) > 0:
                # Add raw data to db
                self.web.scraper.insert_data(parsed_data)

                # Remove id from list of comics to get
                self.web.scraper.comic_ids.remove(self.comic_id)

                # Add success count to stats. Keeps track of how much ref data has been parsed
                self.web.scraper.track_stat('ref_data_success_count', 1)

        # Take it easy on the site
        time.sleep(1)

    def parse(self, soup):
        """
        :return: List of items with their details
        """
        # Adds title
        rdata = self.web.scraper.archive_list.get(self.comic_id)

        # Parse the items here and return the content to be added to the db
        img_src = "http://www.questionablecontent.net" + soup.find('img', {'id': 'strip'})['src'][1:]
        news = soup.find('div', {'id': 'news'}).text.strip()

        comic_filename = '{last_num}/{comic_id}.png'\
                          .format(last_num=str(self.comic_id)[-1],
                                  comic_id=self.comic_id)
        rdata.update({'comic_id': self.comic_id,
                      'news': news,
                      'file_path': self.web.download(img_src, comic_filename),
                      'time_collected': cutil.get_datetime(),
                      })

        return rdata

class QuestionableContentComics(Scraper):

    def __init__(self, config_file=None):
        super().__init__('questionablecontent')

        self.archive_list = self.load_archive_list()
        self.max_id = self.get_latest()
        self.last_id_scraped = self.get_last_scraped()
        self.comic_ids = []

    def start(self):
        """
        Send the ref data to the worker threads
        """
        if self.max_id == self.last_id_scraped:
            # No need to continue
            logger.info("Already have the newest comic")
            return

        self.comic_ids = list(range(self.last_id_scraped + 1, self.max_id + 1))

        # Log how many items in total we will be parsing
        scraper.stats['ref_data_count'] = len(self.comic_ids)

        # Only ever use 1 thread here
        self.thread_profile(1, 'requests', self.comic_ids, Worker)


    def load_archive_list(self):
        """
        Load all the comics and store in a dict with the id's as keys
        Need to do this since this is the only place where the date posted is listed
        """
        rdata = {}
        tmp_web = Web(self, 'requests')

        url = "http://www.questionablecontent.net/archive.php"
        try:
            soup = tmp_web.get_site(url, page_format='html')
        except RequestsError as e:
            logger.critical("Problem getting comic archive", exc_info=True)
            sys.exit(1)

        entries = soup.find('div', {'class': 'row'}).find_all('a')

        comic_archive_pattern = re.compile("Comic\s?(?P<id>\d+)\s?.\s?(?P<title>.*)")
        for entry in entries:
            try:
                results = re.match(comic_archive_pattern, entry.text)
                if results:
                    matched = results.groupdict()
                    comic_id = int(matched.get('id'))
                    comic_title = matched.get('title')

                    # Fix some erros in the archive list
                    # Comic 0 does not exist, but is linked to
                    if comic_id == 0:
                        continue
                    # Comic 2310 has 2 entries, hard code the correct values
                    if comic_id == 2310:
                        comic_title = 'The Experiment'

                    rdata[comic_id] = {'title': comic_title}

                    # This is the last comic in the list
                    if comic_id == 1:
                        break

            except Exception:
                logger.exception("Could not get id or title from comic")

        return rdata


    def get_latest(self):
        """
        Get the latest comic id posted
        """
        max_id = max(self.archive_list.keys())
        logger.info("Newest upload: {id}".format(id=max_id))

        return max_id

    def get_last_scraped(self):
        """
        Get last comic scraped
        """
        last_scraped_id = db_session.query(Setting).filter(Setting.bit == 0).one().comic_last_id

        if last_scraped_id is None:
            last_scraped_id = 0

        return last_scraped_id

    def log_last_scraped(self):
        try:
            try:
                last_comic_id = min(self.comic_ids) - 1
            except ValueError:
                last_comic_id = self.max_id

            setting = db_session.query(Setting).filter(Setting.bit == 0).one()
            setting.comic_last_id = last_comic_id
            setting.comic_last_ran = cutil.get_datetime()

            db_session.add(setting)
            db_session.commit()

        except:
            logger.exception("Problem logging last comic scraped")

    def insert_data(self, data):
        """
        Will handle inserting data into the database
        """
        try:
            # Check if comic is in database, if so update else create
            try:
                comic = db_session.query(Comic).filter(Comic.comic_id == data.get('comic_id')).one()
            except NoResultFound:
                comic = Comic()

            comic.title = data.get('title')
            comic.comic_id = data.get('comic_id')
            comic.news = data.get('news')
            comic.file_path = data.get('file_path')
            comic.time_collected = data.get('time_collected')

            db_session.add(comic)
            db_session.commit()

        except Exception:
            db_session.rollback()
            logger.exception("Error adding to db {data}".format(data=data))


def sigint_handler(signal, frame):
    logger.critical("Keyboard Interrupt")
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, sigint_handler)

    try:
        # Setup the scraper
        scraper = QuestionableContentComics()
        try:
            # Start scraping
            scraper.start()
            scraper.cleanup()

        except Exception:
            logger.critical("Main Error", exc_info=True)

    except Exception:
        logger.critical("Setup Error", exc_info=True)

    finally:
        scraper.log_last_scraped()
        try:
            # Log stats
            scraper_monitor.stop(total_urls=scraper.stats['total_urls'],
                                 ref_data_count=scraper.stats['ref_data_count'],
                                 ref_data_success_count=scraper.stats['ref_data_success_count'],
                                 rows_added_to_db=scraper.stats['rows_added_to_db'])

        except NameError:
            # If there is an issue with scraper.stats
            scraper_monitor.stop()

        except Exception:
            logger.critical("Scraper Monitor Stop Error", exc_info=True)
            scraper_monitor.stop()
