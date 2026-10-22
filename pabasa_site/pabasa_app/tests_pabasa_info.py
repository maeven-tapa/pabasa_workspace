"""Public-page architecture guards for the introductory Overview."""
from html.parser import HTMLParser
from collections import Counter

from django.contrib.auth.models import AnonymousUser
from django.contrib.staticfiles import finders
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve


class PageStructure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        node = {"tag": tag, "attrs": attrs, "ancestors": tuple(self.stack)}
        self.nodes.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(attrs.get("id", ""))

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()

    def handle_startendtag(self, tag, attrs):
        self.nodes.append({"tag": tag, "attrs": dict(attrs), "ancestors": tuple(self.stack)})


class PabasaInfoArchitectureTests(SimpleTestCase):
    def setUp(self):
        request = RequestFactory().get("/what-is-pabasa/")
        request.resolver_match = resolve(request.path)
        request.user = AnonymousUser()
        self.response = request.resolver_match.func(request)
        self.html = self.response.content.decode()
        self.page = PageStructure()
        self.page.feed(self.html)
        self.by_id = {n["attrs"]["id"]: n for n in self.page.nodes if "id" in n["attrs"]}

    def test_all_five_sections_exist_and_overview_contains_only_the_introduction(self):
        self.assertEqual(self.response.status_code, 200)
        section_ids = [n["attrs"].get("id") for n in self.page.nodes if n["tag"] == "section" and n["attrs"].get("id", "").startswith("platform-")]
        self.assertEqual(section_ids, ["platform-overview", "platform-purpose", "platform-tools", "platform-audience", "platform-process"])
        for chapter in ("overview-prologue", "overview-teachers", "overview-students"):
            self.assertNotIn(chapter, self.by_id)
        for section in section_ids[1:]:
            self.assertNotIn("platform-overview", self.by_id[section]["ancestors"])

    def test_removed_chapters_leave_no_links_and_page_navigation_still_resolves(self):
        chapter_links = [n for n in self.page.nodes if n["tag"] == "a" and n["attrs"].get("href", "").startswith("#overview-")]
        self.assertEqual(chapter_links, [])
        for node in self.page.nodes:
            href = node["attrs"].get("href", "")
            if node["tag"] == "a" and href.startswith("#") and len(href) > 1:
                self.assertIn(href[1:], self.by_id)
        page_targets = [n["attrs"]["data-section"] for n in self.page.nodes if "data-section" in n["attrs"]]
        self.assertEqual(page_targets, ["platform-overview", "platform-purpose", "platform-tools", "platform-audience", "platform-process"])

    def test_introduction_keeps_unique_identifiers_and_available_artwork(self):
        identifiers = Counter(n["attrs"]["id"] for n in self.page.nodes if "id" in n["attrs"])
        self.assertEqual([key for key, count in identifiers.items() if count > 1], [])
        self.assertEqual(sum(n["tag"] == "h1" for n in self.page.nodes), 1)
        self.assertIn("story-title", self.by_id)
        artwork = [n["attrs"] for n in self.page.nodes if n["tag"] == "img" and "platform-overview" in n["ancestors"]]
        required = {"hero1.webp"}
        self.assertTrue(required.issubset({image["src"].split("/")[-1] for image in artwork}))
        for image in artwork:
            self.assertIn("alt", image)
            self.assertIn("width", image)
            self.assertIn("height", image)
            self.assertTrue(finders.find(image["src"].split("?")[0].removeprefix("/static/")))
        self.assertNotIn("data-gather-pages", self.html)
        # The separate student workspace still retains its real activity preview.
        self.assertIn("Session 3 · Lesson 7 · Gawain 2C", self.html)
