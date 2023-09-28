#!/usr/bin/env python
import csv
import datetime
import shutil
import tarfile
import time
from contextlib import closing
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import click
from lxml import etree
from sentence_transformers import SentenceTransformer, util

now = datetime.datetime.now(tz=datetime.UTC)
directory = Path(__file__).resolve().parent / "data"


@click.group()
def cli():
    pass


def yearmonths(startyear, startmonth, endyear, endmonth):
    if (endyear, endmonth) < (startyear, startmonth):
        raise click.UsageError("end date must be greater than or equal to start date")
    if (endyear, endmonth) > (now.year, now.month):
        raise click.UsageError("end date must not be in the future")

    for year in range(startyear, endyear + 1):
        firstmonth = startmonth if year == startyear else 1
        lastmonth = endmonth if year == endyear else 12

        for month in range(firstmonth, lastmonth + 1):
            yield year, month


@cli.command()
@click.argument("startyear", type=click.IntRange(2015, now.year))
@click.argument("startmonth", type=click.IntRange(1, 12))
@click.argument("endyear", type=click.IntRange(2015, now.year))
@click.argument("endmonth", type=click.IntRange(1, 12))
def download(startyear, startmonth, endyear, endmonth):
    """
    Write monthly packages from TED to a data/ directory.
    """
    directory.mkdir(exist_ok=True)

    for year, month in yearmonths(startyear, startmonth, endyear, endmonth):
        path = directory / f"{year}-{month:02d}.tar.gz"
        if path.exists():
            click.echo(f"{path.name} exists")
            continue

        url = f"ftp://guest:guest@ted.europa.eu/monthly-packages/{year}/{year}-{month:02d}.tar.gz"
        click.echo(f"Retrieving {url} ...")
        try:
            with closing(urlopen(url)) as r, path.open("wb") as f:
                shutil.copyfileobj(r, f)
        except URLError as e:
            click.echo(e.reason, err=True)


