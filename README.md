# PyLibby, a CLI for Libby

This tool lets you borrow, download and return (audio)books from [Libby](https://libbyapp.com) (OverDrive). 
You can download audiobooks without the extra step of getting the ODM file first.


## How to run PyLibby
You can use pipenv, first install the stuff in the Pipfile (you only need to do this the first time):
```bash
pipenv install
```
Then run PyLibby like this
```bash
pipenv run python pylibby.py -h
```

<pre>CLI for Libby

options:
  -h, --help            show this help message and exit
  -id path, --id-file path
                        Path to id JSON (which you get from &apos;--code&apos;).
  -c 12345678, --code 12345678
                        Login with code.
  -o path, --output path
                        Output dir, will output to current dir if omitted.
  -s &quot;search query&quot;, --search &quot;search query&quot;
                        Search for book in your libraries.
  -sa &quot;search query&quot;, --search-audiobook &quot;search query&quot;
                        Search for audiobook in your libraries.
  -se &quot;search query&quot;, --search-ebook &quot;search query&quot;
                        Search for ebook in your libraries.
  -ls, --list-loans     List your current loans.
  -lsc, --list-cards    List your current cards.
  -b id, --borrow-book id
                        Borrow book from the first library where it&apos;s available.
  -r id, --return-book id
                        Return book. If the same book is borrowed in multiple libraries this will only return the first one.
  -dl id, --download id
                        Download book or audiobook by title id. You need to have borrowed the book.
  -f id, --format id    Which format to download.
  -odm                  Download the ODM instead of directly downloading mp3&apos;s for &apos;audiobook-mp3&apos;.
  -si, --save-info      Save information about downloaded book.
  -i id, --info id      Print media info (JSON).
  -j, --json            Output verbose JSON instead of tables.
</pre>

Alternatively you can run PyLibby without pipenv, but make sure you have 
installed the requirements, "requests" and "tabulate"


You need to log in before you can start using PyLibby. 
You can do this by logging in to Libby on any device and
going to Settings->Copy To Another Device.
You will get a code there which you can use like this:

```bash
python pylibby.py -c 12345678
```

To check if you are logged in you can try listing your loans like this:
```bash
python pylibby.py -ls
```
<pre>+--------+-----------+---------------------+-----------+----------+--------------+--------------+---------------+
|     Id | Type      | Formats             | Library   |   CardId | Authors      | Title        | Narrators     |
+========+===========+=====================+===========+==========+==============+==============+===============+
| 123456 | ebook     | ebook-overdrive     | name1     | 87654321 | Mary Shelley | Frankenstein |               |
|        |           | ebook-epub-adobe    |           |          |              |              |               |
|        |           | ebook-epub-open     |           |          |              |              |               |
+--------+-----------+---------------------+-----------+----------+--------------+--------------+---------------+
| 654321 | audiobook | audiobook-overdrive | name2     | 12345678 | Bram Stoker  | Dracula      | Tavia Gilbert |
|        |           | audiobook-mp3       |           |          |              |              | J. P. Guimont |
+--------+-----------+---------------------+-----------+----------+--------------+--------------+---------------+
</pre>

To download a book you need to specify the format and output path. 
For audiobooks the format will always be "audiobook-mp3".
```bash
python pylibby.py -dl 654321 -f audiobook-mp3 -o /home/username/books
```
You can search for books like this:
```bash
python pylibby.py -s "moby dick"
```
<pre>+---------+-----------+---------------------+------------------------+-----------------+-----------+------------------+
|      Id | Type      | Formats             | Libraries              | Authors         | Title     | Narrators        |
+=========+===========+=====================+========================+=================+===========+==================+
| 1234567 | audiobook | audiobook-overdrive | name3: available       | Herman Melville | Moby Dick | Pete Cross       |
|         |           | audiobook-mp3       |                        |                 |           |                  |
+---------+-----------+---------------------+------------------------+-----------------+-----------+------------------+
|  654321 | ebook     | ebook-overdrive     | name1: available       | Herman Melville | Moby Dick |                  |
|         |           | ebook-epub-adobe    | name2: unavailable     |                 |           |                  |
|         |           | ebook-epub-open     | name3: unavailable     |                 |           |                  |
|         |           | ebook-pdf-adobe     | name4: available       |                 |           |                  |
|         |           | ebook-pdf-open      |                        |                 |           |                  |
+---------+-----------+---------------------+------------------------+-----------------+-----------+------------------+
| 1111111 | ebook     | ebook-kindle        | name1: available       | Herman Melville | Moby Dick |                  |
|         |           | ebook-overdrive     |                        |                 |           |                  |
|         |           | ebook-epub-adobe    |                        |                 |           |                  |
|         |           | ebook-kobo          |                        |                 |           |                  |
+---------+-----------+---------------------+------------------------+-----------------+-----------+------------------+
</pre>

You can chain together multiple arguments like this:
```bash
python pylibby.py -b 87654321 -b 12345678 -ls -dl 12345678 -f audiobook-mp3 -r 12345678 -ls
```


## Doesn't work?
As I mainly use Libby for audiobooks this tool is focused on that. 
If you want to download ebooks your best bet is to try the "ebook-epub-adobe"-format
and use something like [Knock](https://web.archive.org/web/20221016154220/https://github.com/BentonEdmondson/knock).
Unfortunately it was removed from GitHub, but you can still download it [here](https://web.archive.org/web/20221020182238/https://github.com/BentonEdmondson/knock/releases).
Most other formats will just print out a link you can open in your browser.

This tool has only been tested on Linux, I don't know if it will run on other OS's.


## Info
* There's a swagger API with documentation [here](https://thunder-api.overdrive.com/docs/ui/index), but I couldn't get everything to work.
* "ebook-overdrive"-format (Libby web reader) is mostly a regular epub. The book is base64encoded in .xhtml files which we can get. I think most of the toc.ncx file can be reconstructed from openbook.json. Every book could in theory be downloaded this way, then we wouldn't need to bother with acsm's and so on.
* "ebook-kobo"-format is often/always listed as available even if it isn't...? I don't have a device I can test with and I don't know how it works.
* You can still get an ODM file by using ```-odm```


## Thanks to
* Overdrive for their service.
* The Norwegian libraries that are a part of Overdrive.


## Legal
This program is not authorized by Overdrive/Libby. It does not intentionally circumvent any 
restrictions in Overdrive's or Libby's services, 
but instead works in the same way as their own software. 
This means that you will need a valid library card and also a license for 
each book you download (you need to have "borrowed" them). 
PyLibby does not remove DRM from files it downloads.


## License
Copyright © 2022 Raymond Olsen.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see https://www.gnu.org/licenses/

---
#### Donation
If this software was helpful to you, you may donate any amount here.  
Thank you!

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate?hosted_button_id=HCETPXTC7Y4GA)