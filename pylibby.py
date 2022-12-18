#!/usr/bin/env python3

# Copyright (C) 2022 Raymond Olsen
#
# This file is part of PyLibby.
#
# PyLibby is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PyLibby is distributed in the hope that it will be useful,pip
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PyLibby. If not, see <http://www.gnu.org/licenses/>.

import json
import sys
import urllib.parse
import requests
import os
from typing import Callable
from os import path
import datetime
import argparse
from tabulate import tabulate

class Libby:
    id_path = None
    def __init__(self, id_path: str, code: str = None):
        self.id_path = id_path
        self.http_session = requests.Session()

        headers = {
            "Accept": "application/json",
        }

        self.http_session.headers.update(headers)

        if os.path.isfile(id_path):
            with open(id_path, "r") as r:
                identity = json.loads(r.read())
            self.http_session.headers.update({'Authorization': f'Bearer {identity["identity"]}'})
            if not self.is_logged_in():
                if code:
                    self.clone_by_code(code)
                    if not self.is_logged_in():
                        raise RuntimeError("Couldn't log in with code, are you sure you wrote it correctly and that "
                                           "you are within the time limit?"
                                           "You need at least 1 registered library card.")
                else:
                    raise RuntimeError("Not logged in and no code was given.")
        elif code:
            self.get_chip()
            self.clone_by_code(code)
            if self.is_logged_in():
                #Updating id file
                self.get_chip()
            else:
                raise RuntimeError("Couldn't log in with code, are you sure you wrote it correctly and that "
                                   "you are within the time limit?"
                                   "You need at least 1 registered library card.")

        else:
            raise RuntimeError("PyLibby needs a path to a JSON-file with ID-info. To get the file you"
                               " need to provide a code you can get from libby by going to"
                               " Settings->Copy To Another Device.")

    def is_logged_in(self) -> bool:
        s = self.get_sync()
        if "result" in s:
            if s["result"] == "missing_chip":
                return False
            if s["result"] == "synchronized":
                if "cards" in s:
                    if s["cards"]:
                        # at least one card in account means we have to be logged in
                        return True
        return False

    def borrow_book(self, title_id:str, card_id: str, days: int = 21) -> dict:
        media_info = self.get_media_info(title_id)
        j = {
            "period": days,
            "units": "days",
            "lucky_day": None,
            "title_format": media_info["type"]["id"]
        }

        url = f"https://sentry-read.svc.overdrive.com/card/{card_id}/loan/{title_id}"
        resp = self.http_session.post(url, json=j)
        if resp.status_code != 200:
            raise RuntimeError(f"Couldn't borrow book: {resp.json()}, you may need to verify your card in the app.")
        return resp.json()

    def borrow_book_on_any_logged_in_library(self, title_id:str, days: int = 21) -> dict:
        for card in self.get_sync()["cards"]:
            if int(card["counts"]["loan"]) >= int(card["limits"]["loan"]):
                print(f"Card {card['cardId']} at {card['advantageKey']} is at its limit, skipping.")
            elif self.is_book_available(card["advantageKey"], title_id):
                print(f"Book available at {card['advantageKey']}.")
                return self.borrow_book(title_id, card["cardId"], days)
            else:
                print(f"Book not available at {card['advantageKey']}.")
        print("Book not available at any of your libraries.")
        return {}

    def return_book(self, title_id:str, card_id: str = None):
        if not card_id:
            loans = self.get_loans()
            for loan in loans:
                if loan["id"] == title_id:
                    card_id = loan["cardId"]
                    break

        if not card_id:
            raise RuntimeError("Couldn't find cardId on loan or couldn't find loan at all, can't return it.")

        url = f"https://sentry-read.svc.overdrive.com/card/{card_id}/loan/{title_id}"
        resp = self.http_session.delete(url)
        if resp.status_code != 200:
            raise RuntimeError(f"Couldn't return book: {resp.json()}, you may need to verify your card in the app.")

    def get_sync(self) -> dict:
        return self.http_session.get("https://sentry-read.svc.overdrive.com/chip/sync").json()

    def get_media_info(self, title_id: str) -> dict:
        # API documentation: https://thunder-api.overdrive.com/docs/ui/index
        return self.http_session.get(f"https://thunder.api.overdrive.com/v2/media/{title_id}").json()

    def get_loans(self) -> list:
        return self.get_sync()["loans"]

    def get_chip(self) -> dict:
        response = self.http_session.post("https://sentry-read.svc.overdrive.com/chip", params={"client": "dewey"}).json()
        self.http_session.headers.update({'Authorization': f'Bearer {response["identity"]}'})
        with open(self.id_path, "w") as w:
            w.write(json.dumps(response, indent=4, sort_keys=True))

        return response

    def clone_by_code(self, code: int) -> dict:
        resp = self.http_session.post("https://sentry-read.svc.overdrive.com/chip/clone/code", data={"code": code})
        self.get_chip()
        return resp.json()

    def have_loan(self, title_id: str) -> bool:
        return any(l for l in self.get_sync()["loans"] if l["id"] == title_id)

    def get_loan(self, title_id: str) -> dict:
        return next((l for l in self.get_sync()["loans"] if l["id"] == title_id), {})

    def open_audiobook(self, card_id: str, title_id: str) -> dict:
        loan = self.get_loan(title_id)
        if not loan:
            raise RuntimeError("Can't open a book if it is not checked out.")

        url = f"https://sentry-read.svc.overdrive.com/open/{'audiobook' if loan['type']['id'] == 'audiobook' else 'book'}/card/{card_id}/title/{title_id}"
        audiobook = self.http_session.get(url).json()
        message = audiobook["message"]
        openbook_url = audiobook["urls"]["openbook"]

        #THIS IS IMPORTANT
        old_headers = self.http_session.headers
        self.http_session.headers = None
        #We need this to set a cookie for us
        web_url_with_message = audiobook["urls"]["web"] + "?" + message
        self.http_session.get(web_url_with_message)

        self.http_session.headers = old_headers

        return {
                "audiobook_urls": audiobook,
                "openbook":  self.http_session.get(openbook_url).json(),
                "media_info": self.get_media_info(title_id)
                }

    def search_for_book_in_logged_in_libraries(self, query: str) -> list:
        # TODO: make this more readable
        return requests.get(f"https://thunder.api.overdrive.com/v2/media/search?libraryKey={'libraryKey='.join([card['advantageKey'] + '&' for card in self.get_sync()['cards']])}query={query}").json()

    def search_for_audiobook_in_logged_in_libraries(self, query: str) -> list:
        return [h for h in self.search_for_book_in_logged_in_libraries(query) if h["type"]["id"] == "audiobook"]

    def search_for_ebook_in_logged_in_libraries(self, query: str) -> list:
        return [h for h in self.search_for_book_in_logged_in_libraries(query) if h["type"]["id"] == "ebook"]

    def is_book_available(self, library: str, title_id: str) -> bool:
        availability = requests.get(f"https://thunder.api.overdrive.com/v2/libraries/{library}/media/{title_id}/availability").json()
        if "isAvailable" in availability:
            return availability["isAvailable"]
        return False

    def get_author(self, title_id: str) -> str:
        return " and ".join([creator["name"] for creator in self.get_media_info(title_id)["creators"] if creator["role"] == "Author"])

    def get_author_by_media_info(self, media_info: dict) -> str:
        return " and ".join([creator["name"] for creator in media_info["creators"] if creator["role"] == "Author"])

    def get_languages_by_media_info(self, media_info: dict) -> str:
        return " and ".join([l["Name"] for l in media_info["languages"]])

    def get_narrator(self, title_id: str) -> str:
        media_info = self.get_media_info(title_id)
        return " and ".join([creator["name"] for creator in media_info["creators"] if creator["role"] == "Narrator"])

    def get_narrator_by_media_info(self, media_info: dict) -> str:
        return " and ".join([creator["name"] for creator in media_info["creators"] if creator["role"] == "Narrator"])

    def get_download_path(self, media_info: dict) -> str:
        # this should probably take a template, hardcoding the format for now
        author_path = self.get_author_by_media_info(media_info)
        book_path = ""
        if "detailedSeries" in media_info:
            if "readingOrder" in media_info["detailedSeries"]:
                book_path += f"{media_info['detailedSeries']['seriesName']}_{media_info['detailedSeries']['readingOrder']}-"
        book_path += f"{media_info['title']}"
        if "publishDate" in media_info:
            book_path +=f"-[{str(datetime.datetime.fromisoformat(media_info['publishDate']).year)}]"
        book_path += f"-[ODID_{media_info['id']}]"
        for f in media_info["formats"]:
            for i in f["identifiers"]:
                if i["type"] == "ISBN":
                    book_path += f"-[ISBN_{str(i['value'])}]"
                    return os.path.join(author_path, book_path).replace(" ", "_")

        return os.path.join(author_path, book_path).replace(" ", "_")

    def download_audiobook_mp3(self, loan: dict, output_path: str,
                               callback_functions: list[Callable[[str, int], None]] = None,
                               save_info=False, download_covers=True):
        # Workaround for getting audiobook without ODM
        audiobook_info = self.open_audiobook(loan["cardId"], loan["id"])
        if not os.path.exists(output_path):
            raise RuntimeError(f"Path does not exist: {output_path}")

        final_path = os.path.join(output_path, self.get_download_path(audiobook_info["media_info"]))
        os.makedirs(final_path, exist_ok=True)

        for download_url in \
                [audiobook_info["audiobook_urls"]["urls"]["web"] + s["path"] for s in audiobook_info["openbook"]["spine"]]:
            resp = self.http_session.get(download_url, timeout=10, stream=True)

            filename = self.get_filename(download_url)
            with open(os.path.join(final_path, filename), "wb") as w:
                downloaded = 0
                mb = 0
                for chunk in resp.iter_content(1024):
                    w.write(chunk)
                    downloaded += 1024
                    if downloaded > 1024 * 1000:
                        mb += 1
                        downloaded = 0
                        if callback_functions:
                            for f in callback_functions:
                                f(filename, mb)
                        else:
                            print(f"{filename}: Downloaded {mb}MB.")

        if save_info:
            with open(os.path.join(final_path, "info.json"), "w") as w:
                w.write(json.dumps(audiobook_info, indent=4))

        if download_covers:
            self.download_covers(loan, final_path)

    def get_filename(self, url: str) -> str:
        url_parsed = urllib.parse.unquote(url)
        url_parsed = url_parsed.split("#")[0]
        url_parsed = url_parsed.split("?")[0]
        url_parsed = url_parsed.split("://")[-1]
        url_parsed = url_parsed.split("}")[-1]
        return path.basename(url_parsed)

    def get_formats(self, title_id: str) -> list[str]:
        # Can return formats that are not available on loan, I'm guessing different libraries have different formats
        info = self.get_media_info(title_id)
        return [f["id"] for f in info["formats"]]

    def get_formats_for_loaned_book_or_media_info(self, loan: dict) -> list[str]:
        return [f["id"] for f in loan["formats"]]

    def download_covers(self, media_info: dict, path_: str):
        if "covers" in media_info:
            for c in media_info["covers"].keys():
                with open(os.path.join(path_, c + ".jpg"), "wb") as w:
                    w.write(self.http_session.get(media_info["covers"][c]["href"]).content)

    def download_loan(self, loan: dict, format_id: str, output_path: str, save_info=False, download=True, download_covers=True, get_odm=False):
        # Does not actually download ebook, only gets the ODM or ACSM for now.
        # Will however download audiobook-mp3, without ODM
        if not os.path.exists(output_path):
            raise RuntimeError("Path does not exist: ", output_path)

        format_is_available = any(f for f in loan["formats"] if f["id"] == format_id)
        if format_is_available:
            url = f"https://sentry-read.svc.overdrive.com/card/{loan['cardId']}/loan/{loan['id']}/fulfill/{format_id}"
            if format_id == "audiobook-mp3":
                if get_odm:
                    download_path = self.get_download_path(self.get_media_info(loan["id"]))
                    final_path = os.path.join(output_path, download_path)
                    if download or save_info:
                        os.makedirs(final_path, exist_ok=True)
                    fulfill = self.http_session.get(url).json()
                    if "fulfill" in fulfill:
                        fulfill_url = fulfill["fulfill"]["href"]
                        with open(os.path.join(final_path, loan["id"] + ".odm"), "wb") as w:
                            w.write(self.http_session.get(fulfill_url).content)
                            print(f"Downloaded odm file to {w.name}.")
                    else:
                        raise RuntimeError(f"Something went wrong when downloading odm: {fulfill}")
                else:
                    self.download_audiobook_mp3(loan, output_path, save_info=save_info)
            else:
                #resp = self.http_session.get(url)
                #print(resp)
                #print(resp.content)
                #quit()
                fulfill = self.http_session.get(url).json()
                if "fulfill" in fulfill:
                    fulfill_url = fulfill["fulfill"]["href"]
                    download_path = self.get_download_path(self.get_media_info(loan["id"]))
                    final_path = os.path.join(output_path,download_path)
                    if download or save_info:
                        os.makedirs(final_path, exist_ok=True)

                    if format_id == "audiobook-overdrive":
                        print(fulfill_url)
                    elif format_id == "ebook-kobo":
                        print(fulfill_url)
                        raise NotImplementedError("ebook-kobo is not implemented yet.")
                        #kobo_headers = {"User-Agent": "Mozilla/5.0 (Linux; U; Android 2.0; en-us;) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1 (Kobo Touch)"}
                    elif format_id == "ebook-epub-adobe":
                        print("Will download acsm file, use a tool like Knock (https://github.com/agschaid/knock) to get your book.")
                        if download:
                            with open(os.path.join(final_path, self.get_filename(fulfill_url)), "wb") as w:
                                w.write(self.http_session.get(fulfill_url).content)
                                print(f"Downloaded acsm file to {w.name}.")
                        else:
                            print(fulfill_url)
                    else:
                        print(fulfill_url)

                    if save_info:
                        with open(os.path.join(final_path, "loan.json"), "w") as w:
                            w.write(json.dumps(loan, indent=4))

                    if download_covers:
                        self.download_covers(loan, final_path)

                    return fulfill_url

                else:
                    raise RuntimeError("Something went wrong: ", fulfill)

        else:
            raise RuntimeError(f"Format {format_id} not available for title {loan['id']}. Available formats: {str([f['id'] for f in loan['formats']])}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='PyLibby',
        description='CLI for Libby')

    parser.add_argument("-id", "--id-file", help="Path to id JSON (which you get from '--code'. Defaults to id.json).", default="id.json", metavar="path")
    parser.add_argument("-c", "--code", help="Login with code.", type=int, metavar="12345678")
    parser.add_argument("-o", "--output", help="Output dir, will output to current dir if omitted.", default=".", metavar="path")
    parser.add_argument("-s", "--search", help="Search for book in your libraries.", metavar='"search query"')
    parser.add_argument("-sa", "--search-audiobook", help="Search for audiobook in your libraries.", metavar='"search query"')
    parser.add_argument("-se", "--search-ebook", help="Search for ebook in your libraries.", metavar='"search query"')
    parser.add_argument("-ls", "--list-loans", help="List your current loans.", action="store_true")
    parser.add_argument("-lsc", "--list-cards", help="List your current cards.", action="store_true")
    parser.add_argument("-b", "--borrow-book", help="Borrow book from the first library where it's available.", metavar="id")
    parser.add_argument("-r", "--return-book", help="Return book. If the same book is borrowed in multiple libraries this will only return the first one.", metavar="id")
    parser.add_argument("-dl", "--download", help="Download book or audiobook by title id. You need to have borrowed the book.", metavar="id")
    parser.add_argument("-f", "--format", help="Which format to download.", type=str, metavar="id", required="-dl" in sys.argv or "--download" in sys.argv)
    parser.add_argument("-odm", help="Download the ODM instead of directly downloading mp3's for 'audiobook-mp3'.", action="store_true")
    parser.add_argument("-si", "--save-info", help="Save information about downloaded book.", action="store_true")
    parser.add_argument("-i", "--info", help="Print media info (JSON).", type=str, metavar="id")
    parser.add_argument("-j", "--json", help="Output verbose JSON instead of tables.", action="store_true")
    args = parser.parse_args()

    L = Libby(args.id_file, code=args.code)
    def create_table(media_infos: list, narrators=True):
        table = []
        for m in media_infos:
            row  = {
                "Id": m['id'],
                "Type": m['type']['id'],
                "Formats": "\n".join(L.get_formats_for_loaned_book_or_media_info(m)) or "unavailable",
                "Libraries": "\n".join(lib + ": available" if m['siteAvailabilities'][lib]["isAvailable"]
                                       else lib + ": unavailable" for lib in m['siteAvailabilities'].keys()),
                "Authors": "\n".join(L.get_author_by_media_info(m).split(" and ")),
                "Title": m['title']
            }
            if narrators:
                row["Narrators"] = "\n".join(L.get_narrator_by_media_info(m).split(" and "))
            table.append(row)

        return table

    # Doing it this way makes the program more flexible.
    # You can do stuff like -ls -b 999 -ls -dl 999 -r 999 -ls
    # or -b 111 -b 222 -b 333.
    # This is not how argparse is usually used.
    arg_pos = 0
    for arg in sys.argv:
        if arg in ["-ls", "--list-loans"]:
            loans = L.get_loans()
            if args.json:
                print(json.dumps(loans, indent=4))
            else:
                s = L.get_sync()
                t = []
                print("Loans:")
                for lo in loans:
                    mi = L.get_media_info(lo["id"])
                    t.append({
                        "Id": lo['id'],
                        "Type": lo['type']['id'],
                        "Formats": "\n".join(L.get_formats_for_loaned_book_or_media_info(lo)) or "unavailable",
                        "Library": next((c["advantageKey"] for c in s["cards"] if c["cardId"] == lo["cardId"]), ""),
                        "CardId": lo["cardId"],
                        "Authors": "\n".join(L.get_author_by_media_info(mi).split(" and ")),
                        "Title": lo['title'],
                        "Narrators": "\n".join(L.get_narrator_by_media_info(mi).split(" and "))
                    })
                print(tabulate(t, headers="keys", tablefmt="grid"))

        elif arg in ["-lsc", "--list-cards"]:
            s = L.get_sync()
            if args.json:
                print(json.dumps(s, indent=4))
            else:
                t = []
                print("Cards:")
                for c in s["cards"]:
                    t.append({
                        "Id": c['cardId'],
                        "Library": c["advantageKey"]
                    })
                print(tabulate(t, headers="keys", tablefmt="grid"))

        elif arg in ["-dl", "--download"]:
            print("Downloading", sys.argv[arg_pos + 1])
            L.download_loan(L.get_loan(sys.argv[arg_pos + 1]), args.format, args.output, args.save_info, get_odm=args.odm)

        elif arg in ["-r", "--return-book"]:
            L.return_book(sys.argv[arg_pos + 1])
            print(f"Book returned: {sys.argv[arg_pos + 1]}")

        elif arg in ["-b", "--borrow-book"]:
            L.borrow_book_on_any_logged_in_library(sys.argv[arg_pos + 1])
            print(f"Book borrowed: {sys.argv[arg_pos + 1]}")

        elif arg in ["-i", "--info"]:
            mi = L.get_media_info(sys.argv[arg_pos + 1])
            print(json.dumps(mi, indent=4))

        elif arg in ["-s", "--search"]:
            hits = L.search_for_book_in_logged_in_libraries(sys.argv[arg_pos + 1])
            if args.json:
                print(json.dumps(hits, indent=4))
            else:
                print("Search:")
                print(tabulate(create_table(hits), headers="keys", tablefmt="grid"))

        elif arg in ["-sa", "--search-audiobook"]:
            hits = L.search_for_audiobook_in_logged_in_libraries(sys.argv[arg_pos + 1])
            if args.json:
                print(json.dumps(hits, indent=4))
            else:
                print("Search Audiobook:")
                print(tabulate(create_table(hits), headers="keys", tablefmt="grid"))

        elif arg in ["-se", "--search-ebook"]:
            hits = L.search_for_ebook_in_logged_in_libraries(sys.argv[arg_pos + 1])
            if args.json:
                print(json.dumps(hits, indent=4))
            else:
                print("Search Ebook:")
                print(tabulate(create_table(hits, narrators=False), headers="keys", tablefmt="grid"))

        arg_pos += 1