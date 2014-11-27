from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime
import time
import plotly.plotly as py
from plotly.graph_objs import Bar, Scatter, Data, Layout, XAxis, YAxis, Figure, Marker
#from plotly.graph_objs import *
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
import ConfigParser

###############################################################################

# Define the logging level; choose DEBUG or INFO for more detailed output
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

# Change to the working directory, which is the directory of the script
pathname = os.path.dirname(sys.argv[0])
working_dir = os.path.abspath(pathname)
try:
    os.chdir(working_dir)
except:
    logging.error("Couldn't change to script directory.")
    sys.exit("Exiting.")

# Create a ConfigParser and read the configuration file
config_file = 'config.txt'
config = ConfigParser.ConfigParser()
try:
    with open(config_file) as f:
        config.readfp(f)
except IOError:
    logging.error("Couldn't open configuration file.")
    sys.exit("Exiting.")

def config_dict(section):
    dict1 = {}
    options = config.options(section)
    for option in options:
        try:
            dict1[option] = config.get(section, option)
        except:
            logging.info("Configuration exception for option %s." % option)
            dict1[option] = None
    return dict1

# Create two configuration dictionaries for our use
config_secrets = config_dict('secrets')
config_general = config_dict('general')

ui_url = 'https://www.uinet.com'
ui_myacct_url = 'https://www.uinet.com/wps/myportal/uinet/myaccount/accounthome/dashboard'
# Used to save the downloaded ZIP file
greenbutton_zipfile = 'greenbutton.zip'

# You should define your PhantomJS executable location in config.txt
phantom_js = config_general['phantom_js']
# But if you don't we'll try to find it
if phantom_js == '':
    phantom_js = spawn.find_executable("phantom_js")
    if phantom_js is None:
        logging.error("No PhantomJS path set, and none found automatically.")
        #sys.exit("Exiting.")
    else:
        logging.info("No PhantomJS path set, but found at " + phantom_js)

###############################################################################

# Create browser instance and set timeouts
browser = webdriver.PhantomJS(phantom_js)
browser.implicitly_wait(10)
wait = WebDriverWait(browser, 10)

# Sign in to UI site
print('Logging into ' + ui_url + '...')
browser.get(ui_url)
username = browser.find_element_by_name('userid')
password = browser.find_element_by_name('password')
username.send_keys(config_secrets['ui_userid'])
password.send_keys(config_secrets['ui_password'])
password.submit()

# Traverse pages and elements to obtain Green Button ZIP file
# This section is likely to break when the page design or layout changes
print('Getting My Account page...')
browser.get(ui_myacct_url)
# Find the EnergyGuide frame and switch to it
element = browser.find_element_by_xpath("//iframe[contains(@src,'energyguide.com')]")
browser.switch_to_frame(element)
# Find the "Energy Use Analysis" link, get its href attribute, and go there
element = browser.find_element_by_xpath("//a[contains(@href,'LoadAnalysis')]")
ui_analysis_url = element.get_attribute("href")
print('Getting Energy Use Analysis page...')
browser.get(ui_analysis_url)

# Find the Green Button image and click it
element = browser.find_element_by_xpath("//img[contains(@src,'images/GreenButton.jpg')]")
logging.info('Clicking GreenButton...')
element.click()
handles = browser.window_handles
# Since clicking the Green Button opens a second window, switch to the second window
logging.info('Switching to new window...')
browser.switch_to_window(handles[1])
element = browser.find_element_by_id('btnDownloadUsage')
logging.info('Clicking btnDowloadUsage...')
element.click()
element = browser.find_element_by_id('lnkDownload')
logging.info('Moving to lnkDownload...')
# We need to move to the element to make it visible
ActionChains(browser).move_to_element(element).perform()
# Having moved, we need to wait for the element to become visible before clicking it
try:
    logging.info('Waiting for lnkDownload to become visible...')
    wait.until(expected_conditions.visibility_of(element))
    element.click()
    logging.info("Successfully clicked lnkDownload.")
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
print('File location is ' + link)

# Save cookies for use by requests
logging.info('Saving cookies from webdriver...')
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
logging.info('Downloading file...')
r = requests.get(link, cookies=cj)
f = open(greenbutton_zipfile, 'wb')
f.write(r.content)
f.close()

browser.quit()

###############################################################################

logging.info('Unzipping file...')
if zipfile.is_zipfile(greenbutton_zipfile):        
    with zipfile.ZipFile(greenbutton_zipfile) as zf:
        try:
            zf_info = zf.infolist()
            if len(zf_info) == 1:
                greenbutton_xmlfile = zf_info[0].filename
                logging.info("Found one file inside the ZIP file, named " + greenbutton_xmlfile)
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

###############################################################################

print('Parsing unzipped XML file...')
f = open(greenbutton_xmlfile, 'r')
xml = f.read()
soup = BeautifulStoneSoup(xml)
entries = soup.findAll('entry')

if len(entries) == 0:
    logging.error("No usage entries found in the XML file. This is probably not the right file.")
    sys.exit("Exiting.")

# Create dictionary whose keys are timestamps and whose values are daily usage values 
# corresponding to the duration associated with that timestamp
# This file appears to always have durations of 86400 seconds (one day), but I check 
# it and exit if that's not true, since it will screw everything else up.
# This is heavily dependent on the structure of this particular Green Button XML file
# It will likely break if the structure of the XML file changes at all
energyusage = {}

