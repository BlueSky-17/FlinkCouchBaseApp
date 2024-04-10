import streamlit as st
import argparse
import logging
import sys

from pyflink.table import StreamTableEnvironment, DataTypes
from pyflink.datastream import StreamExecutionEnvironment, RuntimeExecutionMode
from pyflink.datastream.connectors.file_system import FileSource, StreamFormat, FileSink, OutputFileConfig, RollingPolicy
from pyflink.datastream.formats.csv import CsvReaderFormat, CsvSchema
from pyflink.common.watermark_strategy import WatermarkStrategy

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
    env.set_parallelism(2)
    
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
    env.execute()
    
    return ds

def connectToCouchBase():
    load_dotenv()
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    bucket_name = os.getenv("DB_BUCKET_NAME")
    connection_string = os.getenv("DB_CONNECTION_STRING")
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

    return bucket, cluster
                
if __name__ == '__main__':
    st.write("Hello world!")
    ds = openDataSet()
    bucket, cluster = connectToCouchBase()

    
    