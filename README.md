# SrumMonkey
**SrumMonkey** is a tool you can use to convert the Microsoft SRU edb database to a SQLite database. Further, you can create report templates to generate XLSX reports based off of YAML templates.

The *xlsx_templates* directory contains YAML templates that are used to create the XLSX reports.

## Usage
SrumMonkey has two sub-commands. One for processing, and the other for re-generating reports:
```
usage: SrumMonkey.py [-h] [--template_folder TEMPLATE_FOLDER]
                     {process,report} ...

SrumMonkey v1.0.0 - Copywrite G-C Partners, LLC

SrumMonkey is a tool you can use to convert the Microsoft SRU edb database to a SQLite database.
Further, you can create report templates to generate XLSX reports based off of YAML templates.

positional arguments:
  {process,report}      Either process or report command is required.
    process             Processes SRUM and generate reports.
    report              Generate reports from an existing SrumMonkey database.

optional arguments:
  -h, --help            show this help message and exit
  --template_folder TEMPLATE_FOLDER
                        Folder that contains YML templates.
```

If you are using the python script, it will look for the xlsx_templates folder by default in the cwd. If you are making your own templates or wish to add templates you can create your own template folder and pass it in via the `--template_folder` parameter. If you are using the compiled version, it is packed with the xml templates and will unpack them at execution to use by default. Both the report and process sub commands use the `--template_folder` parameter.

### Process
There are two artifacts that SrumMonkey needs to parse the SRU database. The SRU database itself, and the Software Hive. The information pulled out of the Software hive allows us to enumerate the names of the tables in the SRU database (otherwise they would just be GUID strings). In addition we can also use the Software hive to enumerate the network interface ids so that you can see the network names of wireless connections.

```
usage: SrumMonkey.py process [-h] --srum_db SRUM_DB --software_hive
                             SOFTWARE_HIVE --outpath OUTPATH [--no_reports]

optional arguments:
  -h, --help            show this help message and exit
  --srum_db SRUM_DB     SRUM Database
  --software_hive SOFTWARE_HIVE
                        SOFTWARE Hive
  --outpath OUTPATH     Output path where you want your reports and db
  --no_reports          Do not run reports (Parsing/Database creation only)
```

### Report
If you are wanting to create new templates and don't want to reparse the data set, you can use the `report` sub-command. Just tell it where to find the converted SRU sqlite database, and give it the outpath where you want the new reports.

```
usage: SrumMonkey.py report [-h] --database DATABASE --outpath OUTPATH

optional arguments:
  -h, --help           show this help message and exit
  --database DATABASE  Database to run reports on
  --outpath OUTPATH    Output Path.
```

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
