#!/usr/bin/env python

# A tool to convert and analyze SRUM
#
# Copyright (C) 2015, G-C Partners, LLC <dev@g-cpartners.com>
# G-C Partners licenses this file to you under the Apache License, Version
# 2.0 (the "License"); you may not use this file except in compliance with the
# License.  You may obtain a copy of the License at:
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.
__VERSION__ = '1.0.0'
import sqlite3
import struct
import logging
import datetime
import sys
import os
import re
import argparse
import copy
import yaml
import pkg_resources
import multiprocessing

#From https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Multiprocessing
try:
    # Python 3.4+
    if sys.platform.startswith('win'):
        import multiprocessing.popen_spawn_win32 as forking
    else:
        import multiprocessing.popen_fork as forking
except ImportError:
    import multiprocessing.forking as forking

if sys.platform.startswith('win'):
    # First define a modified version of Popen.
    class _Popen(forking.Popen):
        def __init__(self, *args, **kw):
            if hasattr(sys, 'frozen'):
                # We have to set original _MEIPASS2 value from sys._MEIPASS
                # to get --onefile mode working.
                os.putenv('_MEIPASS2', sys._MEIPASS)
            try:
                super(_Popen, self).__init__(*args, **kw)
            finally:
                if hasattr(sys, 'frozen'):
                    # On some platforms (e.g. AIX) 'os.unsetenv()' is not
                    # available. In those cases we cannot delete the variable
                    # but only set it to the empty string. The bootloader
                    # can handle this case.
                    if hasattr(os, 'unsetenv'):
                        os.unsetenv('_MEIPASS2')
                    else:
                        os.putenv('_MEIPASS2', '')

    # Second override 'Popen' class with our modified version.
    forking.Popen = _Popen

from gchelpers.writers import XlsxHandler
from gchelpers.db.DbHandler import DbConfig as GcHelperDbConfig

logging.basicConfig(
    level = logging.DEBUG
)

#Requires Metz' libesedb
#https://github.com/libyal/libesedb
#or you can find compiled python bindings for MacOSX and Window versions at
#https://github.com/log2timeline/l2tbinaries
from pyesedb import column_types as DBTYPES
import pyesedb

#Requires installing python-registry
#https://github.com/williballenthin/python-registry
from Registry import Registry

def GetOptions():
    '''Get needed options for processesing'''
    
    usage = """SrumMonkey v{} - Copywrite G-C Partners, LLC

SrumMonkey is a tool you can use to convert the Microsoft SRU edb database to a SQLite database.
Further, you can create report templates to generate XLSX reports based off of YAML templates.""".format(__VERSION__)
    
    options = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(usage)
    )
    
    ###Case Details###
    options.add_argument(
        '--srum_db',
        dest='srum_db',
        action="store",
        type=unicode,
        default=None,
        help='SRUM Database'
    )
    
    options.add_argument(
        '--outpath',
        dest='outpath',
        required=True,
        action="store",
        type=unicode,
        default=None,
        help='Output path where you want your reports and db'
    )
    
    options.add_argument(
        '--software_hive',
        dest='software_hive',
        action="store",
        required=True,
        type=unicode,
        # default=None,
        help='SOFTWARE Hive for Interface Enumeration'
    )
    
    options.add_argument(
        '--template_folder',
        dest='template_folder',
        action="store",
        default=None,
        type=unicode,
        help='Folder that contains YML templates.'
    )
    
    options.add_argument(
        '--no_reports',
        dest='report_flag',
        action="store_false",
        default=True,
        help='Do not run reports (Parsing/Database creation only)'
    )
    
    return options

