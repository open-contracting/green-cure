#!/usr/bin/env python
import ast
import csv
import datetime
import functools
import os
import pickle
import shutil
import subprocess
import tarfile
import time
from contextlib import closing, contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import click
import nltk
import tabulate
from lxml import etree
from nltk import tokenize
from sentence_transformers import SentenceTransformer, util

SENTENCE_MINLENGTH = 10

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


@contextmanager
def timed(message):
    start = time.time()
    click.echo(f"{message}... ", nl=False)
    yield
    click.echo(f"{time.time() - start:.2f}s")


@cli.command()
@click.argument("startyear", type=click.IntRange(2015, now.year))
@click.argument("startmonth", type=click.IntRange(1, 12))
@click.argument("endyear", type=click.IntRange(2015, now.year))
@click.argument("endmonth", type=click.IntRange(1, 12))
def download(startyear, startmonth, endyear, endmonth):
    """
    Write monthly packages from Tenders Electronic Daily to a data/ directory.
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
def xml2csv(startyear, startmonth, endyear, endmonth, file):
    """
    Transform monthly packages in the data/ directory to a CSV file.
    """
    kw = {"namespaces": {"ns": "http://publications.europa.eu/resource/schema/ted/R2.0.9/publication"}}

    writer = csv.DictWriter(
        file,
        [
            "MONTH",
            "FORM",
            "LG",
            "URI_DOC",
            "URL_DOCUMENT_ANY",
            "URL_DOCUMENT",
            "CPV2",
            "CPV3",
            "CPV4",
            "CPV5",
            "CPV_MAIN",
            "SUITABILITY_ANY",
            "SUITABILITY",
            "ECONOMIC_CRITERIA_DOC",
            "ECONOMIC_FINANCIAL_INFO_ANY",
            "ECONOMIC_FINANCIAL_INFO",
            "ECONOMIC_FINANCIAL_MIN_LEVEL_ANY",
            "ECONOMIC_FINANCIAL_MIN_LEVEL",
            "TECHNICAL_CRITERIA_DOC",
            "TECHNICAL_PROFESSIONAL_INFO_ANY",
            "TECHNICAL_PROFESSIONAL_INFO",
            "TECHNICAL_PROFESSIONAL_MIN_LEVEL_ANY",
            "TECHNICAL_PROFESSIONAL_MIN_LEVEL",
            "PERFORMANCE_CONDITIONS_ANY",
            "PERFORMANCE_CONDITIONS",
            "CPV_ADDITIONAL",
            "AC_PROCUREMENT_DOC",
            "AC_PRICE",
            "AC_QUALITY_ANY",
            "AC_QUALITY",
            "AC_COST_ANY",
            "AC_COST",
            "CRITERIA_CANDIDATE_ANY",
            "CRITERIA_CANDIDATE",
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

                url_document = form.xpath("./ns:CONTRACTING_BODY/ns:URL_DOCUMENT/text()", **kw)
                common["URL_DOCUMENT_ANY"] = bool(url_document)
                if url_document:
                    common["URL_DOCUMENT"] = url_document

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
                            common[element] = p

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
                        row["CRITERIA_CANDIDATE"] = p

                    writer.writerow(row)


@cli.command()
@click.argument("infile", type=click.File())
@click.argument("outfile", type=click.File("w"))
@click.argument("cpv")
def csv2corpus(infile, outfile, cpv):
    """
    Extract sentences from the rows of a CSV file that match the CPV code, one line per sentence.
    """
    languages = {
        # ls ~/nltk_data/tokenizers/punkt/*.pickle
        # Also covers "malayalam", but conflicts with "ML" for "maltese".
        # Germanic
        "DA": "danish",
        "NL": "dutch",
        "EN": "english",
        "DE": "german",
        "NO": "norwegian",
        "SV": "swedish",
        # Hellenic
        "EL": "greek",
        # Italic
        "FR": "french",
        "IT": "italian",
        "PT": "portuguese",
        "ES": "spanish",
        # Slavic
        "CS": "czech",
        "PL": "polish",
        "RU": "russian",
        "SL": "slovene",
        # Uralic
        "ET": "estonian",
        "FI": "finnish",
        # Turkic
        "TR": "turkish",
        # Languages not supported by NLTK.
        # Baltic
        "LV": "slovene",  # latvian
        "LT": "slovene",  # lithuanian
        # Celtic
        "GA": "italian",  # irish
        # Italic
        "RO": "italian",  # romanian
        # Semitic
        "ML": "spanish",  # maltese, should be "MT"
        # Slavic
        "BG": "slovene",  # bulgarian
        "HR": "slovene",  # croatian
        "SK": "czech",  # slovak
        # Uralic
        "HU": "finnish",  # hungarian
    }

    nltk.download("punkt")

    columns = {
        "SUITABILITY": 0,
        "ECONOMIC_FINANCIAL_INFO": 0,
        "ECONOMIC_FINANCIAL_MIN_LEVEL": 0,
        "TECHNICAL_PROFESSIONAL_INFO": 0,
        "TECHNICAL_PROFESSIONAL_MIN_LEVEL": 0,
        "PERFORMANCE_CONDITIONS": 0,
        "CRITERIA_CANDIDATE": 0,
        "AC_QUALITY": 0,
        "AC_COST": 0,
    }

    reader = csv.DictReader(infile)
    cpv_key = f"CPV{len(cpv)}"
    sentences = set()
    matching = 0
    rowcount = 0

    with timed("Extracting"):
        for row in reader:
            if row[cpv_key] != cpv:
                continue
            matching += 1

            if not any(row[f"{column}_ANY"] == "True" for column in columns):
                continue
            rowcount += 1

            language = languages[row["LG"]]

            for column in columns:
                if row[column]:
                    for text in ast.literal_eval(row[column]):
                        for sentence in tokenize.sent_tokenize(text, language=language):
                            if len(sentence) > SENTENCE_MINLENGTH:
                                sentences.add(sentence.replace("\n", " "))
                                columns[column] += 1

    for sentence in sentences:
        outfile.write(f"{sentence}\n")

    click.echo(
        f"{len(sentences):,d} unique sentences ({sum(columns.values()):,d} total sentences) "
        f"from {rowcount:,d} non-empty rows ({matching:,d} total rows) with CPV {cpv}",
        err=True,
    )
    click.echo(tabulate.tabulate(columns.items()))


@cli.command()
@click.argument("corpusfile", type=click.File())
@click.argument("queriesfile", type=click.File())
@click.argument("minscore", type=float)
def search(corpusfile, queriesfile, minscore):
    """
    Calculate which sentences match the queries.
    """

    @functools.cache
    def model():
        # intfloat/multilingual-e5-* don't perform well. Can also use paraphrase-multilingual-mpnet-base-v2.
        return SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    def cached(file):
        mtime = os.stat(file.name).st_mtime

        cache = Path(f"{file.name}.pickle")
        if cache.exists():
            with cache.open("rb") as f:
                cache_mtime, sentences, embeddings = pickle.load(f)
                if cache_mtime == mtime:
                    return sentences, embeddings

        sentences = file.read().splitlines()

        with timed(f"Encoding {len(sentences):,d} sentences from {file.name}"):
            embeddings = model().encode(sentences, convert_to_tensor=True, normalize_embeddings=True)
        with cache.open("wb") as f:
            pickle.dump([mtime, sentences, embeddings], f, protocol=pickle.HIGHEST_PROTOCOL)

        return sentences, embeddings

    queries, query_embeddings = cached(queriesfile)
    corpus, corpus_embeddings = cached(corpusfile)

    with timed("Searching"):
        responses = util.semantic_search(
            query_embeddings,
            corpus_embeddings,
            top_k=min(5, len(corpus)),
            score_function=util.dot_score,
            # 100 queries in parallel. Increase these to increase speed (requiring more memory).
            query_chunk_size=100,
            corpus_chunk_size=500000,
        )

    matches = 0
    for i, response in enumerate(responses):
        if response[0]["score"] >= minscore:
            matches += 1
            click.echo(f"\nQ: {queries[i]}")
            for hit in response:
                if hit["score"] >= minscore:
                    click.echo(f"{hit['score']:.4f} {corpus[hit['corpus_id']]}")
    click.echo(f"\n{matches}/{len(queries)} queries match with a score >= {minscore}")


@cli.command()
@click.argument("infile", type=click.Path(exists=True, dir_okay=False))
@click.argument("outfile", type=click.File("w"))
@click.argument("firstpage", type=int)
@click.argument("lastpage", type=int)
def pdf2queries(infile, outfile, firstpage, lastpage):
    if not shutil.which("pdftotext"):
        raise click.UsageError("pdftotext command is not available. Install Poppler: https://poppler.freedesktop.org")

    sentences = set()
    total = 0

    text = subprocess.check_output(
        ["pdftotext", "-f", str(firstpage), "-l", str(lastpage), "-nopgbrk", infile, "-"], text=True
    )
    for sentence in tokenize.sent_tokenize(text, language="english"):
        if len(sentence) > SENTENCE_MINLENGTH:
            sentences.add(sentence.replace("\n", " "))
            total += 1

    for sentence in sentences:
        outfile.write(f"{sentence}\n")

    click.echo(
        f"{len(sentences):,d} unique sentences ({total:,d} total sentences)",
        err=True,
    )


if __name__ == "__main__":
    cli()