@cli.command()
@click.argument("startyear", type=click.IntRange(2015, now.year))
@click.argument("startmonth", type=click.IntRange(1, 12))
@click.argument("endyear", type=click.IntRange(2015, now.year))
@click.argument("endmonth", type=click.IntRange(1, 12))
@click.argument("file", type=click.File("w"))
def transform(startyear, startmonth, endyear, endmonth, file):
    """
    Transform monthly packages in the data/ directory to a CSV file.
    """
    kw = {"namespaces": {"ns": "http://publications.europa.eu/resource/schema/ted/R2.0.9/publication"}}

    writer = csv.DictWriter(
        file,
        [
            "MONTH",
            "FORM",  # codelist
            "LG",  # codelist
            "URI_DOC",  # text
            "CPV2",
            "CPV3",
            "CPV4",
            "CPV5",
            "CPV_MAIN",  # codelist
            "SUITABILITY_ANY",  # boolean
            "SUITABILITY",  # text
            "ECONOMIC_CRITERIA_DOC",  # boolean
            "ECONOMIC_FINANCIAL_INFO_ANY",  # boolean
            "ECONOMIC_FINANCIAL_INFO",  # text
            "ECONOMIC_FINANCIAL_MIN_LEVEL_ANY",  # boolean
            "ECONOMIC_FINANCIAL_MIN_LEVEL",  # text
            "TECHNICAL_CRITERIA_DOC",  # boolean
            "TECHNICAL_PROFESSIONAL_INFO_ANY",  # boolean
            "TECHNICAL_PROFESSIONAL_INFO",  # text
            "TECHNICAL_PROFESSIONAL_MIN_LEVEL_ANY",  # boolean
            "TECHNICAL_PROFESSIONAL_MIN_LEVEL",  # text
            "PERFORMANCE_CONDITIONS_ANY",  # boolean
            "PERFORMANCE_CONDITIONS",  # text
            "CPV_ADDITIONAL",  # colon-separated codelist
            "AC_PROCUREMENT_DOC",  # boolean
            "AC_PRICE",  # boolean
            "AC_QUALITY_ANY",  # boolean
            "AC_QUALITY",  # text
            "AC_COST_ANY",  # boolean
            "AC_COST",  # text
            "CRITERIA_CANDIDATE_ANY",  # boolean
            "CRITERIA_CANDIDATE",  # text
        ],
    )
    writer.writeheader()

    for year, month in yearmonths(startyear, startmonth, endyear, endmonth):
        path = directory / f"{year}-{month:02d}.tar.gz"
        if not path.exists():
            click.echo(f"{path.name} doesn't exist, skipping...", err=True)
            continue

        with tarfile.open(path, "r:gz") as tar:
            while member := tar.next():
                if member.isdir():
                    continue

                doc = etree.fromstring(tar.extractfile(member).read())
                if (
                    # Skip eForms for now.
                    "efext" in doc.nsmap
                    # Skip old defense forms.
                    or doc.nsmap[None] == "http://publications.europa.eu/resource/schema/ted/R2.0.8/publication"
                ):
                    continue

                ted = doc.xpath("/ns:TED_EXPORT", **kw)[0]
                form = ted.xpath("./ns:FORM_SECTION/*[@FORM]", **kw)[0]

                number = form.xpath("./@FORM", **kw)[0]
                # Forms without Section III.
                if number in (
                    # Contract award notice
                    "F03",
                    "F06",
                    # Corrigendum
                    "F14",
                    # Modification notice
                    "F20",
                ):
                    continue

                obj = form.xpath("./ns:OBJECT_CONTRACT", **kw)[0]
                cpv = obj.xpath("./ns:CPV_MAIN/ns:CPV_CODE/@CODE", **kw)[0]

                # https://docs.google.com/spreadsheets/d/1pmc_3oI_teOk7FMVyLK1bKt8d8o3SkvY_Faqth4PMqg/edit
                if cpv[:2] in ("09", "24", "33", "35", "38", "66", "71", "72", "77", "80", "85"):
                    continue

                common = {}

                common["MONTH"] = f"{year}-{month:02d}"
                common["FORM"] = number
                common["LG"] = form.xpath("./@LG", **kw)[0]

                urls = ted.xpath("./ns:CODED_DATA_SECTION/ns:NOTICE_DATA/ns:URI_LIST/ns:URI_DOC", **kw)
                common["URI_DOC"] = urls[0].text

                common["CPV2"] = cpv[:2]
                common["CPV3"] = cpv[:3]
                common["CPV4"] = cpv[:4]
                common["CPV5"] = cpv[:5]
                common["CPV_MAIN"] = cpv

                # LEFTI
                if lefti := form.xpath("./ns:LEFTI", **kw):
                    lefti = lefti[0]

                    for element in ("ECONOMIC_CRITERIA_DOC", "TECHNICAL_CRITERIA_DOC"):
                        common[element] = bool(lefti.xpath(f"./ns:{element}", **kw))
                    for element in (
                        "SUITABILITY",
                        "ECONOMIC_FINANCIAL_INFO",
                        "ECONOMIC_FINANCIAL_MIN_LEVEL",
                        "TECHNICAL_PROFESSIONAL_INFO",
                        "TECHNICAL_PROFESSIONAL_MIN_LEVEL",
                        "PERFORMANCE_CONDITIONS",
                    ):
                        p = lefti.xpath(f"./ns:{element}//text()", **kw)
                        common[f"{element}_ANY"] = bool(p)
                        if p:
                            common[element] = "\n\n".join(p)

                lots = obj.xpath("./ns:OBJECT_DESCR", **kw)
                assert len(lots), "/OBJECT_CONTRACT/OBJECT_DESCR is missing"
                for lot in lots:
                    row = common.copy()

                    row["CPV_ADDITIONAL"] = ";".join(
                        [
                            code
                            for cpv in lot.xpath("./ns:CPV_ADDITIONAL", **kw)
                            for code in cpv.xpath("./ns:CPV_CODE/@CODE", **kw)
                            if code != common["CPV_MAIN"]
                        ]
                    )

                    if ac := lot.xpath("./ns:AC", **kw):
                        ac = ac[0]

                        row["AC_PROCUREMENT_DOC"] = bool(ac.xpath("./ns:AC_PROCUREMENT_DOC", **kw))
                        row["AC_PRICE"] = bool(ac.xpath("./ns:AC_PRICE", **kw))

                        for element in ("AC_QUALITY", "AC_COST"):
                            texts = [
                                c.xpath("./ns:AC_CRITERION/text()", **kw)[0] for c in ac.xpath(f"./ns:{element}", **kw)
                            ]
                            row[f"{element}_ANY"] = bool(texts)
                            if texts:
                                row[element] = texts

                    p = lot.xpath("./ns:CRITERIA_CANDIDATE//text()", **kw)
                    row["CRITERIA_CANDIDATE_ANY"] = bool(p)
                    if p:
                        row["CRITERIA_CANDIDATE"] = "\n\n".join(p)

                    writer.writerow(row)


@cli.command()
@click.argument("file", type=click.File())
@click.argument("requirements", type=click.File())
def search(file, requirements):
    """
    Calculate which rows of a CSV file match green requirements.
    """
    # https://huggingface.co/models?pipeline_tag=sentence-similarity&sort=trending&search=multilingual
    # intfloat/multilingual-e5-* don't perform well. Use sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 or
    # sentence-transformers/paraphrase-multilingual-mpnet-base-v2.
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    t = time.time()

    queries = requirements.read().splitlines()
    corpus = file.read().splitlines()

    query_embeddings = model.encode(queries, convert_to_tensor=True, normalize_embeddings=True)
    corpus_embeddings = model.encode(corpus, convert_to_tensor=True, normalize_embeddings=True)

    reponses = util.semantic_search(
        query_embeddings,
        corpus_embeddings,
        top_k=min(5, len(corpus)),
        score_function=util.dot_score,
        # 100 queries in parallel. Increase these to increase speed (requiring more memory).
        query_chunk_size=100,
        corpus_chunk_size=500000,
    )
    for i, reponse in enumerate(reponses):
        click.echo(f"\nQ: {queries[i]}")
        for hit in reponse:
            click.echo(f"{hit['score']:.4f} {corpus[hit['corpus_id']]}")

    click.echo(f"{time.time() - t:.2f}s")


if __name__ == "__main__":
    cli()