def Main():
    ###GET OPTIONS###
    arguements = GetOptions()
    options = arguements.parse_args()
    
    if not os.path.isdir(options.outpath):
        os.makedirs(options.outpath)
        
    options.output_db = os.path.join(options.outpath,'SRUM.db')
    
    #If Database exists, delete it#
    if os.path.isfile(options.output_db):
        os.remove(options.output_db)
    
    guid_table = None
    
    #Enumerate Registry Here#
    rhandler = RegistryHandler(
        options
    )
    rhandler.EnumerateRegistryValues()
    guid_table = rhandler.GetGuidTable()
    
    # if not options.reports_only_flag:
    srumHandler = SrumHandler(
        options,
        guid_table=guid_table
    )
    
    srumHandler.ConvertDb()
    
    if options.report_flag is True:
        db_config = GcHelperDbConfig(
            db_type='sqlite',
            db=options.output_db
        )
        
        # If no template folder was supplied, check source for default templates
        template_folder = options.template_folder
        if not template_folder:
            if getattr(sys,'frozen',False):
                location = os.path.join(sys._MEIPASS,'xlsx_templates')
                location = os.path.join(location,'')
                location = os.path.abspath(location)
            else:
                location = os.path.abspath(
                    pkg_resources.resource_filename(
                        'xlsx_templates',
                        ''
                    )
                )
            template_folder = location
            
        temp_manager = XlsxHandler.XlsxTemplateManager(
            template_folder
        )
        temp_manager.CreateReports(
            db_config,
            options.outpath
        )
    
