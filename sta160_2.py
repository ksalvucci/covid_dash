import threading
from tkinter import N
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import dash
from dash import dcc
from dash import html
import plotly.express as px
from datetime import datetime
import plotly.graph_objects as go


# DATA CLEANING
# read datasets
main_raw = pd.read_csv("https://data.cdc.gov/api/views/9mfq-cb36/rows.csv?accessType=DOWNLOAD") # 47460 x 15
vaccine_raw = pd.read_csv("https://data.cdc.gov/api/views/unsk-b7fc/rows.csv?accessType=DOWNLOAD") # 29976 x 82

#check for nan
main_before = list(main_raw.isnull().sum())
vaccine_before = list(vaccine_raw.isnull().sum())
main_check = pd.DataFrame({'main_columns':main_raw.columns, 'NA for Main ': main_before,})
vaccine_check = pd.DataFrame({'vaccine_columns': vaccine_raw.columns, 'NA for Vaccine': vaccine_before})

#sort Date
def sortDate(data, DateColumn):
    data[DateColumn] = pd.to_datetime(data[DateColumn], format = '%m/%d/%Y')
    data = data.sort_values(DateColumn)
    print('Number of Unique Dates:', len(data[DateColumn].unique()))
    return data

main_raw = sortDate(main_raw, 'submission_date') #791
vaccine_raw = sortDate(vaccine_raw, 'Date') #465

#fill NaN for main_raw
NAcol = ['conf_cases', 'prob_cases', 'pnew_case', 'conf_death', 'prob_death', 'pnew_death', 'new_death', 'new_case']
ffillcol = ['tot_cases', 'tot_death']

def fillNaN(raw_data):
    for i in range(len(NAcol)):
        raw_data[NAcol[i]] = raw_data[NAcol[i]].fillna(0)
    for j in range(len(main_raw.state.unique())):
        mask = (raw_data.state == main_raw.state.unique()[j])
        sub = raw_data[mask]
        if ((len(sub[sub.prob_cases != 0]) == 0) and
            (len(sub[sub.conf_cases != 0]) == 0)) or ((len(sub[sub.prob_death != 0]) == 0) and
            (len(sub[sub.conf_death != 0]) == 0)):
            raw_data[mask] = raw_data[mask].fillna('Agree')
    for k in range(len(ffillcol)):
        raw_data[ffillcol[k]] = raw_data[ffillcol[k]].fillna(method = 'ffill')

fillNaN(main_raw) # 47460 x 15

#check nan for main_raw
after = list(main_raw.isnull().sum())
check = pd.DataFrame({'Column Names':main_raw.columns, 'before': main_before, 'after': after})

#combine NYC to NY state
maskNY = (main_raw.state == 'NY')
maskNYC = (main_raw.state == 'NYC')
NYdata = main_raw[maskNY]
NYCdata = main_raw[maskNYC]

#supress copy warning
pd.options.mode.chained_assignment = None

#sum NYdata and NYCdata together and replace NYdata by the sum values
for i in range(len(NYdata)):
    for j in range(len(NYdata.columns)):
        if ((j >1) and (j<12)):
            NYdata.iloc[i,j] = NYdata.iloc[i,j]+NYCdata.iloc[i,j]

#replace the NY state data in main_raw by the new NYdata (sum of NY and NYC)
main_raw[(main_raw.state == 'NY')] = NYdata

#check data associate with the location (will delete at the final version)

#comparing VA vs. VA2
VA = vaccine_raw[vaccine_raw.Location == 'VA']
VA2 = vaccine_raw[vaccine_raw.Location == 'VA2']

#remove some locations
main_dropLoc = ['AS','FSM', 'GU','MP','NYC', 'PR', 'PW','RMI', 'VI']
vac_dropLoc  = ['AS', 'BP2', 'DD2', 'DS2', 'FM', 'GU', 'IH2', 'LTC', 'MH', 'MP', 'PR', 'RP', 'US', 'VA2', 'VI', 'PW']
# nomatch_loc = np.setdiff1d(main_data.state.unique(), vac_data.state.unquie())
# main_dropLoc.append(nomatch_loc)
# vac_dropLoc.append(nomatch_loc)

def DropState(data, locationColumn, dropList):
    for i in range(len(dropList)):
        data = data[data[locationColumn] != dropList[i]]
    return data

main_data = DropState(main_raw, 'state', main_dropLoc) # 40341 x 15
vac_data = DropState(vaccine_raw, 'Location', vac_dropLoc) # 23664 x 82

