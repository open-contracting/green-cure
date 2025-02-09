#!/usr/bin/env python
import ast
import csv
import datetime
import functools
import json
import os
import pickle
import re
import shutil
import subprocess
import tarfile
import time
from collections import defaultdict
from contextlib import closing, contextmanager
from operator import itemgetter
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import click
import nltk
import pdf2image
import pypandoc
import requests
import tabulate
from bs4 import BeautifulSoup
from lxml import etree
from nltk import tokenize
from pytesseract import pytesseract
from sentence_transformers import SentenceTransformer, util

SENTENCE_MINLENGTH = 10
WHITESPACE = re.compile(r"\s+")

now = datetime.datetime.now(tz=datetime.UTC)
basedir = Path(__file__).resolve().parent
datadir = basedir / "data"


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


def raise_if_pdftotext_not_present():
    if not shutil.which("pdftotext"):
        raise click.UsageError("pdftotext command is not available. Install Poppler: https://poppler.freedesktop.org")


def sentence_generator(text, language):
    for sentence in tokenize.sent_tokenize(text, language=language):
        stripped = WHITESPACE.sub(sentence, " ").strip()
        if len(stripped) > SENTENCE_MINLENGTH:
            yield stripped


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
def download_ted(startyear, startmonth, endyear, endmonth):
    """Write monthly packages from Tenders Electronic Daily to a data/ directory."""
    datadir.mkdir(exist_ok=True)

    for year, month in yearmonths(startyear, startmonth, endyear, endmonth):
        path = datadir / f"{year}-{month:02d}.tar.gz"
        if path.exists():
            click.echo(f"{path.name} exists")
            continue

        url = f"ftp://guest:guest@ted.europa.eu/monthly-packages/{year}/{year}-{month:02d}.tar.gz"
        click.echo(f"Retrieving {url} ...")
        try:
            with closing(urlopen(url)) as r, path.open("wb") as f:  # noqa: S310 # false positive
                shutil.copyfileobj(r, f)
        except URLError as e:
            click.echo(e.reason, err=True)