class RegistryHandler():
    '''Registry Operations'''
    WLANSVCINTERFACEPROFILES_COLUMN_MAPPING = {
        'ProfileIndex':'INTEGER',
        'succeeded':'BLOB',
        'ProfileGuid':'TEXT',
        'Flags':'INTEGER',
        'All User Profile Security Descriptor':'TEXT',
        'CreatorSid':'BLOB',
        'InterfaceGuid':'TEXT',
        'SSID':'TEXT',
        'Nla':'BLOB',
        'NameLength':'INTEGER',
        'Name':'TEXT'
    }
    WLANSVCINTERFACEPROFILES_COLUMN_ORDER = [
        'ProfileIndex',
        'succeeded',
        'ProfileGuid',
        'Flags',
        'All User Profile Security Descriptor',
        'CreatorSid',
        'InterfaceGuid',
        'SSID',
        'Nla',
        'NameLength',
        'Name'
    ]
    
    CUSTOM_COLUMNS = {
        'All User Profile Security Descriptor':{
            'type':'utf-16le'
        },
        'Channel Hints':{
            'type':'ChannelHints'
        }
    }
    SQLITE_TYPE = {
        'DATETIME':[
            
        ],
        'REAL':[
            
        ],
        'INTEGER':[
            Registry.RegDWord
        ],
        'BLOB':[
        ],
        'TEXT':[
        ]
    }
    
    def __init__(self,options):
        self.options = options
        self.guid_mapping = None
        self.outputDbConfig = DbConfig(
            dbname=options.output_db
        )
        self.outputDbHandler = DbHandler(
            self.outputDbConfig
        )
        
    def _GetWlanSvcKeys(self):
        '''Insert wireless interface info into database'''
        try:
            reg_key = self.registry.open('Microsoft\\WlanSvc\\Interfaces')
        except Registry.RegistryKeyNotFoundException as error:
            print(u'No WlanSvc found at Microsoft\\WlanSvc\\Interfaces')
            return False
        
        profile_list = []
        for interface_key in reg_key.subkeys():
            #Get Interface GUID#
            interface_guid = interface_key.name()
            #If Interface Key has sub keys, enumerate profiles#
            if interface_key.subkeys_number() > 0:
                #Get Profiles Key#
                profiles_key = interface_key.subkey('Profiles')
                profile_dict = {
                    'InterfaceGuid':interface_guid
                }
                for profile_key in profiles_key.subkeys():
                    profile_guid = profile_key.name()
                    profile_dict['ProfileGuid'] = profile_guid
                    if profile_key.values_number() > 0:
                        for value in profile_key.values():
                            profile_dict[value.name()] = value.value()
                    if profile_key.subkeys_number() > 0:
                        metadata_key = profile_key.subkey('MetaData')
                        if metadata_key.values_number() > 0:
                            for value in metadata_key.values():
                                resolved_value = self._GetValue(value)
                                if isinstance(resolved_value,dict):
                                    profile_dict.update(resolved_value)
                                else:
                                    profile_dict[value.name()] = self._GetValue(value)
                    
                    for key in profile_dict:
                        if key not in RegistryHandler.WLANSVCINTERFACEPROFILES_COLUMN_MAPPING:
                            RegistryHandler.WLANSVCINTERFACEPROFILES_COLUMN_MAPPING[key] = 'BLOB'
                        
                        if key not in self.INTERFACE_COLUMN_LISTING:
                            self.INTERFACE_COLUMN_LISTING.append(key)
                            
                    profile_list.append(copy.deepcopy(profile_dict))
        
        self.outputDbHandler.CreateTableFromMapping(
            'WlanSvcInterfaceProfiles',
            RegistryHandler.WLANSVCINTERFACEPROFILES_COLUMN_MAPPING,
            None,
            RegistryHandler.WLANSVCINTERFACEPROFILES_COLUMN_ORDER
        )
        
        self.outputDbHandler.InsertFromListOfDicts(
            'WlanSvcInterfaceProfiles',
            profile_list,
            self.INTERFACE_COLUMN_LISTING
        )
        
        return True
        
    def GetGuidTable(self):
        '''Create a guid table from the guid_mapping'''
        guid_table = {}
        for key,value in self.guid_mapping.items():
            guid_table[key] = value
            guid_table[key+'LT'] = value+'LT'
            
        return guid_table
        
    def _EnumerateSrumExtensions(self):
        '''Insert wireless interface info into database'''
        reg_key = self.registry.open('Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Extensions')
        guid_map = {}
        for guid_key in reg_key.subkeys():
            #Get Interface GUID#
            guid_name = guid_key.name()
            desc = guid_key.value('(default)').value()
            tname = RegistryHandler._GetTableName(desc)
            guid_map[guid_name.upper()] = tname
            pass
        self.guid_mapping = guid_map
    
    @staticmethod
    def _GetTableName(desc):
        tname = desc
        tname = tname.replace(" ", "")
        return tname
    
    def EnumerateRegistryValues(self):
        hive = self.options.software_hive
        self.registry = Registry.Registry(
            hive
        )
        self.INTERFACE_COLUMN_LISTING = RegistryHandler.WLANSVCINTERFACEPROFILES_COLUMN_ORDER
        
        self._EnumerateSrumExtensions()
        result = self._GetWlanSvcKeys()
        if not result:
            # If there was no key, create the table with default columns #
            self.outputDbHandler.CreateTableFromMapping(
                'WlanSvcInterfaceProfiles',
                RegistryHandler.WLANSVCINTERFACEPROFILES_COLUMN_MAPPING,
                None,
                RegistryHandler.WLANSVCINTERFACEPROFILES_COLUMN_ORDER
            )
        
    def _GetValue(self,value):
        new_value = value.value()
        vname = value.name()
        vtype = value.value_type()
        
        ###CHECK FOR CUSTOM DEFINED TABLE COLUMNS TYPES###
        if vname in RegistryHandler.CUSTOM_COLUMNS:
            new_value = self._GetCustomValue(
                RegistryHandler.CUSTOM_COLUMNS[vname],
                new_value
            )
            
            return new_value
        
        return new_value
    
    def _GetCustomValue(self,custom_info,data):
        value = data
        if 'type' in custom_info:
            if custom_info['type'] == 'utf-16le':
                value = data.decode('utf-16le')
            elif custom_info['type'] == 'ChannelHints':
                value = ChannelHints(data)
            elif custom_info['type'] == 'WinDatetime':
                value = GetWinTimeStamp(data)
                
        return value
    