#merge datasets
vac_data = vac_data.rename(columns = {'Date':'submission_date','Location': 'state'})

unique_date = main_data.submission_date.unique() #791 dates

def VacColumn(data, ColumnToAdd):
    new = []
    for i in range(len(unique_date)):
        for j in range(len(data.state.unique())):
            mask = (data['submission_date'] == unique_date[i]) & (data['state'] == data.state.unique()[j])
            sub = data[mask]
            if len(sub) == 0:
                new.append(0)
            else:
                new.append(sub[ColumnToAdd].sum())
    return new

Distributed = VacColumn(vac_data, 'Distributed')

def ConvertAllCol(start, end):
    storeConvertedCol = []
    for i in range(start,end+1):
        storeConvertedCol.append(VacColumn(vac_data, str(vac_data.columns[i])))
    return storeConvertedCol

Dis2 = ConvertAllCol(3,4)

for i in range(len(Dis2)):
    main_data.insert(len(main_data.columns),'Vac'+str(i+3),Dis2[i], True)
# length main_data = 40341, len Dis2 = 40341

# rename column
df = main_data.rename(columns={'new_case': 'new_cases', 'pnew_case': 'pnew_cases'}) # 40339 x 17
vdf = vac_data #23664 x 82

#remove negative values
df = df[(df['new_cases'] >= 0)]
df = df[(df['new_death'] >= 0)]


# DASH APP

# heatmap 
mapfig = px.choropleth(df, 
                locations = 'state', 
                hover_name = 'state',
                color = 'tot_cases', 
                color_continuous_scale = "Reds",
                locationmode = 'USA-states',
                scope = "usa",
                title = 'Covid-19 Total Cases in Each State',
                height = 500,
                hover_data = {'tot_cases':True},
                labels = {'tot_cases':'Total Cases'}
            )

# app layout
app = dash.Dash(__name__)
server = app.server

app.layout = html.Div([
    html.H1("COVID-19 Dashboard"),
    html.Div([    
        dcc.Graph(
            id = 'map',
            figure = mapfig
        ),
        html.Div([
            dcc.Graph(
                id = 'agevac-graph'
            )],
                style = {'width': '69%', 'display': 'inline-block'}
        ),
        html.Div([
            html.Div(
                'Total Vaccines Administered',
                style = {'textAlign': 'center', 'font-weight': 'bold'}),
            html.Div(
                id = 'total-admin',
                style = {'textAlign': 'center'}),
            html.Div(
                'Vaccines Administered per 100K Population',
                style = {'textAlign': 'center', 'font-weight': 'bold'}),
            html.Div(
                id = 'admin-per',
                style = {'textAlign': 'center'}),
            html.Div(
                'Percentage of Population with Vaccine Series Completed',
                style = {'textAlign': 'center', 'font-weight': 'bold'}),
            html.Div(
                id = 'series-done',
                style = {'textAlign': 'center'})
            ],
                style = {'width': '29%', 'float': 'right', 'display': 'inline-block'}
        )
    ],
        style = {'width': '59%', 'display': 'inline-block'}
    ),
    html.Div([
        dcc.RadioItems(
            id = 'yaxis-select',
            options = [{'label':'Deaths', 'value':'death'}, {'label':'Cases', 'value':'cases'}],
            value = 'death',
            labelStyle = {'display': 'inline-block'}
        ),
        dcc.RadioItems(
            id = 'scope-select',
            options = [{'label': 'Total', 'value': 'tot_'}, {'label': 'New', 'value': 'new_'}],
            value = 'tot_',
            labelStyle = {'display': 'inline-block'}
        ),
            dcc.Graph(
            id = 'big-graph', 
        ),
            dcc.Graph(
                id = 'vac-graph'
            )
    ],
        style = {'width': '39%', 'float': 'right', 'display': 'inline-block'}
    )
])

# line chart update
@app.callback(
    dash.dependencies.Output('big-graph', 'figure'),
    [dash.dependencies.Input('yaxis-select', 'value'),
    dash.dependencies.Input('scope-select', 'value'),
    dash.dependencies.Input('map', 'clickData')
    ]
)
def update_graph(yaxis_column, scope, click):
    yaxis = scope + yaxis_column

    if click is None:
        state_name = 'CA'
    else:
        state_name = click['points'][0]['location']
    
    data = df[df.state == state_name]

    if (scope == 'new_'):
        s = 'New '
    else:
        s = 'Total '

    if (yaxis_column == 'cases'):
        a = 'Cases '
    else:
        a = 'Deaths ' 

    fig2 = px.line(data, x = 'submission_date', y = yaxis, title = s + a + 'in ' + state_name)
    #fig2.update_traces(marker = dict(color = 'red'))

    return fig2

