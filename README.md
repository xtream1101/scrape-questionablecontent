# scrape-questionable_content

Developed using Python 3.4

Scrape the site http://questionablecontent.net/ and save all the comics on the site and update on each run

## Dependencies
- [BeautifulSoup4](https://pypi.python.org/pypi/beautifulsoup4)
- [SQLAlchemy](https://pypi.python.org/pypi/SQLAlchemy)
- [custom_utils](https://xnet.serverx.co/git/xtream1101/custom-utils)

## Usage
`$ python3 main.py "/dir/to/download/dir"`  
Set this to run as a cron to keep up to date with the content
