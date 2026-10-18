import pytest

from ojagent.jobstreet import JobStreetClient
from ojagent.models import JobPosting, JobSummary
from ojagent.scraper import OnlineJobsClient
from ojagent.sources import SOURCES, AllSites, make_source
from ojagent.triage import triage


def test_make_source_returns_the_client_for_each_key():
    assert isinstance(make_source("onlinejobs"), OnlineJobsClient)
    assert isinstance(make_source("jobstreet"), JobStreetClient)
    both = make_source("all")
    assert isinstance(both, AllSites)
    assert [type(c) for c in both.clients] == [OnlineJobsClient, JobStreetClient]


def test_sources_have_labels_and_caps():
    assert SOURCES["onlinejobs"] == ("onlinejobs.ph", OnlineJobsClient, 90)
    assert SOURCES["jobstreet"] == ("JobStreet", JobStreetClient, 90)
    assert SOURCES["all"] == ("onlinejobs.ph + JobStreet", AllSites, 90)


class PagedSite:
    """A fake site with `total` jobs, 30 per page, ids prefixed so tests can tell sites apart."""

    def __init__(self, prefix: str, total: int):
        self.prefix, self.total = prefix, total
        self.searched: list[int] = []
        self.fetched: list[str] = []

    def search(self, keyword=None, page=0):
        self.searched.append(page)
        ids = range(page * 30, min((page + 1) * 30, self.total))
        return [JobSummary(job_id=f"{self.prefix}{i}", title=f"{self.prefix} job {i}", url="u") for i in ids]

    def get_job(self, job_id):
        self.fetched.append(job_id)
        return JobPosting(job_id=job_id, title=job_id, url="u", description="Python work")


class HideAll:
    """A Jev stub that screens out every card, so a scan only searches."""

    def fit_probabilities(self, profile, jobs):
        return {j.job_id: 0.0 for j in jobs}


def scan(sites, limit):
    result = triage(AllSites(sites), HideAll(), "profile", limit=limit, keyword="python")
    return [c.job_id for c in result.cards]


def test_postings_count_is_the_total_split_evenly_between_sites():
    olj, js = PagedSite("o", 100), PagedSite("j", 100)
    ids = scan([olj, js], limit=30)
    assert len(ids) == 30
    assert sum(i.startswith("o") for i in ids) == 15
    assert ids[:4] == ["o0", "j0", "o1", "j1"]
    assert olj.searched == js.searched == [0]  # one results page each covers 15


def test_ninety_postings_need_two_pages_per_site():
    olj, js = PagedSite("o", 100), PagedSite("j", 100)
    ids = scan([olj, js], limit=90)
    assert len(ids) == 90 and sum(i.startswith("j") for i in ids) == 45
    assert olj.searched == js.searched == [0, 1]


def test_the_other_site_fills_in_when_one_runs_short():
    olj, js = PagedSite("o", 5), PagedSite("j", 100)
    ids = scan([olj, js], limit=60)
    assert len(ids) == 60
    assert sum(i.startswith("o") for i in ids) == 5
    assert olj.searched == [0, 1] and js.searched == [0, 1]


def test_an_empty_site_is_not_searched_again():
    olj, js = PagedSite("o", 0), PagedSite("j", 100)
    scan([olj, js], limit=60)
    assert olj.searched == [0]


def test_get_job_goes_to_the_site_that_listed_it():
    olj, js = PagedSite("o", 30), PagedSite("j", 30)
    both = AllSites([olj, js])
    both.search("python", 0)
    both.get_job("j3")
    both.get_job("o7")
    assert js.fetched == ["j3"] and olj.fetched == ["o7"]
    with pytest.raises(KeyError):
        both.get_job("x1")
