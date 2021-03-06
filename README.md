# Python FreiFunk Heat Map #
Web application for showing reception of [Freifunk](http://freifunk.net) wifi nodes on a map.

Data is gathered using [WifiLocationLogger](https://github.com/tjanson/WifiLocationLogger) running under an Android, and is then displayed on a map.

**This software is currently insecure and nearly untested. Do not run the server on the public internet. Do not use it for valuable data.**

## Getting Started ##
* [download](https://github.com/oliver/pyffheatmap/archive/master.zip) or checkout the sources
* run `sqlite3 scanresults.db < create_tables_sqlite.sql` to create database tables
* run `./app.py` to start web application
* visit [127.0.0.1:8080](http://127.0.0.1:8080/) for the overview page
* to add some test data, visit [127.0.0.1:8080/upload](http://127.0.0.1:8080/upload) and upload the `example-wifill.csv` file (it will add a single scan result)
* to view uploaded data, visit [127.0.0.1:8080/map](http://127.0.0.1:8080/map)

To upload own data, use WifiLocationLogger to gather some logs. Then change the Server URL in the app to the URL of your upload page (use the actual hostname of your computer), which looks something like this: http://*myhostname*:8080/upload and upload logs from the app.

For debugging, uploaded data is also stored in `/tmp/uploaded.bin` so that you can save a copy of the raw data. The database only contains the data which is actually needed for the map.

## Open Points ##

* the current heat map is basically wrong. It incorrectly takes the number of measurements into account, which means that you will see a huge red blob in places where you made many measurements. Instead, it should actually only take the reception level into account.

The whole project is an experimental prototype, to allow development of suitable visualizations of wifi reception for Freifunk projects, and to act as server for new wifi reception measurement tools. You are encouraged to add new map features or to add support for new upload formats!

## Third-Party Components ##
This application builds upon several existing components.
For the following components the (minified) source code is being delivered together with this project (in the `/static` subdirectory):

* [jQuery](http://jquery.org): MIT license
* [Leaflet](http://leafletjs.com): BSD license
* [PruneCluster](http://github.com/SINTEF-9012/PruneCluster): MIT license
* [Heatmap.js and Leaflet-Heatmap](http://patrick-wied.at/static/heatmapjs): MIT license
* [D3.js](http://d3js.org): BSD license
* [D3-hexbin](http://github.com/d3/d3-plugins/tree/master/hexbin): BSD license
* [Leaflet-D3](http://github.com/Asymmetrik/leaflet-d3): MIT license
