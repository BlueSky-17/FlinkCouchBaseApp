import argparse
import logging
import sys
import os
import datetime
import pandas as pd
import csv
import time
from dotenv import load_dotenv
import streamlit as st

from pyflink.datastream import StreamExecutionEnvironment, RuntimeExecutionMode
from pyflink.datastream.connectors.file_system import FileSource, StreamFormat, FileSink, OutputFileConfig, RollingPolicy
from pyflink.datastream.formats.csv import CsvReaderFormat, CsvSchema
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.common.serialization import Encoder
from pyflink.common.types import Row
from pyflink.datastream.formats.csv import CsvBulkWriters
from pyflink.datastream import SinkFunction

from pyflink.table import StreamTableEnvironment, DataTypes
from pyflink.common import Row
from pyflink.table import (EnvironmentSettings, TableEnvironment, TableDescriptor, Schema,
                           DataTypes, FormatDescriptor, Table)
from pyflink.table.expressions import lit, col
from pyflink.table.udf import udf, udtf

from datetime import timedelta
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import (ClusterOptions, ClusterTimeoutOptions,
                               QueryOptions)
from couchbase.exceptions import CouchbaseException

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
from collections import Counter

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors
from scipy.stats import linregress
#from yellowbrick.cluster import KElbowVisualizer, SilhouetteVisualizer


@udtf(result_types=[DataTypes.INT(), DataTypes.INT(), DataTypes.INT()])
def splitInvoiceDate(x): 
    temp = x.split(' ')[0]
    month = int(temp.split('/')[0])
    day = int(temp.split('/')[1])
    year = int(temp.split('/')[2])
    
    return [Row(day,month,year)]

@udtf(result_types=[DataTypes.FLOAT()])
def calculateVenue(quantity, unitprice): 
    
    venue = int(quantity) * unitprice
    
    return [Row(venue)]


def openDataSet(dataPath): 

    # Create the corresponding StreamExecutionEnvironment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_runtime_mode(RuntimeExecutionMode.STREAMING)
    # write all the data to one file
    env.set_parallelism(1)
    
    schema = CsvSchema.builder()\
            .add_string_column('InvoiceNo')\
            .add_string_column('StockCode')\
            .add_string_column('Description')\
            .add_number_column('Quantity', number_type=DataTypes.INT())\
            .add_string_column('InvoiceDate')\
            .add_number_column('UnitPrice', number_type=DataTypes.DOUBLE())\
            .add_string_column('CustomerID')\
            .add_string_column('Country')\
            .set_column_separator(',') \
            .set_escape_char('\\') \
            .set_use_header() \
            .set_strict_headers() \
            .build()
            
    source = FileSource.for_record_stream_format(CsvReaderFormat.for_schema(schema), dataPath).build()
    ds = env.from_source(source, WatermarkStrategy.no_watermarks(), 'csv-source')
    return ds, env

def sink(ds,outputPath):
    
    schemaOutput = CsvSchema.builder()\
        .add_string_column('InvoiceNo')\
        .add_string_column('StockCode')\
        .add_string_column('Description')\
        .add_number_column('Quantity', number_type=DataTypes.INT())\
        .add_string_column('InvoiceDate')\
        .add_number_column('UnitPrice', number_type=DataTypes.DOUBLE())\
        .add_string_column('CustomerID')\
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
    cluster.wait_until_ready(timedelta(seconds=10))
    
    is_connected = cluster.ping()
    if is_connected:
        print("Kết nối tới Couchbase thành công!")
    else:
        print("Không thể kết nối tới Couchbase.")

    # get a reference to our bucket
    bucket = cluster.bucket(bucket_name)
    print(bucket_name)
    scope = bucket.scope(scope)

    return scope, bucket, cluster

def insertToCouchBase(coll, filePath):
    with open(filePath, 'r', newline='', encoding='utf-8') as csvfile:
        csvReader = csv.reader(csvfile)
        
        try:
            for row in csvReader:
                document = {
                    "invoiceNo": row[0],
                    "stockCode": row[1],
                    "description": row[2],
                    "quantity": int(row[3]),
                    "invoiceDate": row[4],
                    "unitPrice": float(row[5]),
                    "customerId": int(row[6]),
                    "country": row[7]
                }
                
                key = row[0] + "_" + row[1]
                
                result = coll.upsert(key, document)
                print(result.cas)
        except Exception as e:
            print(e)

