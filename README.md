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
./manage.py transform 2022 01 2022 12 2022.csv
```

Perform a semantic similarity search:

```shell
./manage.py search 2022.csv queries.csv
```

## Exploration

[Install qsv](https://github.com/jqnatividad/qsv#installation-options).

Check the frequencies of values in columns using codelists:

```shell
qsv index 2022.csv
qsv frequency -l 0 -s MONTH,FORM,LG,CPV2,CPV3,CPV4,CPV5,ECONOMIC_CRITERIA_DOC,TECHNICAL_CRITERIA_DOC,AC_PROCUREMENT_DOC,AC_PRICE,SUITABILITY_ANY,ECONOMIC_FINANCIAL_INFO_ANY,ECONOMIC_FINANCIAL_MIN_LEVEL_ANY,TECHNICAL_PROFESSIONAL_INFO_ANY,TECHNICAL_PROFESSIONAL_MIN_LEVEL_ANY,PERFORMANCE_CONDITIONS_ANY,AC_QUALITY_ANY,AC_COST_ANY,CRITERIA_CANDIDATE_ANY 2022.csv | sort
```

## Future possibilities

- Train new model
- Use GPU acceleration (CUDA)
