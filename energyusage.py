from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime
import time
import plotly.plotly as py
from plotly.graph_objs import Bar, Scatter, Data, Layout, XAxis, YAxis, Figure, Marker
from numpy import average, polyfit
import os
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
import zipfile
import requests
import cookielib, urllib
import sys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from distutils import spawn
import ConfigParser
from retrying import retry

###############################################################################
def create_config_dict(config, section):
    "Returns a configuration dictionary for a given section, using a ConfigParser instance"
    d = {}
    options = config.options(section)
    for option in options:
        try:
            d[option] = config.get(section, option)
        except:
            print("Configuration exception for option %s." % option)
            d[option] = None
    return d

def get_config(config_file):
    "Return a dictionary of configuration options from the configuration file"
    # Create a ConfigParser instance
    config = ConfigParser.ConfigParser()
    # Try to read the configuration file
    try:
        with open(config_file) as f:
            config.readfp(f)
    except IOError:
        print("Couldn't open configuration file.")
        sys.exit("Exiting.")
    # Create an empty configuration dictionary, then update it with details
    # from the ConfigParser instance
    config_dict = {}
    config_dict.update(create_config_dict(config, 'secrets'))
    config_dict.update(create_config_dict(config, 'general'))
    # Change the natural language boolean to an actual boolean value
    config_dict['upload_graph'] = config.getboolean('general', 'upload_graph')
    return config_dict
    
def configure(config_dict):
    "Establish initial configuration"
    # You should define your PhantomJS executable location in config.txt
    phantom_js = config_dict['phantom_js']
    # But if you don't we'll try to find it
    if phantom_js == '':
        phantom_js = spawn.find_executable("phantomjs")
        if phantom_js is None:
            print("No PhantomJS path set, and none found automatically.")
            #sys.exit("Exiting.")
        else:
            print("No PhantomJS path set, but found at " + phantom_js)

# Retry our request up to x=5 times, waiting 2^x * 1 minute after each retry
@retry(stop_max_attempt_number=5, wait_exponential_multiplier=60000)
def pyplot(fig, name):
    "py.plot with retrying. Pass in a figure and a name, returns a url."
    return py.plot(fig, filename=name, auto_open=False)

# Retry creating the webdriver instance up to 3 times, with 2 minute intervals
# Occasionally selenium randomly can't connect to phantomjs, and throws a WebDriverException
@retry(stop_max_attempt_number=3, wait_fixed=120000)
def create_webdriver(config_dict):
    "Returns a webdriver instance using the phantomjs driver; retries on exceptions."
    return webdriver.PhantomJS(config_dict['phantom_js'])

def download_file(config_dict, browser):
    "Download the Green Button zip file."
    # Set up some waits
    browser.implicitly_wait(10)
    wait = WebDriverWait(browser, 10)
    # Sign in to UI site
    print('Logging into ' + config_dict['ui_url'] + '...')
    browser.get(config_dict['ui_url'])
    username = browser.find_element_by_name('userid')
    password = browser.find_element_by_name('password')
    username.send_keys(config_dict['ui_userid'])
    password.send_keys(config_dict['ui_password'])
    password.submit()
    # Traverse pages and elements to obtain Green Button ZIP file
    # This section is likely to break when the page design or layout changes
    print('Getting My Account page...')
    browser.get(config_dict['ui_myacct_url'])
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
    print('Clicking GreenButton...')
    element.click()
    handles = browser.window_handles
    # Since clicking the Green Button opens a second window, switch to the second window
    print('Switching to new window...')
    browser.switch_to_window(handles[1])
    element = browser.find_element_by_id('btnDownloadUsage')
    print('Clicking btnDowloadUsage...')
    element.click()
    element = browser.find_element_by_id('lnkDownload')
    print('Moving to lnkDownload...')
    # We need to move to the element to make it visible
    ActionChains(browser).move_to_element(element).perform()
    # Having moved, we need to wait for the element to become visible before clicking it
    try:
        print('Waiting for lnkDownload to become visible...')
        wait.until(expected_conditions.visibility_of(element))
        element.click()
        print("Successfully clicked lnkDownload.")
    except:
        print("Probable timeout waiting for lnkDownload to become visible.")
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
    print('Saving cookies from webdriver...')
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
        print(new_cookie)
        cj.set_cookie(new_cookie)
    # Download the file using requests and our saved cookies
    print('Downloading file...')
    r = requests.get(link, cookies=cj)
    f = open(config_dict['greenbutton_zipfile'], 'wb')
    f.write(r.content)
    f.close()
    browser.quit()

