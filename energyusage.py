from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime
import time
import numpy
import plotly.plotly as py
#from plotly.graph_objs import Bar, Scatter, Data, Layout, XAxis, YAxis, Figure, Marker
from plotly.graph_objs import *
from numpy import average, polyfit
import os
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
import zipfile
import requests
import cookielib, urllib
import logging
import sys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from distutils import spawn

###############################################################################
# Private information you should set according to your accounts
ui_userid = 'gabeandlindsay'
ui_password = 'wedding032313'
plotly_userid = 'langelgjm'
plotly_password = '9jg4ctwmge'
###############################################################################

# Define the logging level
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

# Important variables; set create_new_graph to 0 to not upload a new graph to Plotly
working_dir = os.getcwd()
create_new_graph = 1
ui_url = 'https://www.uinet.com'
ui_myacct_url = 'https://www.uinet.com/wps/myportal/uinet/myaccount/accounthome/dashboard'
# Used to save the downloaded ZIP file
greenbutton_zipfile = 'greenbutton.zip'

# You should define your PhantomJS executable location here
phantom_js = '/Users/gjm/phantomjs-1.9.8-macosx/bin/phantomjs'
# But if you don't we'll try to find it
if phantom_js == '':
    phantom_js = spawn.find_executable("phantom_js")
    if phantom_js is None:
        logging.error("No PhantomJS path set, and none found automatically.")
        #sys.exit("Exiting.")
    else:
        logging.debug("No PhantomJS path set, but found at " + phantom_js)

###############################################################################

# Create browser instance and set timeouts
browser = webdriver.PhantomJS(phantom_js)
browser.implicitly_wait(10)
wait = WebDriverWait(browser, 10)

# Sign in to UI site
logging.info('Logging into ' + ui_url + '...')
browser.get(ui_url)
username = browser.find_element_by_name('userid')
password = browser.find_element_by_name('password')
username.send_keys(ui_userid)
password.send_keys(ui_password)
password.submit()

# Traverse pages and elements to obtain Green Button ZIP file
# This section is likely to break when the page design or layout changes
logging.info('Getting My Account page...')
browser.get(ui_myacct_url)
# Find the EnergyGuide frame and switch to it
element = browser.find_element_by_xpath("//iframe[contains(@src,'energyguide.com')]")
browser.switch_to_frame(element)
# Find the "Energy Use Analysis" link, get its href attribute, and go there
element = browser.find_element_by_xpath("//a[contains(@href,'LoadAnalysis')]")
ui_analysis_url = element.get_attribute("href")
logging.info('Getting Energy Use Analysis page...')
browser.get(ui_analysis_url)

# Find the Green Button image and click it
element = browser.find_element_by_xpath("//img[contains(@src,'images/GreenButton.jpg')]")
logging.debug('Clicking GreenButton...')
element.click()
handles = browser.window_handles
# Since clicking the Green Button opens a second window, switch to the second window
logging.debug('Switching to new window...')
browser.switch_to_window(handles[1])
element = browser.find_element_by_id('btnDownloadUsage')
logging.debug('Clicking btnDowloadUsage...')
element.click()
element = browser.find_element_by_id('lnkDownload')
logging.debug('Moving to lnkDownload...')
# We need to move to the element to make it visible
ActionChains(browser).move_to_element(element).perform()
# Having moved, we need to wait for the element to become visible before clicking it
try:
    logging.debug('Waiting for lnkDownload to become visible...')
    wait.until(expected_conditions.visibility_of(element))
    element.click()
    logging.debug("Successfully clicked lnkDownload.")
except:
    logging.error("Probable timeout waiting for lnkDownload to become visible.")
    browser.quit()
    sys.exit("Exiting.")

# PhantomJS can't download files.
# But clicking the element executes some JavaScript that changes the "href"
# attribute of the "lnkDownload".
# So here we get that attribute and download the file using requests.
element = browser.find_element_by_id('lnkDownload')
link = element.get_attribute('href')
logging.info('File location is ' + link)

