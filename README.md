# Green Cure

## Installation

```shell
pip install -r requirements.txt
```

## Usage

```shell
./manage.py --help
```

Download data, for example:

```shell
./manage.py download 2022 01 2022 12
```

Transform TED XML data to CSV, for example:

```shell
./manage.py xml-to-csv 2022 01 2022 12 2022.csv
```

Extract sentences from CSV, for example:

```shell
./manage.py csv-to-corpus 2022.csv corpus.csv
```

Perform a semantic similarity search, for example:

```shell
./manage.py search corpus.csv queries.csv 391
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
| SUITABILITY | Suitability to pursue the professional activity, including requirements relating to enrolment on professional or trade registers | | paragraphs | |
| ECONOMIC_CRITERIA_DOC | Whether the notice defers to procurement documents for economic criteria | | boolean | |
| ECONOMIC_FINANCIAL_INFO_ANY | Whether `ECONOMIC_FINANCIAL_INFO_ANY` is set | | boolean | |
| ECONOMIC_FINANCIAL_INFO | List and brief description of economic selection criteria | | paragraphs | |
| ECONOMIC_FINANCIAL_MIN_LEVEL_ANY | Whether `ECONOMIC_FINANCIAL_MIN_LEVEL_ANY` is set | | boolean | |
| ECONOMIC_FINANCIAL_MIN_LEVEL | Minimum level(s) of economic standards possibly required | | paragraphs | |
| TECHNICAL_CRITERIA_DOC | Whether the notice defers to procurement documents for technical criteria | | boolean | |
| TECHNICAL_PROFESSIONAL_INFO_ANY | Whether `TECHNICAL_PROFESSIONAL_INFO_ANY` is set | | boolean | |
| TECHNICAL_PROFESSIONAL_INFO | List and brief description of technical selection criteria | | paragraphs | |
| TECHNICAL_PROFESSIONAL_MIN_LEVEL_ANY | Whether `TECHNICAL_PROFESSIONAL_MIN_LEVEL_ANY` is set | | boolean | |
| TECHNICAL_PROFESSIONAL_MIN_LEVEL | Minimum level(s) of technical standards possibly required | | paragraphs | |
| PERFORMANCE_CONDITIONS_ANY | Whether `PERFORMANCE_CONDITIONS_ANY` is set | | boolean | |
| PERFORMANCE_CONDITIONS | Contract performance conditions | | paragraphs | |
| CPV_ADDITIONAL | Additional CPV code(s) | | codelist, colon-separated | |
| AC_PROCUREMENT_DOC | Whether non-price criteria are stated only in procurement documents | | boolean | |
| AC_PRICE | Whether price is a criterion | | boolean | |
| AC_QUALITY_ANY | Whether `AC_QUALITY_ANY` is set | | boolean | |
| AC_QUALITY | The names of the quality criteria | | Python list | |
| AC_COST_ANY | Whether `AC_COST_ANY` is set | | boolean | |
| AC_COST | The names of the cost criteria | | Python list | |
| CRITERIA_CANDIDATE_ANY | Whether `CRITERIA_CANDIDATE_ANY` is set | ✓ | boolean | |
| CRITERIA_CANDIDATE | Objective criteria for choosing the limited number of candidates | | paragraphs | |

## Future possibilities

- Train new model
- Use GPU acceleration (CUDA)
