# SrumMonkey
**SrumMonkey** is a tool you can use to convert the Microsoft SRU edb database to a SQLite database. Further, you can create report templates to generate XLSX reports based off of YAML templates.

**SrumMonkey.py** will use *CustomSqlFunctions.py* to create custom SQLite Functions that you can call from the YAML template SQL query.

The *xlsx_templates* directory contains YAML templates that are used to create the XLSX reports.

## Needed Libraries
- pythone-registry
  - Git - https://github.com/williballenthin/python-registry
- libesedb
  - Git - https://github.com/libyal/libesedb
  - Binary Python Binding - https://github.com/log2timeline/l2tbinaries
- PyYAML
  - Get the compiled binaries - http://pyyaml.org/wiki/PyYAML
- xlsxwriter
  - Git - https://github.com/jmcnamara/XlsxWriter