def getAllFromCouchBase(scope):
    query = f'SELECT * FROM raw_data'

    row_iter = scope.query(query)

    result = []
    
    for row in row_iter:
        result.append(row['raw_data'])
        
    return result
    
def plot_missing_percentage(df: pd.DataFrame):
    missing_data = df.isna().sum()
    missing_percentage = (missing_data[missing_data > 0] / df.shape[0]) * 100

    missing_percentage = missing_percentage.sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(15, 4))
    ax.barh(missing_percentage.index, missing_percentage, color="#ff6200")

    for i, (value, name) in enumerate(
        zip(missing_percentage, missing_percentage.index)
    ):
        ax.text(
            value + 0.5,
            i,
            f"{value:.2f}%",
            ha="left",
            va="center",
            fontweight="bold",
            fontsize=18,
            color="black",
        )

    ax.set_xlim([0, 50])
    plt.title("Missing values proportion", fontweight="bold", fontsize=22)
    plt.xlabel("Percentage (%)", fontsize=16)
    st.pyplot(plt)

def print_top_frequent(df: pd.DataFrame, column: str, num: int = 5):
    top_10_percent = df[column].value_counts(normalize=True).head(num) * 100

    plt.figure(figsize=(12,8))
    top_10_percent.plot(kind='barh', color='#ff6200')

    for i, value in enumerate(top_10_percent):
        plt.text(value, i, f'{value:.2f}%', fontsize = 10)
    
    plt.title(f'Top 10 most frequent {column}')
    plt.xlabel(f'Frequency (%)')
    plt.ylabel(column)
    plt.gca().invert_yaxis()
    st.pyplot(plt)

def openDataSetTable(inputPath) -> Table:
    
    t_env = TableEnvironment.create(EnvironmentSettings.in_streaming_mode())
    # write all the data to one file
    t_env.get_config().set("parallelism.default", "1")
    
    t_env.create_temporary_table(
        'source',
        TableDescriptor.for_connector('filesystem')
            .schema(Schema.new_builder()
                    .column('InvoiceNo', DataTypes.STRING())
                    .column('StockCode', DataTypes.STRING())
                    .column('Description', DataTypes.STRING())
                    .column('Quantity', DataTypes.STRING())
                    .column('InvoiceDate', DataTypes.STRING())
                    .column('UnitPrice', DataTypes.FLOAT())
                    .column('CustomerID', DataTypes.STRING())
                    .column('Country', DataTypes.STRING())
                    .build())
            .option('path', inputPath)
            .format("csv")
            .build())
    
    
    tab = t_env.from_path('source')
    res = tab.join_lateral(splitInvoiceDate(col('InvoiceDate')).alias("Day", "Month", "Year")).select(col("*"))
    return res

def filterData(tab, country, year, month) -> pd.DataFrame:
    res = tab.filter(col('Country') == country)\
                .filter(col('Year') == year)\
                .filter(col('Month') == month)
                
    df = res.to_pandas()
    
    return df

def getVenuePerMonth(tab, country, year, month) -> pd.DataFrame:
    res = tab.filter(col('Country') == country)\
                .filter(col('Year') == year)\
                .filter(col('Month') == month)\
                .join_lateral(calculateVenue(col('Quantity'), col('UnitPrice')).alias("Venue") )\
                .select(col('Venue').sum.alias('Total'))
    df = res.to_pandas()
    
    return df

def getListProduct(tab, country, year, month) -> pd.DataFrame:
    res = tab.filter(col('Country') == country)\
            .filter(col('Year') == year)\
            .filter(col('Month') == month)\
            .join_lateral(calculateVenue(col('Quantity'), col('UnitPrice')).alias("Venue"))\
            .select(col('*'))\
            .group_by(col('StockCode'), col('Description'))\
            .select(col('StockCode'), col('Description'), col('Venue').sum.alias("Total"))
            
            # .select(col('StockCode'), col('Description'), col('Venue').sum.alias('Total'))
            
    df = res.to_pandas()
    df = df.sort_values(by='Total', ascending=False)
    
    # print(df)
    return df

