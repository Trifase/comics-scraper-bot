import datetime
import json
import locale
import logging
import sys
import traceback

import httpx
from bs4 import BeautifulSoup
from telegram import (
    LinkPreviewOptions,
    Update,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Defaults,
)

from config import ID_COMICS, TOKEN

# Logging setup
logger = logging.getLogger()

logging.basicConfig(
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler("logs/log.log", maxBytes=1000000, backupCount=5),
    ],
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
)

# httpx become very noisy from 0.24.1, so we set it to WARNING
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)

# We also want to lower the log level of the scheduler
aps_logger = logging.getLogger("apscheduler")
aps_logger.setLevel(logging.WARNING)


locale.setlocale(locale.LC_TIME, "it_IT.UTF-8")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    logging.info(f"È accaduto un errore! {tb_list[2]}\n{tb_list[1]}")

    ID_BOTCENTRAL = -1001180175690
    await context.bot.send_message(
        chat_id=ID_BOTCENTRAL,
        text=f'<pre><code class="language-python">{tb_string[:4000]}</code></pre>',
        parse_mode="HTML",
    )


async def post_init(app: Application) -> None:
    if "last_urls" not in app.bot_data:
        app.bot_data["last_urls"] = {}

    with open("last_urls.json") as last_urls_json:
        last_urls = json.load(last_urls_json)
        app.bot_data["last_urls"] = last_urls
    logger.info("Pronti!")


async def scrape_comics(context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.info("It's scraping' time.")
    text, url = get_comic("smbc")
    await send_if_not_already_sent(context, "smbc", url, text)

    text, url = get_comic("pbf")
    await send_if_not_already_sent(context, "pbf", url, text)

    text, url = get_comic("octopuns")
    await send_if_not_already_sent(context, "octopuns", url, text)

    text, url = get_comic("poorlydrawnlines")
    await send_if_not_already_sent(context, "poorlydrawnlines", url, text)

    text, url = get_comic("xkcd")
    await send_if_not_already_sent(context, "xkcd", url, text)

    text, url = get_comic("oglaf")
    await send_if_not_already_sent(context, "oglaf", url, text, spoiler=True)
    logging.info("Scraping completed.")
    logging.info("========================")


def get_comic(comic):
    date = datetime.datetime.now().strftime("%Y-%m-%d")

    if comic == "smbc":
        url = "https://www.smbc-comics.com/"
        r = httpx.get(url)
        soup = BeautifulSoup(r.text, features="lxml")
        image = soup.find("img", id="cc-comic")
        url = image.attrs["src"]
        text = image.attrs["title"]
        text = f"<b>Saturday Morning Breakfast Cereal</b>, {date}\n\n{text}"

    elif comic == "pbf":
        url = "https://pbfcomics.com/"
        r = httpx.get(url)
        soup = BeautifulSoup(r.text, features="lxml")
        div_comic = soup.find("div", id="comic")
        image = div_comic.find("img", class_="lazyload")
        url = image.attrs["data-src"]
        text = image.attrs["title"].replace("PBF-", "")
        text = f"<b>Perry Bible Fellowship</b>, {date}\n\n{text}"

    elif comic == "octopuns":
        url = "https://www.octopuns.com/"
        r = httpx.get(url)
        soup = BeautifulSoup(r.text, features="lxml")
        div_comic = soup.find("div", class_="post-body entry-content")
        text = soup.find("h3").text.strip()
        image = div_comic.find("img")
        url = image.attrs["src"]
        text = f"<b>Octopuns</b>, {date}\n\n{text}"

    elif comic == "poorlydrawnlines":
        url = "https://poorlydrawnlines.com/"
        r = httpx.get(url)
        soup = BeautifulSoup(r.text, features="lxml")
        div_comic = soup.find("div", class_="entry-content")
        image = div_comic.find("img")
        url = image.attrs["data-src"]
        text = f"<b>Poorly Drawn Lines</b>, {date}"

    elif comic == "xkcd":
        url = "https://xkcd.com/"
        r = httpx.get(url)
        soup = BeautifulSoup(r.text, features="lxml")
        div_comic = soup.find("div", id="comic")
        image = div_comic.find("img")
        url = f'https:{image.attrs["src"]}'
        text = image.attrs["title"]
        text = f"<b>XKCD</b>, {date}\n\n{text}"

    elif comic == "oglaf":
        url = "https://www.oglaf.com/"
        cookies = {"AGE_CONFIRMED": "yes"}
        r = httpx.get(url, cookies=cookies)
        soup = BeautifulSoup(r.text, features="lxml")
        image = soup.find("img", id="strip")
        url = image.attrs["src"]
        text = image.attrs["title"]
        alt = image.attrs["alt"]
        text = f"<b>Oglaf</b>, {date}\n\n{alt}\n{text}"

    return (text, url)


async def send_if_not_already_sent(context: ContextTypes.DEFAULT_TYPE, comic, url, text, spoiler=False) -> None:
    last_urls = context.bot_data["last_urls"]
    last_url = last_urls.get(comic, None)
    if last_url == url:
        logging.info(f"[{comic}] già inviato.")
        return
    last_urls[comic] = url
    context.bot_data["last_urls"] = last_urls
    with open("last_urls.json", "w") as last_urls_json:
        json.dump(last_urls, last_urls_json)

    logging.info(f"[{comic}] Invio.")
    await context.bot.send_photo(ID_COMICS, url, caption=text, parse_mode="HTML", has_spoiler=spoiler)


async def manual_scrape_comics(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    return await scrape_comics(context)


def main():
    defaults = Defaults(
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )

    builder = ApplicationBuilder()
    builder.token(TOKEN)
    builder.defaults(defaults)
    builder.post_init(post_init)

    app = builder.build()

    j = app.job_queue
    j.run_once(scrape_comics, 5, data=None)
    j.run_repeating(scrape_comics, interval=3600, data=None, job_kwargs={"misfire_grace_time": 25})

    app.add_handler(CommandHandler("manual_scrape", manual_scrape_comics), 1)
    app.add_error_handler(error_handler)

    app.run_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)


main()
