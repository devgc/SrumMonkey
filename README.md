# SrumMonkey
**SrumMonkey** is a tool you can use to convert the Microsoft SRU edb database to a SQLite database. Further, you can create report templates to generate XLSX reports based off of YAML templates.

**SrumMonkey.py** will use *CustomSqlFunctions.py* to create custom SQLite Functions that you can call from the YAML template SQL query.

The *xlsx_templates* directory contains YAML templates that are used to create the XLSX reports.

## YAML Templates
SrumMonkey now uses the GcHelpers library.

See [https://github.com/devgc/GcHelpers/wiki/XLSX-Templates](https://github.com/devgc/GcHelpers/wiki/XLSX-Templates) for documentation on creating YAML templates for XLSX report generation.

See [https://github.com/devgc/SrumMonkey/tree/master/xlsx_templates](https://github.com/devgc/SrumMonkey/tree/master/xlsx_templates) for example templates.

## Dependencies that are not installed with setup.py
- libesedb
  - Git</br> 
  https://github.com/libyal/libesedb
  - Binary Python Binding</br> 
  https://github.com/log2timeline/l2tbinaries
- PyYAML
  - Get the compiled binaries</br>
  http://pyyaml.org/wiki/PyYAML