class SrumHandler():
    '''A Handler for converting SRU to SQLite'''
    CURRENT_LOCATION = {
        'table':None,
        'table_enum':None,
        'column':None
    }
    GUID_TABLES = {
        '{DD6636C4-8929-4683-974E-22C046A43763}':'NetworkConnectivityData',
        '{D10CA2FE-6FCF-4F6D-848E-B2E99266FA89}':'ApplicationResourceUsageData',
        '{973F5D5C-1D90-4944-BE8E-24B94231A174}':'NetworkUsageData',
        '{D10CA2FE-6FCF-4F6D-848E-B2E99266FA86}':'EnergyUsageData',
        '{FEE4E14F-02A9-4550-B5CE-5FA2DA202E37}':'WindowsPushNotificationData',
        '{FEE4E14F-02A9-4550-B5CE-5FA2DA202E37}LT':'WindowsPushNotificationDataLT',
    }
    SQLITE_TYPE = {
        'DATETIME':[
            pyesedb.column_types.DATE_TIME
        ],
        'REAL':[
            pyesedb.column_types.DOUBLE_64BIT,
            pyesedb.column_types.FLOAT_32BIT
        ],
        'INTEGER':[
            pyesedb.column_types.BOOLEAN,
            pyesedb.column_types.INTEGER_16BIT_SIGNED,
            pyesedb.column_types.INTEGER_16BIT_UNSIGNED,
            pyesedb.column_types.INTEGER_32BIT_SIGNED,
            pyesedb.column_types.INTEGER_32BIT_UNSIGNED,
            pyesedb.column_types.INTEGER_64BIT_SIGNED,
            pyesedb.column_types.INTEGER_8BIT_UNSIGNED
        ],
        'BLOB':[
            pyesedb.column_types.BINARY_DATA,
            pyesedb.column_types.LARGE_BINARY_DATA
        ],
        'TEXT':[
            pyesedb.column_types.GUID,
            pyesedb.column_types.LARGE_TEXT,
            pyesedb.column_types.SUPER_LARGE_VALUE,
            pyesedb.column_types.TEXT
        ]
    }
    
    #If Columns have same name but need to be treated differently#
    CUSTOM_TABLES = {
        
    }
    
    #How to decode a special column#
    CUSTOM_COLUMNS = {
        'EventTimestamp':{
            'type':'WinDatetime'
        },
        'ConnectStartTime':{
            'type':'WinDatetime'
        },
        'LocaleName':{
            'type':'utf-16le'
        },
        'Key':{
            'type':'utf-16le'
        },
        'IdBlob':{
            'type':'IdBlob'
        }
    }

    def __init__(self,options,guid_table=None):
        '''Create a SrumHandler
        
        Args:
            options: Options
            guid_table: Optional guid table mapping'''
        self.srum_db = options.srum_db
        self.output_db = options.output_db
        
        self.esedb_file = pyesedb.file()
        self.esedb_file.open(self.srum_db)
        
        if guid_table:
            SrumHandler.GUID_TABLES = guid_table
        
        self.outputDbConfig = DbConfig(
            dbname=self.output_db
        )
        
        self.outputDbHandler = DbHandler(
            self.outputDbConfig
        )
        
    def _CreateTableNameFromGuid(self,guid):
        '''If you wanted to change the table name of a guid table'''
        new_table_name = guid
        
        #new_table_name = new_table_name.replace('{','')
        #new_table_name = new_table_name.replace('}','')
        #new_table_name = new_table_name.replace('-','')
        
        return new_table_name
        
    def ConvertDb(self):
        '''Convert SRU Database to a SQLite Database'''
        for table in self.esedb_file.tables:
            #Enumerate if GUID Table#
            self.table_name = table.name
            if self.table_name.upper() in SrumHandler.GUID_TABLES:
                self.table_name = SrumHandler.GUID_TABLES[self.table_name]
                
            ###Check if Table Name is GUID###
            regexp = re.compile(r'^\{[0-9a-zA-Z]{8}\-[0-9a-zA-Z]{4}\-[0-9a-zA-Z]{4}\-[0-9a-zA-Z]{4}\-[0-9a-zA-Z]{12}\}')
            if regexp.search(self.table_name) is not None:
                self.table_name = self._CreateTableNameFromGuid(
                    self.table_name
                )
            
            SrumHandler.CURRENT_LOCATION['table'] = table.name
            SrumHandler.CURRENT_LOCATION['table_enum'] = self.table_name
            
            print 'Converting Table {} as {}'.format(table.name,self.table_name)
            
            column_names = []
            for column in table.columns:
                column_names.append(column.name)
                
            self._CreateTable(
                table
            )
            
            num_of_columns = table.get_number_of_columns()
            items_to_insert = []
            for record in table.records:
                enum_record = self._EnumerateRecord(
                    num_of_columns,
                    record
                )
                items_to_insert.append(enum_record)
                
            self.outputDbHandler.InsertFromListOfDicts(
                self.table_name,
                items_to_insert,
                column_names
            )
            
    def _CreateTable(self,table):
        '''Create a table
        
        Args:
            table: A pyesedb table object'''
        column_names = []
        for column in table.columns:
            column_names.append(column.name)
        
        field_mapping = self._CreateFieldMapping(
            table
        )
        
        self.outputDbHandler.CreateTableFromMapping(
            self.table_name,
            field_mapping,
            None,
            column_names
        )
        
    def _CreateFieldMapping(self,table):
        '''Create a field mapping (table schema) for the SQLite table
        
        Args:
            table: A pyesedb table object
            
        Return:
            field_mapping: A dictionary of column to type mappings'''
        field_mapping = {}
        for column in table.columns:
            key = column.name
            
            if column.type in SrumHandler.SQLITE_TYPE['TEXT']:
                field_mapping[key] = 'TEXT'
            elif column.type in SrumHandler.SQLITE_TYPE['BLOB']:
                field_mapping[key] = 'BLOB'
            elif column.type in SrumHandler.SQLITE_TYPE['INTEGER']:
                field_mapping[key] = 'INTEGER'
            elif column.type in SrumHandler.SQLITE_TYPE['REAL']:
                field_mapping[key] = 'REAL'
            elif column.type in SrumHandler.SQLITE_TYPE['DATETIME']:
                field_mapping[key] = 'DATETIME'
            else:
                logging.error('Type not accounted for in table mapping creation: {}'.format(column.type))
                sys.exit(1)
        
        return field_mapping
    
    def _EnumerateRecord(self,num_of_columns,record):
        '''Enumerate vales for a record
        
        Args:
            num_of_columns: The number of columns in the record
            record: a pyesedb record object
            
        Returns:
            values: the record as a dictionary'''
        values = {}
        for index in range(0,num_of_columns):
            self.CURRENT_VALUES = values
            data = self._GetColumnValueFromRecord(
                record,
                index
            )
            
            values.update(data)
            
        return values
        
    def _GetColumnValueFromRecord(self,record,index):
        '''Get enumerated value based off of column and/or type
        
        Args:
            record: a pyesedb record object
            index: the column index for record
        Return:
            value: The value of a column for the record
        '''
        item = {}
        value = None
        name = record.get_column_name(index)
        dtype = record.get_column_type(index)
        data = record.get_value_data(index)
        
        SrumHandler.CURRENT_LOCATION['column'] = name
        
        if data is None:
            item = {name:None}
            return item
        
        ###CHECK FOR CUSTOM DEFINED TABLE COLUMNS TYPES###
        if self.table_name in SrumHandler.CUSTOM_TABLES:
            if name in SrumHandler.CUSTOM_TABLES[self.table_name]:
                value = self._GetCustomValue(
                    SrumHandler.CUSTOM_TABLES[name][self.table_name],
                    data
                )
                item = {name:value}
                return item
            
        ###CHECK FOR CUSTOM DEFINED TABLE COLUMNS TYPES###
        if name in SrumHandler.CUSTOM_COLUMNS:
                value = self._GetCustomValue(
                    SrumHandler.CUSTOM_COLUMNS[name],
                    data
                )
                item = {name:value}
                return item
        
        if dtype == DBTYPES.DOUBLE_64BIT:
            value = struct.unpack('d',data)[0]
        if dtype == DBTYPES.FLOAT_32BIT:
            value = struct.unpack('f',data)[0]
        if dtype == DBTYPES.BOOLEAN:
            value = struct.unpack('?',data)[0]
        elif dtype == DBTYPES.INTEGER_8BIT_UNSIGNED:
            value = struct.unpack('B',data)[0]
        elif dtype == DBTYPES.INTEGER_16BIT_SIGNED:
            value = struct.unpack('h',data)[0]
        elif dtype == DBTYPES.INTEGER_16BIT_UNSIGNED:
            value = struct.unpack('H',data)[0]
        elif dtype == DBTYPES.INTEGER_32BIT_SIGNED:
            value = struct.unpack('i',data)[0]
        elif dtype == DBTYPES.INTEGER_32BIT_UNSIGNED:
            value = struct.unpack('I',data)[0]
        elif dtype == DBTYPES.INTEGER_64BIT_SIGNED:
            value = struct.unpack('q',data)[0]
        elif dtype == DBTYPES.GUID:
            value = uuid.UUID(bytes=data)
        elif dtype == DBTYPES.LARGE_TEXT:
            value = data
        elif dtype == DBTYPES.SUPER_LARGE_VALUE:
            value = data
        elif dtype == DBTYPES.TEXT:
            value = data
        elif dtype == DBTYPES.BINARY_DATA:
            value = data
        elif dtype == DBTYPES.LARGE_BINARY_DATA:
            value = data
        elif dtype == DBTYPES.DATE_TIME:
            value = GetOleTimeStamp(data)
        else:
            msg = 'UNKNOWN TYPE {}'.format(dtype)
            logging.error(msg)
            raise Exception(msg)
        
        item = {name:value}
        
        return item
    
    def _GetCustomValue(self,custom_info,data):
        '''Get a value from a column based off of defined criteria.
        
        Used to parse binary data within columns such as timestamps.
        
        Args:
            custom_info: A columns info from SrumHandler.CUSTOM_COLUMNS
            data: The raw data from a records column
        Returns:
            value: The custom value'''
        value = data
        if 'type' in custom_info:
            if custom_info['type'] == 'utf-16le':
                value = data.decode('utf-16le')
            elif custom_info['type'] == 'OleDatetime':
                value = GetOleTimeStamp(data)
            elif custom_info['type'] == 'WinDatetime':
                value = GetWinTimeStamp(data)
            elif custom_info['type'] == 'IdBlob':
                if self.CURRENT_VALUES['IdType'] == 2 or self.CURRENT_VALUES['IdType'] == 1 or self.CURRENT_VALUES['IdType'] == 0:
                    value = data.decode('utf-16le')
                elif self.CURRENT_VALUES['IdType'] == 3:
                    sid = SID(data)
                    if sid:
                        value = str(sid)
                
        return value

