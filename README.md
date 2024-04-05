# Green Cure

## Installation

```shell
pip install -r requirements.txt
```

Install [Popper](https://poppler.freedesktop.org) for its `pdftotext` command. For example, on macOS:

```shell
brew install poppler
```

Install [Pandoc](https://pandoc.org) to convert DOCX to text. For example, on macOS:

```shell
brew install pandoc
```

Install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) to convert PDF to text. For example, on macOS:

```shell
brew install tesseract
```

The commands automatically download:

- [Punkt Tokenizer Models](https://www.nltk.org/nltk_data/) from [NLTK](https://www.nltk.org), for sentence splitting
- [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) from [Hugging Face](https://huggingface.co/models?pipeline_tag=sentence-similarity&sort=trending&search=multilingual), for sentence similarity

## Usage

```shell
./manage.py --help
```

### Tenders Electronic Daily (TED)

Download data, for example:

```shell
./manage.py download-ted 2022 01 2022 12
```

Transform TED XML data to CSV, for example:

```shell
./manage.py xml2csv 2022 01 2022 12 2022.csv
```

Extract sentences from CSV, for example:

```shell
./manage.py csv2corpus 2022.csv corpus-furniture.csv 391
./manage.py csv2corpus 2022.csv corpus-textiles.csv 18 395 98311 98312 5083 5082 98313
./manage.py csv2corpus 2022.csv corpus-cleaning.csv 90911200 90919 98341130 98341110
```

Extract green requirements from [PDF documents](https://green-business.ec.europa.eu/green-public-procurement/gpp-criteria-and-requirements_en), for example:

```shell
./manage.py pdf2queries 'Criteria for Furniture.pdf' queries-furniture.csv 6 27
```

### Dominican Republic

Download data, for example:

```shell
./manage.py download-do data/do
```

### General

Transform DOCX, BMP, PNG, JPEG and PDF to text files:

```shell
./manage.py any2txt data/do
```

Extract sentences from text files:

```shell
./manage.py txt2corpus data/do corpus-do.csv spanish
```

Perform a semantic similarity search, for example:

```shell
./manage.py search corpus-furniture.csv queries-furniture.csv 0.7
```

## Exploration

[Install qsv.](https://github.com/jqnatividad/qsv#installation-options)

Check the frequencies of values in columns using codelists:

```shell
qsv index 2022.csv
qsv frequency -l 0 -s MONTH,FORM,LG,CPV2,CPV3,CPV4,CPV5,ECONOMIC_CRITERIA_DOC,TECHNICAL_CRITERIA_DOC,AC_PROCUREMENT_DOC,AC_PRICE,SUITABILITY_ANY,ECONOMIC_FINANCIAL_INFO_ANY,ECONOMIC_FINANCIAL_MIN_LEVEL_ANY,TECHNICAL_PROFESSIONAL_INFO_ANY,TECHNICAL_PROFESSIONAL_MIN_LEVEL_ANY,PERFORMANCE_CONDITIONS_ANY,AC_QUALITY_ANY,AC_COST_ANY,CRITERIA_CANDIDATE_ANY 2022.csv | sort
```

## Data dictionary

| Column | Description | Required | Format | Example |
| - | - | - | - | - |
| MONTH | The monthly package | ✓ | YYYY-MM | 2022-01 |
| FORM | The form number | ✓ | codelist | F02 |
| LG | The document language | ✓ | codelist | DE |
| URI_DOC | The notice URL | ✓ | URL | |
| URL_DOCUMENT_ANY | Whether `URI_DOCUMENT` is set | ✓ | boolean | |
| URI_DOCUMENT | The access URL for procurement documents | | URL | |
| CPV2 | The first 2 digits of `CPV_MAIN` | ✓ | codelist | 30 |
| CPV3 | The first 3 digits of `CPV_MAIN` | ✓ | codelist | 301 |
| CPV4 | The first 4 digits of `CPV_MAIN` | ✓ | codelist | 3019 |
| CPV5 | The first 5 digits of `CPV_MAIN` | ✓ | codelist | 30197 |
| CPV_MAIN | Main CPV code | ✓ | codelist | 30197630 |
| SUITABILITY_ANY | Whether `SUITABILITY` is set | | boolean | |
| SUITABILITY | Suitability to pursue the professional activity, including requirements relating to enrolment on professional or trade registers | | Python list | |
| ECONOMIC_CRITERIA_DOC | Whether the notice defers to procurement documents for economic criteria | | boolean | |
| ECONOMIC_FINANCIAL_INFO_ANY | Whether `ECONOMIC_FINANCIAL_INFO_ANY` is set | | boolean | |
| ECONOMIC_FINANCIAL_INFO | List and brief description of economic selection criteria | | Python list | |
| ECONOMIC_FINANCIAL_MIN_LEVEL_ANY | Whether `ECONOMIC_FINANCIAL_MIN_LEVEL_ANY` is set | | boolean | |
| ECONOMIC_FINANCIAL_MIN_LEVEL | Minimum level(s) of economic standards possibly required | | Python list | |
| TECHNICAL_CRITERIA_DOC | Whether the notice defers to procurement documents for technical criteria | | boolean | |
| TECHNICAL_PROFESSIONAL_INFO_ANY | Whether `TECHNICAL_PROFESSIONAL_INFO_ANY` is set | | boolean | |
| TECHNICAL_PROFESSIONAL_INFO | List and brief description of technical selection criteria | | Python list | |
| TECHNICAL_PROFESSIONAL_MIN_LEVEL_ANY | Whether `TECHNICAL_PROFESSIONAL_MIN_LEVEL_ANY` is set | | boolean | |
| TECHNICAL_PROFESSIONAL_MIN_LEVEL | Minimum level(s) of technical standards possibly required | | Python list | |
| PERFORMANCE_CONDITIONS_ANY | Whether `PERFORMANCE_CONDITIONS_ANY` is set | | boolean | |
| PERFORMANCE_CONDITIONS | Contract performance conditions | | Python list | |
| CPV_ADDITIONAL | Additional CPV code(s) | | codelist, colon-separated | |
| AC_PROCUREMENT_DOC | Whether non-price criteria are stated only in procurement documents | | boolean | |
| AC_PRICE | Whether price is a criterion | | boolean | |
| AC_QUALITY_ANY | Whether `AC_QUALITY_ANY` is set | | boolean | |
| AC_QUALITY | The names of the quality criteria | | Python list | |
| AC_COST_ANY | Whether `AC_COST_ANY` is set | | boolean | |
| AC_COST | The names of the cost criteria | | Python list | |
| CRITERIA_CANDIDATE_ANY | Whether `CRITERIA_CANDIDATE_ANY` is set | ✓ | boolean | |
| CRITERIA_CANDIDATE | Objective criteria for choosing the limited number of candidates | | Python list | |

## Future possibilities

- Train new model
- Use GPU acceleration (CUDA)
