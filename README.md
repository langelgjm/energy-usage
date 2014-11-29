energy-usage
============

[United Illimunating](http://en.wikipedia.org/wiki/The_United_Illuminating_Company) (UI) is my local electricity company. They have deployed smart meters to customers, and make daily usage information available to account holders online. While they provide some rudimentary graphing tools, you can also export your data in CSV or XML formats.

This Python script automates the login process to a United Illuminating utility account, and fetches the historical usage data in XML format. The XML data is in a standardized schema called [Green Button](http://www.greenbuttondata.org/), which in theory allows authorized third-party applications to connect to utilities and access customer data.

The script parses the XML data and plots the output on [plot.ly](http://plot.ly), a free online service for developing interactive graphs and visualizations.

To use the script, clone this repository, add your configuration details (login credentials and PhantomJS path) to config.txt, and run. I have my own setup run this script once a day as a cron job; you can see the output [here](https://plot.ly/~langelgjm/2/electricity-usage/).

In order to run the script, you'll need to be a UI customer, and have both Python and [PhantomJS](http://phantomjs.org/) installed. Tested with Python 2.7.8 and PhantomJS 1.9.8 on Mac OS X and Ubuntu Linux.