class Authority(long):
    def __new__(self, buf):
       return long.__new__(self, struct.unpack(">Q",('\x00\x00'+buf[0:6]))[0])
    
class SubAuthority(long):
    def __new__(self, buf):
       return long.__new__(self, struct.unpack("<L",buf[0:4])[0])

class SID(object):
    def __init__(self,buf):
        self.revision = struct.unpack("<B",buf[0:1])[0]
        self.sub_authority_count = struct.unpack("<B",buf[1:2])[0]
        self.authority = Authority(buf[2:8])
        self.sub_authorities = []
        
        # Get sub authorities
        offset = 8
        for i in range(self.sub_authority_count):
            self.sub_authorities.append(
                SubAuthority(buf[offset:offset+4])
            )
            offset += 4
    
    def __str__(self):
        return 'S-{}-{}-{}'.format(
            self.revision,
            self.authority,
            '-'.join(str(x) for x in self.sub_authorities)
        )

def GetOleTimeStamp(raw_timestamp):
    '''Return Datetime from raw OleTimestamp'''
    timestamp = struct.unpack(
        "d",
        raw_timestamp
    )[0]
    
    origDateTime = datetime.datetime(
        1899,
        12,
        30,
        0,
        0,
        0
    )
    
    timeDelta = datetime.timedelta(days=timestamp)
    
    new_datetime = origDateTime + timeDelta
  
    #new_datetime = new_datetime.strftime("%Y-%m-%d %H:%M:%S.%f")
    
    return new_datetime