# lollipop chart update
@app.callback(
    dash.dependencies.Output('vac-graph', 'figure'),
    [dash.dependencies.Input('map', 'clickData')
    ]
)
def update_graph(click):

    if click is None: 
        state_name = 'CA'
    else: 
        state_name = click['points'][0]['location']

    data = vdf[vdf.submission_date == (df['submission_date'].max())]
    data = data[data.state == state_name]
    col_list = ['state', 'Distributed_Janssen', 'Distributed_Moderna', 'Distributed_Pfizer', 'Administered_Janssen', 'Administered_Moderna', 'Administered_Pfizer']
    data = data[col_list]
    data = pd.wide_to_long(data, stubnames = ['Distributed', 'Administered'], i = 'state', j = 'vacvar', sep = '_', suffix='\\w+') 

    title_name = 'Vaccine Allocation in ' + state_name
    ylabs = ['Janssen', 'Moderna', 'Pfizer']
    xzero = 'Administered'
    xone = 'Distributed'

    return lolli(data, title_name, ylabs, xzero, xone)

# create lollipop chart
def lolli(data, title_name, ylabs, xzero, xone):
    fig1 = go.Figure()

    for i in range(0, len(data)):
        fig1.add_shape(type = 'line',
                       x0 = data[xzero][i],
                       y0 = i,
                       x1 = data[xone][i],
                       y1 = i,
                       line = dict(color = 'gray', width = 3))

    fig1.add_trace(go.Scatter(x = data[xone], 
                              y = ylabs, 
                              mode = 'markers',
                              marker_color = 'darkblue',
                              marker_size = 10,
                              name = xone))
    fig1.add_trace(go.Scatter(x = data[xzero],
                              y = ylabs,
                              mode = 'markers',
                              marker_color = 'green',
                              marker_size = 10,
                              name = xzero))

    fig1.update_layout(title = title_name)

    return fig1

# lollipop chart 2 update
@app.callback(
    dash.dependencies.Output('agevac-graph', 'figure'),
    [dash.dependencies.Input('map', 'clickData')
    ]
)
def update_graph(click):

    if click is None: 
        state_name = 'CA'
    else: 
        state_name = click['points'][0]['location']

    data = vdf[vdf.submission_date == (df['submission_date'].max())]
    data = data[data.state == state_name]
    col_list = ['state', 'Administered_12Plus', 'Administered_18Plus', 'Administered_65Plus', 'Series_Complete_12Plus', 'Series_Complete_18Plus', 'Series_Complete_65Plus']
    data = data[col_list]
    data = pd.wide_to_long(data, stubnames = ['Administered', 'Series_Complete'], i = 'state', j = 'vacvar', sep = '_', suffix='\\w+') 

    title_name = 'Vaccines by Age in ' + state_name
    ylabs = ['12 +', '18 +', '65 +']
    xzero = 'Series_Complete'
    xone = 'Administered'

    return lolli(data, title_name, ylabs, xzero, xone)


# update numeric values
@app.callback(
    dash.dependencies.Output('total-admin', 'children'),
    [dash.dependencies.Input('map', 'clickData')
    ]
)
def update_graph(click):

    if click is None: 
        state_name = 'CA'
    else: 
        state_name = click['points'][0]['location']

    data = vdf[vdf.submission_date == (df['submission_date'].max())]
    data = data[data.state == state_name]

    return data['Administered']
    
@app.callback(
    dash.dependencies.Output('admin-per', 'children'),
    [dash.dependencies.Input('map', 'clickData')
    ]
)
def update_graph(click):

    if click is None: 
        state_name = 'CA'
    else: 
        state_name = click['points'][0]['location']

    data = vdf[vdf.submission_date == (df['submission_date'].max())]
    data = data[data.state == state_name]

    return data['Admin_Per_100K']

@app.callback(
    dash.dependencies.Output('series-done', 'children'),
    [dash.dependencies.Input('map', 'clickData')
    ]
)
def update_graph(click):

    if click is None: 
        state_name = 'CA'
    else: 
        state_name = click['points'][0]['location']

    data = vdf[vdf.submission_date == (df['submission_date'].max())]
    data = data[data.state == state_name]

    return data['Series_Complete_Pop_Pct']


# run
if __name__ == '__main__':
    app.run_server(debug=True)