@cli.command()
@click.argument("startyear", type=click.IntRange(2015, now.year))
@click.argument("startmonth", type=click.IntRange(1, 12))
@click.argument("endyear", type=click.IntRange(2015, now.year))
@click.argument("endmonth", type=click.IntRange(1, 12))
@click.argument("file", type=click.File("w"))
@click.argument("cpv", nargs=-1)
def xml2csv(startyear, startmonth, endyear, endmonth, file, cpv):
    """Transform monthly packages in the data/ directory to a CSV file."""
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
        path = datadir / f"{year}-{month:02d}.tar.gz"
        if not path.exists():
            click.echo(f"{path.name} doesn't exist, skipping...", err=True)
            continue

        with tarfile.open(path, "r:gz") as tar:
            while member := tar.next():
                if member.isdir():
                    continue

                doc = etree.fromstring(tar.extractfile(member).read())  # noqa: S320 # trusted internal
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
                if number in {
                    # Contract award notice
                    "F03",
                    "F06",
                    # Corrigendum
                    "F14",
                    # Modification notice
                    "F20",
                }:
                    continue

                obj = form.xpath("./ns:OBJECT_CONTRACT", **kw)[0]
                code = obj.xpath("./ns:CPV_MAIN/ns:CPV_CODE/@CODE", **kw)[0]

                # https://docs.google.com/spreadsheets/d/1pmc_3oI_teOk7FMVyLK1bKt8d8o3SkvY_Faqth4PMqg/edit
                if code[:2] in {"09", "24", "33", "35", "38", "66", "71", "72", "77", "80", "85"}:
                    continue

                common = {}

                common["CPV2"] = code[:2]
                common["CPV3"] = code[:3]
                common["CPV4"] = code[:4]
                common["CPV5"] = code[:5]
                common["CPV_MAIN"] = code

                if cpv and not any(
                    common[f"CPV{len(code)}"] == code if len(code) <= 5 else common["CPV_MAIN"] == code for code in cpv
                ):
                    continue

                common["MONTH"] = f"{year}-{month:02d}"
                common["FORM"] = number
                common["LG"] = form.xpath("./@LG", **kw)[0]

                urls = ted.xpath("./ns:CODED_DATA_SECTION/ns:NOTICE_DATA/ns:URI_LIST/ns:URI_DOC", **kw)
                common["URI_DOC"] = urls[0].text

                url_document = form.xpath("./ns:CONTRACTING_BODY/ns:URL_DOCUMENT/text()", **kw)
                common["URL_DOCUMENT_ANY"] = bool(url_document)
                if url_document:
                    common["URL_DOCUMENT"] = url_document

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
                if not lots:
                    raise AssertionError("/OBJECT_CONTRACT/OBJECT_DESCR is missing")
                for lot in lots:
                    row = common.copy()

                    row["CPV_ADDITIONAL"] = ";".join(
                        [
                            code
                            for cpv_additional in lot.xpath("./ns:CPV_ADDITIONAL", **kw)
                            for code in cpv_additional.xpath("./ns:CPV_CODE/@CODE", **kw)
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
@click.argument("cpv", nargs=-1)
def csv2corpus(infile, outfile, cpv):
    """Extract sentences from the rows of a CSV file that match the CPV code(s), one line per sentence."""
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
    sentences = set()
    matching = 0
    rowcount = 0

    with timed("Extracting"):
        for row in reader:
            if not any(row[f"CPV{len(code)}"] == code if len(code) <= 5 else row["CPV_MAIN"] == code for code in cpv):
                continue
            matching += 1

            if not any(row[f"{column}_ANY"] == "True" for column in columns):
                continue
            rowcount += 1

            language = languages[row["LG"]]

            for column in columns:
                if row[column]:
                    for text in ast.literal_eval(row[column]):
                        for sentence in sentence_generator(text, language):
                            sentences.add(sentence)
                            columns[column] += 1

    for sentence in sentences:
        outfile.write(f"{sentence}\n")

    click.echo(
        f"{len(sentences):,d} unique sentences ({sum(columns.values()):,d} total sentences) "
        f"from {rowcount:,d} non-empty rows ({matching:,d} total rows) with CPV {' '.join(cpv)}",
        err=True,
    )
    click.echo(tabulate.tabulate(columns.items()))


@cli.command()
@click.argument("corpusfile", type=click.File())
@click.argument("queriesfile", type=click.File())
@click.argument("minscore", type=float)
def search(corpusfile, queriesfile, minscore):
    """Calculate which sentences match the queries."""

    @functools.cache
    def model():
        # intfloat/multilingual-e5-* don't perform well. Can also use paraphrase-multilingual-mpnet-base-v2.
        return SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    def cached(file):
        mtime = file.stat().st_mtime

        cache = Path(f"{file.name}.pickle")
        if cache.exists():
            with cache.open("rb") as f:
                cache_mtime, sentences, embeddings = pickle.load(f)  # noqa: S301 # our data
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

    remove = re.compile(r"[•]\s*")

    matches = 0
    for i, response in enumerate(responses):
        if response[0]["score"] >= minscore:
            matches += 1
            click.echo(f"\nQ: {queries[i]}")
            for hit in response:
                if hit["score"] >= minscore:
                    click.echo(f"{hit['score']:.4f} {WHITESPACE.sub(' ', remove.sub('', corpus[hit['corpus_id']]))}")
    click.echo(f"\n{matches}/{len(queries)} queries match with a score >= {minscore}")


@cli.command()
@click.argument("infile", type=click.Path(exists=True, dir_okay=False))
@click.argument("outfile", type=click.File("w"))
@click.argument("firstpage", type=int)
@click.argument("lastpage", type=int)
def pdf2queries(infile, outfile, firstpage, lastpage):
    """Extract sentences from a page range in a PDF file."""
    raise_if_pdftotext_not_present()

    sentences = set()
    total = 0

    text = subprocess.check_output(  # noqa: S603: trusted input
        ["pdftotext", "-nopgbrk", "-f", str(firstpage), "-l", str(lastpage), infile, "-"],  # noqa: S607
        text=True,
    )
    for sentence in sentence_generator(text, "english"):
        sentences.add(sentence)
        total += 1

    for sentence in sentences:
        outfile.write(f"{sentence}\n")

    click.echo(
        f"{len(sentences):,d} unique sentences ({total:,d} total sentences)",
        err=True,
    )


@cli.command()
@click.argument("outdir", type=click.Path(exists=False, file_okay=False, path_type=Path))
def download_do(outdir):
    """Write "Especificaciones/Ficha Técnica" files from comprasverdes.gob.do."""
    with (basedir / "assets" / "do_post.json").open() as f:
        post_data = json.load(f)

    response = requests.post(
        "https://wabi-us-east-a-primary-api.analysis.windows.net/public/reports/querydata?synchronous=true",
        # This request data is copied from the web browser.
        json=post_data,
        # The other headers from the web browser are not required.
        headers={"X-PowerBI-ResourceKey": "6d07fc9a-46df-4b72-9509-ea5c80c85178"},
        timeout=10,
    )
    response.raise_for_status()

    """
    Responses look like:

    {
        "jobIds": ["UUID"],
        "results": [
            {
                "jobId": "UUID",
                "result": {
                    "data": {
                        "timestamp": "2023-10-10T18:22:39.397Z",
                        "rootActivityId": "UUID",
                        "descriptor": {...},
                        "metrics": {...}, // start times, end times, row counts for operations
                        "fromCache": false,
                        "dsr": {
                            "Version": 2,
                            "MinorVersion": 1,
                            "DS": [
                                {
                                    "N": "DS0",
                                    "PH": [
                                        {
                                            "DM0": [
                                                {
                                                    "S": [...],
                                                    "C": [...]
                                                },
                                                {
                                                    "C": [
                                                        // a row of values
                                                    ],
                                                    "R": 123
                                                },
                                                ...
                                            ]
                                        }
                                    ],
                                    "IC": true,
                                    "HAD": true,
                                    "ValueDicts": {
                                        "D0": [
                                            "...",
                                            ...
                                        ],
                                        ...
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        ]
    }
    """
    urls = set(response.json()["results"][0]["result"]["data"]["dsr"]["DS"][0]["ValueDicts"]["D9"])
    entries = response.json()["results"][0]["result"]["data"]["dsr"]["DS"][0]["PH"][0]["DM0"]
    urls.update(value for entry in entries for value in entry["C"] if str(value).startswith("http"))

    base_url = "https://comunidad.comprasdominicana.gob.do"
    pattern = re.compile(r"documentFileId=(\d+)")
    outdir.mkdir(parents=True, exist_ok=True)
    documents = []
    no_documents_found = []
    document_types_skipped = defaultdict(int)

    with timed(f"Downloading {len(urls)} URLs"):
        for url in urls:
            # Accept-Language must be set for document types to appear correctly (English is often empty).
            #
            # /Public/Tendering/OpportunityDetail/Index?noticeUID=DO1.NTC.1305239
            response = requests.get(url, headers={"Accept-Language": "es"}, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            tender_id = soup.find(id="fdsRequestSummaryInfo_tblDetail_trRowRef_tdCell2_spnRequestReference").text
            tender_title = soup.find(id="fdsRequestSummaryInfo_tblDetail_trRowName_tdCell2_spnRequestName").text

            click.echo(".", nl=False)
            found = False

            for row in soup.find(id="grdGridDocumentList_tbl").find_all("tr"):
                if row.find("th"):
                    continue

                document_name = row.find("td", id="grdGridDocumentListtd_thColumnDocumentName").text
                document_type = row.find("td", id="grdGridDocumentListtd_thColumnDocumentType").text
                document_url = (
                    row.find("td", id="grdGridDocumentListtd_thColumnDownloadDocument")
                    .find("a")["onclick"]
                    .replace("javascript:getAction('", "")
                    .replace("',true);", "")
                    .replace("' + '", "")
                )

                if document_type != "Especificaciones/Ficha Técnica":
                    document_types_skipped[document_type] += 1
                    continue

                document_id = pattern.search(document_url).group(1)
                document_path = outdir / f"{tender_id}+{document_id}{Path(document_name).suffix.lower()}"

                documents.append(
                    {
                        "id": tender_id,
                        "title": tender_title,
                        "document_id": document_id,
                        "document_name": document_name,
                        "document_type": document_type,
                        "document_url": document_url,
                        "url": url,
                    }
                )

                found = True
                if document_path.exists():
                    continue
                click.echo("↓", nl=False)

                # /Public/Tendering/OpportunityDetail/DownloadFile?documentFileId=7364440
                # &mkey=554f0311_b812_4cd7_babe_ed25a7a17272
                response = requests.get(f"{base_url}{document_url}", timeout=10)
                response.raise_for_status()

                # Responses look like:
                #
                # <script language="javascript">window.location.href = '/Public/Archive/RetrieveFile/Index
                # ?DocumentId=7585910&InCommunity=False&InPaymentGateway=False&DocUniqueIdentifier='</script>
                soup = BeautifulSoup(response.content, "html.parser")
                pdf_url = soup.find("script").text.replace("window.location.href = ", "").replace("'", "")

                # /Public/Archive/RetrieveFile/Index?DocumentId=7585910&InCommunity=False
                # &InPaymentGateway=False&DocUniqueIdentifier=
                response = requests.get(f"{base_url}{pdf_url}", timeout=10)
                response.raise_for_status()

                with document_path.open("wb") as f:
                    f.write(response.content)

            if not found:
                no_documents_found.append(url)
                click.echo("☒", nl=False)

    path = outdir / "documents.csv"
    click.secho(f"Writing {len(documents)} rows to {path}...", fg="green")
    with path.open("w") as f:
        fieldnames = ["id", "title", "document_id", "document_name", "document_type", "document_url", "url"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(documents)

    # As of 2023-10-26:
    #
    # 341 Otro
    # 168 Solicitud Compra o Contratación
    #  49 Copia de los Estatutos
    #  45 Certificado de Apropiación Presupuestaria
    #  37
    #  23 Copia del Decreto designación Máxima Autoridad
    #  17 Pliego de Condiciones
    #  14 Formulario de Información sobre Oferente
    #  10 Oferta Económica (Cotización)
    #   5 Documentación legal que lo faculte a operar
    #   5 Formulario de Entrega de Muestras
    #   4 Dictámen Jurídico Pliego
    #   4 Ofertas económicas
    #   3 Acto Administrativo de Inicio de Procedimiento
    #   2 Credenciales
    #   2 Resolución del Comité de Compras y Contrataciones
    #   1 Acta simple de aperturas de ofertas
    #   1 Autorización del Fabricante
    #   1 Declaración Original Simple
    #   1 Documento de Tributación Fiscal (RNC/Cedula/Clave Tributaria País Extranjero/Pasaporte)
    #   1 Experiencia Contratista
    #   1 Informe pericial que justifique el uso de la excepción
    #   1 Ofertas técnicas
    #   1 Publicación en periódicos de circulación nacional
    click.secho(f"Skipped {len(document_types_skipped)} document types:", fg="yellow")
    for document_type, count in sorted(document_types_skipped.items(), reverse=True, key=itemgetter(1)):
        click.echo(f"{count:3d} {document_type}")

    click.secho(f"No documents found for {len(no_documents_found)} contracting processes:", fg="yellow")
    for url in no_documents_found:
        click.echo(url)


@cli.command()
@click.argument("indir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--skip-existing", is_flag=True)
def any2txt(indir, skip_existing):
    """Transform PDF, DOC, DOCX, BMP, PNG and JPEG to .txt files."""
    raise_if_pdftotext_not_present()

    for root, _, files in os.walk(indir):
        root_path = Path(root)
        for file in files:
            outfile = indir / f"{file}.txt"
            infile = root_path / file
            suffix = infile.suffix.lower()

            if suffix in {".csv", ".txt"}:
                continue
            if skip_existing and outfile.exists():
                click.echo(".", nl=False)
                continue
            click.echo(infile)

            if suffix == ".docx":
                text = pypandoc.convert_file(infile, "plain")
            elif suffix == (".bmp", ".jpeg", ".png"):
                text = pytesseract.image_to_string(infile)
            elif suffix == ".pdf":
                text = subprocess.check_output(  # noqa: S603: trusted input
                    ["pdftotext", "-nopgbrk", infile, "-"],  # noqa: S607
                    text=True,
                )
                if not text:
                    text = "\n".join(
                        pytesseract.image_to_string(i) for i in pdf2image.convert_from_path(infile, dpi=500)
                    )
            else:
                click.secho(f"Unsupported format ({suffix})", fg="yellow")
                continue

            if text:
                with outfile.open("w") as f:
                    f.write(text)


@cli.command()
@click.argument("indir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("outfile", type=click.File("w"))
@click.argument("language")
def txt2corpus(indir, outfile, language):
    """Extract sentences from .txt files in the input directory."""
    writer = csv.writer(outfile)
    for file in indir.glob("*.txt"):
        with file.open() as f:
            for sentence in sentence_generator(f.read(), language):
                writer.writerow([sentence])


if __name__ == "__main__":
    cli()
