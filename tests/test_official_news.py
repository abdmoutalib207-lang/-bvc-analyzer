import json

from pipeline.official_news import parse_ammc, annotate_provenance
from pipeline import fetch_news as news

NOW = "2026-09-20T12:00:00+00:00"


def row(title="Sonasid — Résultats S1 2026", date="2026-09-18T15:56:48Z", link="/sites/default/files/sonasid.pdf"):
    return f'''<li class="actualites-row"><div><time datetime="{date}">18/09/2026</time></div>
    <div class="views-field views-field-title"><span>{title}</span></div>
    <a href="{link}" type="application/pdf">PDF</a></li>'''


def test_official_index_is_not_financial_content_confirmation():
    articles = parse_ammc(row() + row(), NOW)
    assert len(articles) == 1
    a = articles[0]
    assert a["date"] == "2026-09-18T15:56:48+00:00"
    assert a["first_seen_at"] == NOW
    assert a["url"] == "https://www.ammc.ma/sites/default/files/sonasid.pdf"
    assert a["validation_status"] == "listed_officially"
    assert a["document_content_verified"] is False
    assert a["usable_for_score"] is False


def test_untrusted_links_missing_dates_and_future_dates_rejected():
    assert not parse_ammc(row(link="https://example.com/fake.pdf"), NOW)
    assert not parse_ammc(row(date=""), NOW)
    assert not parse_ammc(row(date="2027-09-18T15:56:48Z"), NOW)
    assert not parse_ammc(row(link="javascript:alert(1)"), NOW)


def test_relay_cannot_claim_official_confirmation():
    a = annotate_provenance({"source": "Bank Al-Maghrib", "url": "https://news.google.com/rss/articles/abc", "sentiment": "POSITIF"}, NOW)
    assert a["source_type"] == "search_relay"
    assert a["validation_status"] == "unverified"
    assert a["sentiment"] == "NEUTRE"
    assert not a["usable_for_score"]
    assert news._parse_date("") == ""


def test_collect_then_outage_preserves_publication_and_first_seen(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "OUTPUT_PATH", tmp_path / "news.json")
    monkeypatch.setattr(news, "SOURCES_RSS", [])
    monkeypatch.setattr(news, "fetch_medias24_api", lambda n: [])
    monkeypatch.setattr(news, "fetch_idb_news", lambda n: [])
    # Publication within the running archive window, no network.
    from datetime import datetime, timezone, timedelta
    published = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    class Response:
        text = row(date=published)
        def raise_for_status(self): pass
    monkeypatch.setattr(news.requests, "get", lambda *a, **k: Response())
    first = news.run()
    assert len(first["articles"]) == 1
    assert first["articles"][0]["tickers"] == ["SNA"]
    assert first["source_health"]["AMMC documents"]["status"] == "ok"
    def unavailable(*args, **kwargs): raise TimeoutError("offline")
    monkeypatch.setattr(news.requests, "get", unavailable)
    second = news.run()
    assert second["source_health"]["AMMC documents"]["status"] == "error"
    assert second["articles"][0]["first_seen_at"] == first["articles"][0]["first_seen_at"]
    assert second["articles"][0]["sentiment"] == "NEUTRE"
    assert json.loads(news.OUTPUT_PATH.read_text())["count"] == 1


def test_official_documents_survive_a_full_press_feed(tmp_path, monkeypatch):
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(news, "OUTPUT_PATH", tmp_path / "news.json")
    monkeypatch.setattr(news, "MAX_ARTICLES", 5)
    monkeypatch.setattr(news, "SOURCES_RSS", [("https://example.test/rss", "Presse", 10)])
    monkeypatch.setattr(news, "fetch_rss", lambda *a, **k: [
        {"id": str(i), "url": f"https://example.test/{i}", "title": "Marché", "source": "Presse",
         "date": now.isoformat(), "tickers": []} for i in range(10)])
    monkeypatch.setattr(news, "fetch_medias24_api", lambda n: [])
    monkeypatch.setattr(news, "fetch_idb_news", lambda n: [])
    class Response:
        text = row(date=(now - timedelta(days=2)).isoformat())
        def raise_for_status(self): pass
    monkeypatch.setattr(news.requests, "get", lambda *a, **k: Response())
    output = news.run()
    assert len(output["articles"]) == 5
    assert sum(a.get("validation_status") == "listed_officially" for a in output["articles"]) == 1
