import streamlit as st
import argparse
import logging
import sys
import os
import datetime
import json
import csv

from pyflink.table import StreamTableEnvironment, DataTypes
from pyflink.datastream import StreamExecutionEnvironment, RuntimeExecutionMode
from pyflink.datastream.connectors.file_system import FileSource, StreamFormat, FileSink, OutputFileConfig, RollingPolicy
from pyflink.datastream.formats.csv import CsvReaderFormat, CsvSchema
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.common.serialization import Encoder
from pyflink.datastream.formats.csv import CsvBulkWriters
from pyflink.datastream import SinkFunction

from datetime import timedelta
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import (ClusterOptions, ClusterTimeoutOptions,
                               QueryOptions)
from dotenv import load_dotenv
import os

def openDataSet(): 
    #open example dataset with 100 rows
    data_Path = './Data/Online Retail100.csv'

    # Create the corresponding StreamExecutionEnvironment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_runtime_mode(RuntimeExecutionMode.STREAMING)
    # write all the data to one file
    env.set_parallelism(1)
    
    schema = CsvSchema.builder()\
            .add_number_column('InvoiceNo', number_type=DataTypes.INT())\
            .add_string_column('StockCode')\
            .add_string_column('Description')\
            .add_number_column('Quantity', number_type=DataTypes.INT())\
            .add_string_column('InvoiceDate')\
            .add_number_column('UnitPrice', number_type=DataTypes.DOUBLE())\
            .add_number_column('CustomerID', number_type=DataTypes.INT())\
            .add_string_column('Country')\
            .set_column_separator(',') \
            .set_escape_char('\\') \
            .set_use_header() \
            .set_strict_headers() \
            .build()
            
    source = FileSource.for_record_stream_format(CsvReaderFormat.for_schema(schema), data_Path).build()
    ds = env.from_source(source, WatermarkStrategy.no_watermarks(), 'csv-source')
    
    ds.print()
    
    # ds.map(lambda x: (x, 1))\
    #     .key_by(lambda x: x[1])\
    #     .reduce(lambda x,y: ('Total',x[1] + y[1]))\
    #     .print()
    
    # env.execute()


    return ds, env

def sink(ds,outputPath):
    
    schemaOutput = CsvSchema.builder()\
        .add_number_column('InvoiceNo', number_type=DataTypes.INT())\
        .add_string_column('StockCode')\
        .add_string_column('Description')\
        .add_number_column('Quantity', number_type=DataTypes.INT())\
        .add_string_column('InvoiceDate')\
        .add_number_column('UnitPrice', number_type=DataTypes.DOUBLE())\
        .add_number_column('CustomerID', number_type=DataTypes.INT())\
        .add_string_column('Country')\
        .set_column_separator(',') \
        .set_strict_headers(strict = True)\
        .set_use_header(use = False) \
        .build()
        
    sink = FileSink \
    .for_bulk_format(outputPath, CsvBulkWriters.for_schema(schemaOutput))\
    .with_output_file_config(
            OutputFileConfig.builder()
            .with_part_suffix(".csv")
            .build())\
    .build()
        
    ds.sink_to(sink)
    
    return ds

def getLastestFile(path):
    lastestFolder = None
    
    recentModTime = datetime.datetime.min
    for folderName, subFolder, fileNames in os.walk(path):
        folderModTime = datetime.datetime.fromtimestamp(os.path.getmtime(folderName))
        
        if folderModTime > recentModTime:
            recentModTime = folderModTime
            lastestFolder = folderName
    
    # path = os.path.join(path, lastestFolder)
    files = os.listdir(folderName)
    
    lastestFile = None
    recentModTime = datetime.datetime.min
    
    for file in files:
        
        filePath = os.path.join(lastestFolder, file)
        fileModTime = datetime.datetime.fromtimestamp(os.path.getmtime(filePath))
        
        if fileModTime > recentModTime:
            recentModTime = fileModTime
            lastestFile = file
            
    return lastestFile, lastestFolder
        
def connectToCouchBase():
    load_dotenv()
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    bucket_name = os.getenv("DB_BUCKET_NAME")
    connection_string = os.getenv("DB_CONNECTION_STRING")
    scope = os.getenv("DB_SCOPE")
    # User Input ends here.

    # Connect options - authentication
    auth = PasswordAuthenticator(
        username,
        password,
    )

    # Get a reference to our cluster
    # NOTE: For TLS/SSL connection use 'couchbases://<your-ip-address>' instead
    cluster = Cluster(connection_string, ClusterOptions(auth))

    # Wait until the cluster is ready for use.
    cluster.wait_until_ready(timedelta(seconds=5))
    
    is_connected = cluster.ping()
    if is_connected:
        print("Kết nối tới Couchbase thành công!")
    else:
        print("Không thể kết nối tới Couchbase.")

    # get a reference to our bucket
    bucket = cluster.bucket(bucket_name)
    
    scope = bucket.scope(scope)

    return scope, bucket, cluster

def insertToCouchBase(coll, filePath):
    with open(filePath, 'r', newline='', encoding='utf-8') as csvfile:
        csvReader = csv.reader(csvfile)
        
        try:
            for row in csvReader:
                document = {
                    "invoiceNo": int(row[0]),
                    "stockCode": row[1],
                    "description": row[2],
                    "quantity": int(row[3]),
                    "invoiceDate": row[4],
                    "unitPrice": float(row[5]),
                    "customerId": row(row[6]),
                    "county": row[7]
                }
                
                key = row[0] + "_" + row[1]
                
                result = coll.upsert(key, document)
                print(result.cas)
        except Exception as e:
            print(e)
            
    

if __name__ == '__main__':
    st.write("Hello world!")
    
    outputPath = './Data/output'
    ds, env = openDataSet()
    ds = sink(ds, outputPath)
    env.execute()

    file, folder = getLastestFile(outputPath)
    filePath = os.path.join(folder, file)
    
    scope, bucket, cluster = connectToCouchBase()
    
    coll = scope.collection("raw_data")
    
    insertToCouchBase(coll, filePath)
    
    
    
    

    
    