def GetWinTimeStamp(raw_timestamp):
    '''Return Datetime from raw Win32Timestamp'''
    timestamp = struct.unpack(
        "Q",
        raw_timestamp
    )[0]
    
    if datetime < 0:
        return None
    
    microsecs, _ = divmod(
        timestamp,
        10
    )
    
    timeDelta = datetime.timedelta(
        microseconds=microsecs
    )
    
    origDateTime = datetime.datetime(
        1601,
        1,
        1
    )
    
    new_datetime = origDateTime + timeDelta
    #new_datetime = new_datetime.strftime("%Y-%m-%d %H:%M:%S.%f")
    
    return new_datetime

class ChannelHints(dict):
    def __init__(self,data):
        self['NameLength'] = struct.unpack("I",data[0:4])[0]
        self['Name'] = data[4:4+self['NameLength']]
        self['SSID'] = data[36:36+32].encode('hex')
    
class DbConfig():
    '''This tells the DbHandler what to connect too'''
    def __init__(self,dbname=None):
        self.db = dbname

class DbHandler():
    def __init__(self,db_config,table=None):
        #Db Flags#
        self.db_config = db_config
        
    def CreateTableFromMapping(self,tbl_name,field_mapping,primary_key_str,field_order):
        dbh = self.GetDbHandle()
        
        string = "CREATE TABLE IF NOT EXISTS '{0:s}' (\n".format(tbl_name)
        for field in field_order:
            string += "'{0:s}' {1:s},\n".format(
                field,
                field_mapping[field]
            )
        
        if primary_key_str is not None:
            string = string + primary_key_str
        else:
            string = string[0:-2]
        
        string = string + ')'
        
        cursor = dbh.cursor()
        
        try:
            cursor.execute(string)
        except Exception as error:
            error_str = u"ERROR {}\nSQL_STRING: {}".format(str(error),string)
            raise Exception(error_str)
        
    def CreateInsertString(self,table,row,column_order,INSERT_STR=None):
        nco = []
        for column in column_order:
            nco.append("'{}'".format(column))
            
        columns = ', '.join(nco)
        
        in_row = []
        
        for key in column_order:
            if key in row.keys():
                in_row.append("{}".format(row[key]))
            else:
                in_row.append(None)
            
            placeholders = ','.join('?' * len(in_row))
        
        if INSERT_STR == None:
            INSERT_STR = 'INSERT OR IGNORE'
        
        sql = '{} INTO \'{}\' ({}) VALUES ({})'.format(INSERT_STR,table,columns, placeholders)
            
        return sql
    
    def InsertFromListOfDicts(self,table,rows_to_insert,column_order,INSERT_STR=None):
        dbh = self.GetDbHandle()
        # Set text_factory to str so we can insert raw bytes
        dbh.text_factory = str
        sql_c = dbh.cursor()
        
        for row in rows_to_insert:
            in_row = []
            sql = self.CreateInsertString(
                table,
                row,
                column_order,
                INSERT_STR=None
            )
            
            for key in column_order:
                if key in row.keys():
                    in_row.append(row[key])
                else:
                    in_row.append(None)
            
            try:
                sql_c.execute(sql,in_row)
            except Exception as e:
                error_str = "[ERROR] {}\n[SQL] {}\n[ROW] {}".format(str(e),sql,str(row))
                raise Exception('SQL Error. Error: {}'.format(error_str))
        
        dbh.commit()
    
    def CreateView(self,view_str):
        dbh = self.GetDbHandle()
        cursor = dbh.cursor()
        
        cursor.execute(view_str)
        dbh.commit()
    
    def GetDbHandle(self):
        '''Create database handle based off of databaseinfo'''
        dbh = None
        
        dbh = sqlite3.connect(
            self.db_config.db,
            timeout=10000,
            detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES
        )
        
        return dbh
    
    def FetchRecords(self,sql_string):
        dbh = self.GetDbHandle()
        dbh.row_factory = sqlite3.Row
        
        column_names = []
        
        sql_c = dbh.cursor()
        
        sql_c.execute(sql_string)
        
        for desc in sql_c.description:
            column_names.append(
                desc[0]
            )
        
        
        for record in sql_c:
            yield column_names,record
    
    def GetColumnInfo(self,sql_string):
        dbh = self.GetDbHandle()
        dbh.row_factory = sqlite3.Row
        
        #Register User Functions#
        RegisterFunctions(dbh)
        
        sql_c = dbh.cursor()
        
        sql_c.execute(sql_string)
        
        row = sql_c.fetchone()
    
if __name__ == '__main__':
    multiprocessing.freeze_support()
    Main()