def getListProdcutTotal(tab) -> pd.DataFrame:
    res = tab.join_lateral(calculateVenue(col('Quantity'), col('UnitPrice')).alias("Venue"))\
            .select(col('*'))\
            .group_by(col('Description'))\
            .select(col('Description'), col('Venue').sum.alias("Total"))
        
    df = res.to_pandas()
    df = df.sort_values(by='Total', ascending=False).iloc[:10]
    
    # print(df)
    return df

def getDailyVenue(tab: Table, country, year, month) -> pd.DataFrame:
    res = tab.filter(col('Country') == country)\
        .filter(col('Year') == year)\
        .filter(col('Month') == month)\
        .join_lateral(calculateVenue(col('Quantity'), col('UnitPrice')).alias("Venue"))\
        .group_by(col('Day'))\
        .select(col('Day'), col('Venue').sum.alias('DailyVenue'))
        
    df = res.to_pandas()
    return df

def getCountryList(tab):
    res = tab.group_by(col('Country')).select(col('Country'))
    
    # res.execute().print()

    df = res.to_pandas()
    
    countryList = df['Country'].tolist()
    
    return countryList

def getCountryCount(tab):
    res = tab.join_lateral(calculateVenue(col('Quantity'), col('UnitPrice')).alias("Venue"))\
            .group_by(col('Country'))\
            .select(col('Country'), col('Venue').sum.alias('Total'))
    
    df = res.to_pandas()
    
    print(df)
    
    return df

def getYearlyVenue(tab):
    res = tab.join_lateral(calculateVenue(col('Quantity'), col('UnitPrice')).alias("Venue"))\
            .select(col('Venue').sum.alias('YearlyVenue'))
        
    df = res.to_pandas()
    
    return df


# Function to create a radar chart
def create_radar_chart(ax, angles, data, color, cluster):
    # Plot the data and fill the area
    ax.fill(angles, data, color=color, alpha=0.4)
    ax.plot(angles, data, color=color, linewidth=2, linestyle="solid")

    # Add a title
    ax.set_title(f"Cluster {cluster}", size=20, color=color, y=1.1)