# Save cookies for use by requests
logging.debug('Saving cookies from webdriver...')
cj = cookielib.CookieJar()
for cookie in browser.get_cookies():
    new_cookie = cookielib.Cookie(name=cookie['name'], 
                          value=urllib.unquote(cookie['value']), 
                          domain=cookie['domain'], 
                          path=cookie['path'], 
                          secure=cookie['secure'], 
                          rest={'HttpOnly': cookie['httponly']}, 
                          version=0, 
                          port=None,
                          port_specified=False, 
                          domain_specified=False,
                          domain_initial_dot=False,
                          path_specified=True,
                          expires=None,
                          discard=True,
                          comment=None,
                          comment_url=None,
                          rfc2109=False)
    logging.debug(new_cookie)
    cj.set_cookie(new_cookie)

# Download the file using requests and our saved cookies
logging.debug('Downloading file...')
r = requests.get(link, cookies=cj)
f = open(greenbutton_zipfile, 'wb')
f.write(r.content)
f.close()

logging.debug('Unzipping file...')
if zipfile.is_zipfile(greenbutton_zipfile) == True:        
    with zipfile.ZipFile(greenbutton_zipfile) as zf:
        try:
            zf_info = zf.infolist()
            if len(zf_info) == 1:
                greenbutton_xmlfile = zf_info[0].filename
                logging.debug("Found one file inside the ZIP file, named " + greenbutton_xmlfile)
                # Not bothering to see what kind of file we're actually extracting
                zf.extract(zf_info[0], working_dir)
            else:
                logging.error("Found more than one file inside the ZIP file. Don't know which file to extract.")
                sys.exit("Exiting.")            
        except zipfile.BadZipfile:
            logging.error("Error extracting ZIP file.")
            sys.exit("Exiting.")
else:
    logging.error("Not a ZIP file.")
    sys.exit("Exiting.")

logging.info('Parsing unzipped XML file...')
f = open(greenbutton_xmlfile, 'r')
xml = f.read()
logging.debug(xml)
soup = BeautifulStoneSoup(xml)
entries = soup.findAll('entry')

if len(entries) == 0:
    logging.error("No usage entries found in the XML file. This is probably not the right file.")
    sys.exit("Exiting.")

# Create lists of dates and values based on XML
# This is heavily dependent on the structure of this particular Green Button XML file
# It will likely break if the structure of the XML file changes at all
starts = []
timestamps = []
values = []
for entry in entries:
    if entry.title is not None and entry.title.contents[0] == u'Energy Usage':
        duration = entry.content.intervalblock.intervalreading.timeperiod.duration.contents[0]
        start = entry.content.intervalblock.intervalreading.timeperiod.start.contents[0]
        timestamp = datetime.fromtimestamp(int(start))
        value = int(entry.content.intervalblock.intervalreading.value.contents[0])
        starts.append(int(start))
        timestamps.append(timestamp)
        values.append(value)
        
f.close()

# Convert to kWh
values = numpy.array(values)
values = values / 1000
values_mean = average(values)
logging.info('Average: ' +  str(values_mean))
# Convert single mean to list for plotting purposes
values_mean = [values_mean] * len(values)

# Make a fitted line
timestamps_ts = [time.mktime(t.timetuple()) for t in timestamps]
m,b = polyfit(timestamps_ts, values, 1)
values_fitted = [m*x + b for x in timestamps_ts]

# Create a list of 12 colors, one for each month (Brewer colors)
month_colors = ['#a6cee3', '#1f78b4', '#b2df8a', '#33a02c',
          '#fb9a99', '#e31a1c', '#fdbf6f', '#ff7f00', 
          '#cab2d6', '#6a3d9a', '#ffff99', '#b15928']
bar_colors = [month_colors[t.month - 1] for t in timestamps]


# There's some weird indentation error going on here I can't figure out right now
if create_new_graph == 1:
    logging.info('Uploading new graph to Plotly...')
    py.sign_in(plotly_userid, plotly_password)
    
    bar1 = Bar(
               x=timestamps,
               y=values,
               marker=Marker(color=bar_colors),
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
                    xaxis=XAxis(title='Updated daily from smart meter (with several day lag)')
                    )

    fig = Figure(data=data, layout=layout)
    plot_url = py.plot(fig, filename='energy-usage', auto_open=False)
    logging.debug('Done uploading.')
else:
    logging.info('Not uploading a new graph.')

logging.info('Done.')