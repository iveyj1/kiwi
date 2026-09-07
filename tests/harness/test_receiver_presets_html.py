from html.parser import HTMLParser

from kiwi_client.client_app import normalize_receiver_address
from kiwi_client.state_store import load_presets_file


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def test_receiver_presets_html_links_every_receiver_register():
    parser = LinkParser()
    parser.feed(open("receiver-presets.html", encoding="utf-8").read())
    linked = {normalize_receiver_address(link) for link in parser.links}
    presets = load_presets_file("presets.toml")["receiver_presets"]
    configured = {normalize_receiver_address(value["receiver"]) for value in presets.values()}

    assert linked == configured
    assert len(parser.links) == len(presets)