def unzip_file(config_dict, working_dir):
    "Unzips the zipfile and returns the name of the XML file inside"
    print('Unzipping file...')
    if zipfile.is_zipfile(config_dict['greenbutton_zipfile']):        
        with zipfile.ZipFile(config_dict['greenbutton_zipfile']) as zf:
            try:
                zf_info = zf.infolist()
                if len(zf_info) == 1:
                    greenbutton_xmlfile = zf_info[0].filename
                    print("Found one file inside the ZIP file, named " + greenbutton_xmlfile)
                    # Not bothering to see what kind of file we're actually extracting
                    zf.extract(zf_info[0], working_dir)
                    return greenbutton_xmlfile
                else:
                    print("Found more than one file inside the ZIP file. Don't know which file to extract.")
                    sys.exit("Exiting.")            
            except zipfile.BadZipfile:
                print("Error extracting ZIP file.")
                sys.exit("Exiting.")
    else:
        print("Not a ZIP file.")
        sys.exit("Exiting.")

def parse_xml(greenbutton_xmlfile):
    "Parses the Green Button XML file and returns the parsed data in a dictionary."
    # Assumes 24 hour durations.
    # Does not account for varying interval start times, so sum totals will be incorrect
    print('Parsing unzipped XML file...')
    f = open(greenbutton_xmlfile, 'r')
    xml = f.read()
    soup = BeautifulStoneSoup(xml)
    entries = soup.findAll('entry')
    if len(entries) == 0:
        print("No usage entries found in the XML file. This is probably not the right file.")
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
                print("Found a duration other than 1 day, which I can't handle.")
                sys.exit("Exiting.")
            start = entry.content.intervalblock.intervalreading.timeperiod.start.contents[0]
            dt = datetime.fromtimestamp(int(start))
            value = int(entry.content.intervalblock.intervalreading.value.contents[0])
            energyusage.update({dt:value})
            print str(dt), value
    f.close()
    return energyusage

def analyze_data(energyusage):
    "Returns various dictionaries and lists of analyzed data"
    # Convert to kWh
    for k in energyusage:
        energyusage[k] = energyusage[k] / 1000
    #
    # Generate mean and fit (simply linear regression) lines for each month.
    # Do this by creating dictionaries whose keys are month/years tuples
    # And whose values are (x,y) coordinate tuples, where x is a datetime 
    # and y is the value (mean or fitted value, respectively)
    month_mean_dict = {}
    month_fit_dict = {}
    #
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
    #
    #print('Average monthly values: ')
    #print('Fitted monthly values: ')
    #
    # Three alternating colors to provide contrast month to month
    month_colors = ['#7fc97f','#beaed4','#fdc086']
    # Mean colors are slightly darker
    mean_colors = ['#4daf4a', '#984ea3', '#ff7f00']
    # Remember to use the sorted keys, otherwise colors will be out of order
    timestamps = sorted([k for k in energyusage])
    bar_colors = [month_colors[k.month % 3] for k in timestamps]
    return month_mean_dict, month_fit_dict, timestamps, month_colors, mean_colors, bar_colors

def create_graphs(config_dict, energyusage, month_mean_dict, month_fit_dict, timestamps, month_colors, mean_colors, bar_colors):
    "Creates desktop and mobile plotly graphs, if desired. Returns the URLs."
    if config_dict['upload_graph']:
        print('Uploading new graphs to Plotly...')
        py.sign_in(config_dict['plotly_userid'], config_dict['plotly_apikey'])
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
        url1 = pyplot(fig, 'energy-usage')
        url2 = pyplot(fig_mobile, 'energy-usage-mobile')
        print('Done uploading.')
        print('Desktop graph available at ' + url1)
        print('Mobile graph available at ' + url2)
        return url1, url2
    else:
        print('Not uploading a new graph.')
        return None

def main():
    # Change to the working directory, which is the directory of the script
    pathname = os.path.dirname(sys.argv[0])
    working_dir = os.path.abspath(pathname)
    try:
        os.chdir(working_dir)
    except:
        print("Couldn't change to script directory.")
        sys.exit("Exiting.")
    # Get configuration options
    config_dict = get_config('config.txt')
    # Do initial setup using these options
    configure(config_dict)
    # Create browser instance and set timeouts
    browser = create_webdriver(config_dict)
    # Downloads the file and closes the browser
    download_file(config_dict, browser)
    # Unzips the zipfile and gets the name of the XML file inside
    greenbutton_xmlfile = unzip_file(config_dict, working_dir)
    # Parse the XML
    energyusage = parse_xml(greenbutton_xmlfile)
    # Analyze the data and get the results
    month_mean_dict, month_fit_dict, timestamps, month_colors, mean_colors, bar_colors = analyze_data(energyusage)
    # Create graphs, if desired, using these results
    create_graphs(config_dict, energyusage, month_mean_dict, month_fit_dict, timestamps, month_colors, mean_colors, bar_colors)
    print('Done.')
    # TODO: add function to delete XML files based on a configuration option

if __name__ == "__main__":
    main()