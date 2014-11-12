from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime
import time
import numpy
import plotly.plotly as py
from plotly.graph_objs import Bar, Scatter, Data, Layout, XAxis, YAxis, Figure
from numpy import average, polyfit
import os
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
import zipfile
import requests
import cookielib, urllib
from distutils import spawn
from selenium.webdriver.common.by import By 
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
import code
import readline
import rlcompleter

# Important variables; set create_new_graph to 0 to not upload to plotly
create_new_graph = 0
ui_userid = 'gabeandlindsay'
ui_password = 'wedding032313'
plotly_userid = 'langelgjm'
plotly_password = '9jg4ctwmge'
download_dir = os.getcwd()
ui_url = 'https://www.uinet.com'
ui_myacct_url = 'https://www.uinet.com/wps/myportal/uinet/myaccount/accounthome/dashboard'
phantom_js = '/Users/gjm/phantomjs-1.9.8-macosx/bin/phantomjs'


# Create browser instance and login
print 'Logging into ' + ui_url + '...'
browser = webdriver.PhantomJS(phantom_js)
browser.implicitly_wait(10)
browser.get(ui_url)
username = browser.find_element_by_name('userid')
password = browser.find_element_by_name('password')
username.send_keys(ui_userid)
password.send_keys(ui_password)
password.submit()

print 'Traversing website...'
# Traverse pages and elements to obtain Green Button zip file
# This section is likely to break when the page design or layout changes
browser.get(ui_myacct_url)
# Find the EnergyGuide frame and switch to it
element = browser.find_element_by_xpath("//iframe[contains(@src,'energyguide.com')]")
browser.switch_to_frame(element)
# Find the "Energy Use Analysis" link, get its href attribute, and go there
element = browser.find_element_by_xpath("//a[contains(@href,'LoadAnalysis')]")
ui_analysis_url = element.get_attribute("href")
browser.get(ui_analysis_url)

# For testing only
#vars = globals()
#vars.update(locals())
#shell = code.InteractiveConsole(vars)
#shell.interact()

element = browser.find_element_by_xpath("//img[contains(@src,'images/GreenButton.jpg')]")
element.click()
print "clicked GreenButton"
handles = browser.window_handles
# Since clicking the Green Button opens a second window, switch to the second window
browser.switch_to_window(handles[1])
element = browser.find_element_by_id('btnDownloadUsage')
element.click()
print "clicked btnDownloadUsage"
element = browser.find_element_by_id('lnkDownload')
ActionChains(browser).move_to_element(element).perform()
# We need to wait a while for the element to become visible
# Recode this section to use a try with an expected condition?
time.sleep(10)
element.click()
print "clicked lnkDownload"
# PhantomJS can't download files. But clicking the element executes some javascript that changes the href attribute of the lnkDownload
# So here I get that attribute and download the file using another tool
element = browser.find_element_by_id('lnkDownload')
link = element.get_attribute('href')
print 'File location is ' + link

# Save webdriver cookies for use by requests
cj = cookielib.CookieJar()
for c in browser.get_cookies():
#    print "%s -> %s" % (c['name'], c['value'])
    ck = cookielib.Cookie(name=c['name'], value=urllib.unquote(c['value']), domain=c['domain'], \
             path=c['path'], \
             secure=c['secure'], rest={'HttpOnly': c['httponly']}, \
             version =0,    port=None,port_specified=False, \
             domain_specified=False,domain_initial_dot=False, \
             path_specified=True,   expires=None,   discard=True, \
             comment=None, comment_url=None, rfc2109=False)
#    print ck
    cj.set_cookie(ck)

r = requests.get(link, cookies=cj)
f = open('ui.zip', 'wb')
f.write(r.content)
f.close()

print 'Got Green Button file! Extracting and parsing...'

# Define a filter for file name extensions
def only_ext(ext):
    def compare(fn): return os.path.splitext(fn)[1] == ext
    return compare

# Define function to get the most recent path and file with a specific extension in a specified directory
def get_recent_file_with_ext(ext, directory):
    files = filter(os.path.isfile, os.listdir(directory))
    files = filter(only_ext(ext), files)
    # add path to each file
    files = [os.path.join(directory, f) for f in files] 
    files.sort(key=lambda x: os.path.getmtime(x))
    return files[-1]

# Get most recent zip file in the cwd
newest_file = get_recent_file_with_ext(".zip", download_dir)

# Unzip the most recent zip file
# This is not a safe way to do this - extractall does not prevent path traversal attacks
def unzip(source_filename, dest_dir):
    with zipfile.ZipFile(source_filename) as zf:
        zf.extractall()
unzip(newest_file, download_dir)

# Get most recent xml file
newest_file = get_recent_file_with_ext(".xml", download_dir)

#e = 0
starts = []
timestamps = []
values = []

# Use the most recent xml file as our data source
f = open(newest_file, 'r')
xml = f.read()
soup = BeautifulStoneSoup(xml)
entries = soup.findAll('entry')

# Create lists based on data source
for entry in entries:
    if entry.title is not None:
#        e = e + 1
#        print 'Entry ' + str(e) + ': ' + entry.title.contents[0]
# Exclude blocks like address info or summary usage
        if entry.title.contents[0] == u'Energy Usage':
            duration = entry.content.intervalblock.intervalreading.timeperiod.duration.contents[0]
#            print 'Duration: ' + duration
            start = entry.content.intervalblock.intervalreading.timeperiod.start.contents[0]
#            print 'Start: ' + start
            timestamp = datetime.fromtimestamp(int(start))
#            print 'Timestamp: ' + str(datetime.fromtimestamp(timestamp))
            value = int(entry.content.intervalblock.intervalreading.value.contents[0])
#            print 'Value: ' + value
            print timestamp, value
            starts.append(int(start))
            timestamps.append(timestamp)
            values.append(value)
    else:
        pass

f.close()

# Convert to kWh
values = numpy.array(values)
values = values / 1000
values_mean = average(values)
print 'Average: ' +  str(values_mean)
# Convert single mean to list for plotting purposes
values_mean = [values_mean] * len(values)

# Make a fitted line
timestamps_ts = [time.mktime(t.timetuple()) for t in timestamps]
m,b = polyfit(timestamps_ts, values, 1)
values_fitted = [m*x + b for x in timestamps_ts]

if create_new_graph:
    py.sign_in(plotly_userid, plotly_password)
      
    bar1 = Bar(
               x=timestamps,
               y=values,
               name='Daily')
    line_mean = Scatter(
                       x=timestamps,
                       y=values_mean,
                       mode='lines',
                       name='Mean'
                       )
    line_fit = Scatter(
                       x=timestamps,
                       y=values_fitted,
                       mode='lines',
                       name='Trend'
                       )

    data = Data([bar1, line_mean, line_fit])

    layout = Layout(
                    title='Energy Usage',
                    yaxis=YAxis(title='kWh consumed in prior 24h period'),
                    xaxis=XAxis(title='Automatically updated daily from smart meter')
                    )

    fig = Figure(data=data, layout=layout)
    plot_url = py.plot(fig, filename='energy-usage', auto_open=False)
    print 'Uploaded new Plotly plot.'
else:
    print 'Didn\'t upload new Plotly plot.'

print "Sleeping for 5 minutes."
time.sleep(300)
print 'Done.'
