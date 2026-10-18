from ojagent.jobstreet import JobStreetClient
from ojagent.scraper import OnlineJobsClient
from ojagent.sources import SOURCES, make_source


def test_make_source_returns_the_client_for_each_key():
    assert isinstance(make_source("onlinejobs"), OnlineJobsClient)
    assert isinstance(make_source("jobstreet"), JobStreetClient)


def test_sources_have_labels_and_caps():
    assert SOURCES["onlinejobs"] == ("onlinejobs.ph", OnlineJobsClient, 90)
    assert SOURCES["jobstreet"] == ("JobStreet", JobStreetClient, 90)