if __name__ == '__main__':
    st.set_page_config(
        page_title="Sales data simple dashboard",
        page_icon="✅",
        layout="wide",
    )
    
    # st.sidebar.success("Select a demo above.")
    
    outputPath = './Data/output'
    dataPath = './Data/Online Retail.csv'
    
    ds, env = openDataSet(dataPath)
    ds = sink(ds, outputPath)
    
    env.execute()

    time.sleep(10)

    file, folder = getLastestFile(outputPath)
    filePath = os.path.join(folder, file)

    #scope, bucket, cluster = connectToCouchBase()
    
    # coll = scope.collection("raw_data")
    
    # insertToCouchBase(coll, filePath)
    
    # listDataJSON = getAllFromCouchBase(scope) #listData type is JSON
    
    # listData = pd.DataFrame(listDataJSON)
    # dashboard(listData)
    
    #coll = scope.collection("raw_data")
    
    #insertToCouchBase(coll, filePath)

    st.title(" :bar_chart: CompanyX analytics real-time dashboard")
    df = pd.read_csv(filePath, names= ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"])
    st.write("## Number of Null and NaN values detected")
    plot_missing_percentage(df)
    st.write("## Get top 10 in data")
    option = st.selectbox("Top n in X collumn: X = ", df.columns.to_list())

    print_top_frequent(df, option, 10)
    # Convert InvoiceDate to datetime and extract only the date
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["InvoiceDay"] = pd.to_datetime(df["InvoiceDate"]).dt.date
    df['Transaction_Status'] = np.where(df.InvoiceNo.astype(str).str.startswith('C'), 'Cancelled','Completed')

    # Find the most recent purchase date for each customer
    customer_data = df.groupby("CustomerID")["InvoiceDay"].max().reset_index()

    # Find the most recent date in the entire dataset
    most_recent_date = df["InvoiceDay"].max()

    # Convert InvoiceDay to datetime type before subtraction
    customer_data["InvoiceDay"] = pd.to_datetime(customer_data["InvoiceDay"])
    most_recent_date = pd.to_datetime(most_recent_date)

    # Calculate the number of days since the last purchase for each customer
    customer_data["Days_Since_Last_Purchase"] = (
    most_recent_date - customer_data["InvoiceDay"]
    ).dt.days

    # Remove the InvoiceDay column
    customer_data = customer_data.drop(columns=["InvoiceDay"])

    # Calculate the total number of transactions made by each customer
    total_transactions = df.groupby("CustomerID")["InvoiceNo"].nunique().reset_index()
    total_transactions = total_transactions.rename(
        columns={"InvoiceNo": "Total_Transactions"}
    )

    # Calculate the total number of products purchased by each customer
    total_products_purchased = df.groupby("CustomerID")["Quantity"].sum().reset_index()
    total_products_purchased = total_products_purchased.rename(
        columns={"Quantity": "Total_Products_Purchased"}
    )

    # Merge the new features into the customer_data dataframe
    customer_data = pd.merge(customer_data, total_transactions, on="CustomerID")
    customer_data = pd.merge(customer_data, total_products_purchased, on="CustomerID")
        
    # Calculate the total spend by each customer
    df["Total_Spend"] = df["UnitPrice"] * df["Quantity"]
    total_spend = df.groupby("CustomerID")["Total_Spend"].sum().reset_index()

    # Calculate the average transaction value for each customer
    average_transaction_value = total_spend.merge(total_transactions, on="CustomerID")
    average_transaction_value["Average_Transaction_Value"] = (
        average_transaction_value["Total_Spend"]
        / average_transaction_value["Total_Transactions"]
    )

    # Merge the new features into the customer_data dataframe
    customer_data = pd.merge(customer_data, total_spend, on="CustomerID")
    customer_data = pd.merge(
        customer_data,
        average_transaction_value[["CustomerID", "Average_Transaction_Value"]],
        on="CustomerID",
    )
    
        # Calculate the number of unique products purchased by each customer
    unique_products_purchased = (
        df.groupby("CustomerID")["StockCode"].nunique().reset_index()
    )
    unique_products_purchased = unique_products_purchased.rename(
        columns={"StockCode": "Unique_Products_Purchased"}
    )

    # Merge the new feature into the customer_data dataframe
    customer_data = pd.merge(customer_data, unique_products_purchased, on="CustomerID")

    # Extract day of week and hour from InvoiceDate
    df["Day_Of_Week"] = df["InvoiceDate"].dt.dayofweek
    df["Hour"] = df["InvoiceDate"].dt.hour

    # Calculate the average number of days between consecutive purchases
    days_between_purchases = df.groupby("CustomerID")["InvoiceDay"].apply(
        lambda x: (x.diff().dropna()).apply(lambda y: y.days)
    )
    average_days_between_purchases = (
        days_between_purchases.groupby("CustomerID").mean().reset_index()
    )
    average_days_between_purchases = average_days_between_purchases.rename(
        columns={"InvoiceDay": "Average_Days_Between_Purchases"}
    )

    # Find the favorite shopping day of the week
    favorite_shopping_day = (
        df.groupby(["CustomerID", "Day_Of_Week"]).size().reset_index(name="Count")
    )
    favorite_shopping_day = favorite_shopping_day.loc[
        favorite_shopping_day.groupby("CustomerID")["Count"].idxmax()
    ][["CustomerID", "Day_Of_Week"]]

    # Find the favorite shopping hour of the day
    favorite_shopping_hour = (
        df.groupby(["CustomerID", "Hour"]).size().reset_index(name="Count")
    )
    favorite_shopping_hour = favorite_shopping_hour.loc[
        favorite_shopping_hour.groupby("CustomerID")["Count"].idxmax()
    ][["CustomerID", "Hour"]]

    # Merge the new features into the customer_data dataframe
    customer_data = pd.merge(customer_data, average_days_between_purchases, on="CustomerID")
    customer_data = pd.merge(customer_data, favorite_shopping_day, on="CustomerID")
    customer_data = pd.merge(customer_data, favorite_shopping_hour, on="CustomerID")
    

        # Group by CustomerID and Country to get the number of transactions per country for each customer
    customer_country = (
        df.groupby(["CustomerID", "Country"])
        .size()
        .reset_index(name="Number_of_Transactions")
    )

    # Get the country with the maximum number of transactions for each customer (in case a customer has transactions from multiple countries)
    customer_main_country = customer_country.sort_values(
        "Number_of_Transactions", ascending=False
    ).drop_duplicates("CustomerID")

    # Create a binary column indicating whether the customer is from the UK or not
    customer_main_country["Is_UK"] = customer_main_country["Country"].apply(
        lambda x: 1 if x == "United Kingdom" else 0
    )

    # Merge this data with our customer_data dataframe
    customer_data = pd.merge(
        customer_data,
        customer_main_country[["CustomerID", "Is_UK"]],
        on="CustomerID",
        how="left",
    )

    # Calculate the total number of transactions made by each customer
    total_transactions = df.groupby("CustomerID")["InvoiceNo"].nunique().reset_index()

    # Calculate the number of cancelled transactions for each customer
    cancelled_transactions = df[df["Transaction_Status"] == "Cancelled"]
    cancellation_frequency = (
        cancelled_transactions.groupby("CustomerID")["InvoiceNo"].nunique().reset_index()
    )
    cancellation_frequency.rename(
        columns={"InvoiceNo": "Cancellation_Frequency"}, inplace=True
    )

    # Merge the Cancellation Frequency data into the customer_data dataframe
    customer_data = pd.merge(
        customer_data, cancellation_frequency, on="CustomerID", how="left"
    )

    # Replace NaN values with 0 (for customers who have not cancelled any transaction)
    customer_data["Cancellation_Frequency"].fillna(0, inplace=True)

    # Calculate the Cancellation Rate
    customer_data["Cancellation_Rate"] = (
        customer_data["Cancellation_Frequency"] / total_transactions["InvoiceNo"]
    )

        # Extract month and year from InvoiceDate
    df["Year"] = pd.to_datetime(df["InvoiceDate"]).dt.year
    df["Month"] = df["InvoiceDate"].dt.month

    # Calculate monthly spending for each customer
    monthly_spending = (
        df.groupby(["CustomerID", "Year", "Month"])["Total_Spend"].sum().reset_index()
    )

    # Calculate Seasonal Buying Patterns: We are using monthly frequency as a proxy for seasonal buying patterns
    seasonal_buying_patterns = (
        monthly_spending.groupby("CustomerID")["Total_Spend"]
        .agg(["mean", "std"])
        .reset_index()
    )
    seasonal_buying_patterns.rename(
        columns={"mean": "Monthly_Spending_Mean", "std": "Monthly_Spending_Std"},
        inplace=True,
    )

    # Replace NaN values in Monthly_Spending_Std with 0, implying no variability for customers with single transaction month
    seasonal_buying_patterns["Monthly_Spending_Std"].fillna(0, inplace=True)


    # Calculate Trends in Spending
    # We are using the slope of the linear trend line fitted to the customer's spending over time as an indicator of spending trends
    def calculate_trend(spend_data: pd.DataFrame):
        # If there are more than one data points, we calculate the trend using linear regression
        if len(spend_data) > 1:
            x = np.arange(len(spend_data))
            slope, _, _, _, _ = linregress(x, spend_data)
            return slope
        # If there is only one data point, no trend can be calculated, hence we return 0
        else:
            return 0


    # Apply the calculate_trend function to find the spending trend for each customer
    spending_trends = (
        monthly_spending.groupby("CustomerID")["Total_Spend"]
        .apply(calculate_trend)
        .reset_index()
    )
    spending_trends.rename(columns={"Total_Spend": "Spending_Trend"}, inplace=True)

    # Merge the new features into the customer_data dataframe
    customer_data = pd.merge(customer_data, seasonal_buying_patterns, on="CustomerID")
    customer_data = pd.merge(customer_data, spending_trends, on="CustomerID")

    columns_to_scale = [
    "Days_Since_Last_Purchase",
    "Total_Transactions",
    "Total_Products_Purchased",
    "Total_Spend",
    "Average_Transaction_Value",
    "Unique_Products_Purchased",
    "Average_Days_Between_Purchases",
    "Hour",
    "Cancellation_Frequency",
    "Cancellation_Rate",
    "Monthly_Spending_Mean",
    "Monthly_Spending_Std",
    "Spending_Trend",
    ]

    scaled_customer_data = customer_data.copy()
    scaler = StandardScaler()
    scaled_customer_data[columns_to_scale] = scaler.fit_transform(
        scaled_customer_data[columns_to_scale]
    )

    scaled_customer_data = scaled_customer_data.set_index("CustomerID")

    optimal_k = 4

    kmeans = KMeans(
        n_clusters=optimal_k, init="k-means++", n_init=10, max_iter=100, random_state=42
    )
    kmeans.fit(scaled_customer_data)

    cluster_frequencies = Counter(kmeans.labels_)

    # Create a mapping from old labels to new labels based on frequency
    label_mapping = {
        label: new_label
        for new_label, (label, _) in enumerate(cluster_frequencies.most_common())
    }

    # Reverse the mapping to assign labels as per your criteria
    # label_mapping = {v: k for k, v in {2: 1, 1: 0, 0: 2}.items()}
    label_mapping = {v: k for k, v in {0: 3, 1: 2, 2: 1, 3: 0}.items()}

    # Apply the mapping to get the new labels
    new_labels = np.array([label_mapping[label] for label in kmeans.labels_])

    clustered_customer_data = customer_data.copy()
    clustered_customer_data["Cluster"] = new_labels

    cluster_percentage = (
        clustered_customer_data["Cluster"].value_counts(normalize=True) * 100
    ).reset_index()
    cluster_percentage.columns = ["Cluster", "Percentage"]
    cluster_percentage.sort_values(by="Cluster", inplace=True)

    # Create a horizontal bar plot
    plt.figure(figsize=(10, 4))
    sns.barplot(x="Percentage", y="Cluster", data=cluster_percentage, orient="h")

    # Adding percentages on the bars
    for index, value in enumerate(cluster_percentage["Percentage"]):
        plt.text(value + 0.5, index, f"{value:.2f}%")

    plt.title("Distribution of Customers Across Clusters", fontsize=14)
    plt.xticks(ticks=np.arange(0, 50, 5))
    plt.xlabel("Percentage (%)")
    st.pyplot(plt)

    colors = ["#e8000b", "#1ac938", "#023eff", '#ffa500']

    # Setting 'CustomerID' column as index and assigning it to a new dataframe
    df_customer = clustered_customer_data.set_index("CustomerID")

    # Standardize the data (excluding the cluster column)
    scaler = StandardScaler()
    df_customer_standardized = scaler.fit_transform(
        df_customer.drop(columns=["Cluster"], axis=1)
    )

    # Create a new dataframe with standardized values and add the cluster column back
    df_customer_standardized = pd.DataFrame(
        df_customer_standardized, columns=df_customer.columns[:-1], index=df_customer.index
    )
    df_customer_standardized["Cluster"] = df_customer["Cluster"]

    # Calculate the centroids of each cluster
    cluster_centroids = df_customer_standardized.groupby("Cluster").mean()

    # Set data
    labels = np.array(cluster_centroids.columns)
    num_vars = len(labels)

    # Compute angle of each axis
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()

    # The plot is circular, so we need to "complete the loop" and append the start to the end
    labels = np.concatenate((labels, [labels[0]]))
    angles += angles[:1]

    # Initialize the figure
    fig, ax = plt.subplots(figsize=(20, 15), subplot_kw=dict(polar=True), nrows=2, ncols=2)

    # Create radar chart for each cluster
    for i, color in enumerate(colors):
        data = cluster_centroids.loc[i].tolist()
        data += data[:1]  # Complete the loop
        create_radar_chart(ax[i // 2, i % 2], angles, data, color, i)

    # Add input data
    ax[0, 0].set_xticks(angles[:-1])
    ax[0, 0].set_xticklabels(labels[:-1])

    ax[0, 1].set_xticks(angles[:-1])
    ax[0, 1].set_xticklabels(labels[:-1])

    ax[1, 0].set_xticks(angles[:-1])
    ax[1, 0].set_xticklabels(labels[:-1])

    ax[1, 1].set_xticks(angles[:-1])
    ax[1, 1].set_xticklabels(labels[:-1])

    # Display the plot
    plt.tight_layout()
    st.pyplot(plt)