for entry in entries:
    if entry.title is not None and entry.title.contents[0] == u'Energy Usage':
        duration = int(entry.content.intervalblock.intervalreading.timeperiod.duration.contents[0])
        if duration != 86400:
            logging.error("Found a duration other than 1 day, which I can't handle.")
            sys.exit("Exiting.")
        start = entry.content.intervalblock.intervalreading.timeperiod.start.contents[0]
        timestamp = datetime.fromtimestamp(int(start))
        value = int(entry.content.intervalblock.intervalreading.value.contents[0])
        energyusage.update({timestamp:value})
        
f.close()

###############################################################################

# Convert to kWh
for k in energyusage:
    energyusage[k] = energyusage[k] / 1000

# Generate mean and fit (simply linear regression) lines for each month.
# Do this by creating dictionaries whose keys are month/years tuples
# And whose values are (x,y) coordinate tuples, where x is a datetime 
# and y is the value (mean or fitted value, respectively)
month_mean_dict = {}
month_fit_dict = {}

for m,y in list(set([(k.month,k.year) for k in energyusage])):
    # Get the x values (timestamps) in order for dates that are in this month/year tuple
    timestamps = sorted([n for n in energyusage if (n.month,n.year) == (m,y)])
    # Get the average of each energyusage value whose keys are in the timestamps
    month_average = average([energyusage[n] for n in timestamps])
    # Update the mean lines dictionary with a tuple of the timestamp (x) and average (y)
    month_mean_dict.update({(m,y):[(n,month_average) for n in timestamps]})
    # For fitting, get the y values in order (based on the ordered timestamps created above)
    values = [energyusage[n] for n in timestamps]
    # convert the x values (timestamps) to UNIX times so that polyfit has numbers to work with
    timestamps_ts = [time.mktime(t.timetuple()) for t in timestamps]
    # Get the slope and intercept based on the x and y values
    em,be = polyfit(timestamps_ts, values, 1)
    # Make a list of fitted values based on the slope, intercept, and timestamps
    # y value is the fitted value, x value is the timestamp as datetime (not UNIX time)
    # Details: convert epoch to localtime, convert localtime to datetime (first 6 of tuple)
    # Store it in a dictionary with the month/year tuple as the key
    month_fit_dict.update({(m,y):[(datetime(*time.localtime(x)[:6]),em*x + be) for x in timestamps_ts]})

print('Average monthly values: ' +  str(month_mean_dict))
print('Fitted monthly values: ' + str(month_fit_dict))

# Three alternating colors to provide contrast month to month
month_colors = ['#7fc97f','#beaed4','#fdc086']
# Mean colors are slightly darker
mean_colors = ['#4daf4a', '#984ea3', '#ff7f00']
# Remember to use the sorted keys, otherwise colors will be out of order
timestamps = sorted([k for k in energyusage])
bar_colors = [month_colors[k.month % 3] for k in timestamps]

###############################################################################

if config.getboolean('general', 'upload_graph'):
    print('Uploading new graph to Plotly...')
    py.sign_in(config_secrets['plotly_userid'], config_secrets['plotly_password'])
    #
    bar1 = Bar(x=timestamps,
               y=[energyusage[t] for t in timestamps],
               marker=Marker(color=bar_colors),
               name='Daily',
               showlegend=False)
    bar1_mobile = Bar(y=timestamps,
               x=[energyusage[t] for t in timestamps],
		orientation='h',
               marker=Marker(color=bar_colors),
               name='Daily',
               showlegend=False)
    # Loop through the mean lines dictionary, creating a mean line for each month/year tuple
    mean_lines = []
    for mo,ye in month_mean_dict:
        # Use the ordered timestamps list created earlier; order matters for plotting
        # Return the indices of timestamps that match the current month/year tuple
        x,y = zip(*month_mean_dict[mo,ye])
        x = list(x)
        y = list(y)
        mean_line = Scatter(x=x, 
                            y=y, 
                            mode='lines',
                            # Get the friendly month name
                            name=datetime(ye,mo,1,1,1,1).strftime("%b %Y") + ' Mean',
                            # Make sure it's the same color as the month
                            marker=Marker(color=mean_colors[mo % 3]),
                            showlegend=False
                            )
        mean_lines.append(mean_line)
    # Loop through the fit lines dictionary, creating a fit line for each month/year tuple
    fit_lines = []
    for mo,ye in month_fit_dict:
        x,y = zip(*month_fit_dict[mo,ye])
        x = list(x)
        y = list(y)
        fit_line = Scatter(x=x,
                           y=y,
                            mode='lines',
                            # Get the friendly month name
                            name=datetime(ye,mo,1,1,1,1).strftime("%b %Y") + ' Trend',
                            # Make sure it's the same color as the month
                            marker=Marker(color=mean_colors[mo % 3]),
                            showlegend=False
                            )
        fit_lines.append(fit_line)
    #
    data = Data([bar1] + mean_lines + fit_lines)
    data_mobile = Data([bar1_mobile])
    #
    layout = Layout(
                    title='Electricity Usage',
                    yaxis=YAxis(title='kWh consumed in prior 24 hour period'),
                    xaxis=XAxis(title='Updated daily from my smart meter (with several day lag)')
                    )
    layout_mobile = Layout(
                    title='Electricity Usage',
                    xaxis=XAxis(title='kWh')
                    )
    #
    fig = Figure(data=data, layout=layout)
    fig_mobile = Figure(data=data_mobile, layout=layout_mobile)
    plot_url = py.plot(fig, filename='energy-usage', auto_open=False)
    plot_url = py.plot(fig_mobile, filename='energy-usage-mobile', auto_open=False)
    logging.info('Done uploading.')
else:
    print('Not uploading a new graph.')

###############################################################################

print('Done.')
