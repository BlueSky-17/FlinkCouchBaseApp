# Copyright (c) Streamlit Inc. (2018-2022) Snowflake Inc. (2022-2024)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any
import os
import numpy as np
import pandas as pd 
import streamlit as st
# from FlinkCouchBaseApp.appDraft import connectToCouchBase, getAllFromCouchBase, sink, openDataSet, getLastestFile
from app import *
import plotly.express as px
import matplotlib.pyplot as plt


def plotting_demo(df: pd.DataFrame):
    # day = len(df)
    # venueList = df['DailyVenue'].tolist()
    # status_text = st.sidebar.empty()

    # chart = st.line_chart(df['DailyVenue'])
    
    fig = px.line(df, x='Day', y='DailyVenue', title='Biểu đồ doanh thu theo ngày')
    fig.update_xaxes(title='Ngày')
    fig.update_yaxes(title='Doanh thu')

    # Hiển thị biểu đồ trong ứng dụng Streamlit
    st.plotly_chart(fig)



st.set_page_config(page_title="Dashboard", layout="wide")
st.markdown("# Dashboard")
st.sidebar.header("Dashboard")

print('dashboard.py here')

# dataPath = './Data/Online Retail100.csv'
dataPath = './Data/Online Retail1.csv'

tab = openDataSetTable(dataPath)

countryList = getCountryList(tab)

# print(countryList)

with st.sidebar:
    countrySelected = st.selectbox('Select a country', countryList, index=len(countryList)-1)
    
    yearList = [2010, 2011]
    yearSelected = st.selectbox('Select a year', yearList, index=len(yearList)-1)
    
    monthList = []
    
    if yearSelected == 2010:
        monthList = [12]
    else:
        monthList = [1,2,3,4,5,6,7,8,9,10,11,12] 
    monthSelected = st.selectbox('Select a month', monthList, index=len(monthList)-1)

# df_selected = df[(df['Country'] == countrySelected) & (df['Year'] == yearSelected) & (df['Month'] == monthSelected)]

# daily_sum = df_selected.groupby('Day')['Quantity'].sum().reset_index()

with st.container():
    df = getYearlyVenue(tab)
    temp = df["YearlyVenue"][0]    
    st.write(f'## Total Venue from 12/2010 - 12/2011: {temp} USD')

col = st.columns((3, 3), gap='medium')

with col[0]:
    st.write("#### Best Seller")
    
    columnsDrop = ['Total']
    
    df = getListProdcutTotal(tab).reset_index(drop=True)
    # df = df.drop(columns=columnsDrop)
    # df.index += 1
    # st.write(df)
    
    st.dataframe(df,
                column_order=("Description", "Total"),
                hide_index=True,
                width=None,
                column_config={
                "Description": st.column_config.TextColumn(
                    "Product",
                ),
                "Total": st.column_config.ProgressColumn(
                    "Venue",
                    format="%f",
                    min_value=0,
                    max_value=max(df['Total']),
                )}
            )

    df = getCountryCount(tab)
    
    st.write("#### Country Percentage")
    fig, ax = plt.subplots()
    ax.pie(df['Total'].tolist(), labels=df['Country'].tolist(), autopct='%1.1f%%', startangle=90)
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

    # Display the chart in Streamlit
    st.pyplot(fig)
    
with col[1]:
    df = getDailyVenue(tab, countrySelected, yearSelected, monthSelected)
    plotting_demo(df)
    
    




 





