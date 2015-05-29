#!/usr/bin/python

#
# Python Freifunk Heat Map
#


import datetime
import web

#web.config.debug = False


# file format constants
FILE_FORMAT_WIFI_LL_CSV = 1


render = web.template.render("templates/")
db = web.database(dbn="sqlite", db="test1.db")

urls = (
    "/", "Index",
    "/upload", "Upload",
    "/map", "Map",
    "/mapdata/(.+)/(.+)/(.+)/(.+)", "MapData",
    )

app = web.application(urls, globals())

class Index:
    def GET(self):
        return render.index()


class Map:
    def GET(self):
        return render.mapview()


class MapData:
    def GET(self, west, east, north, south):

        scans = db.query("select * from scans where scans.lon >= $west and scans.lon <= $east and scans.lat >= $south and scans.lat <= $north limit 300",
            vars={"west": float(west), "east": float(east), "north": float(north), "south": float(south)})

        geojson = {
            "type": "FeatureCollection",
            "features": []
        }

        numRows = 0
        for row in scans:
            hotspots = db.query("select * from hotspots where scanid = $scanid",
                vars={"scanid": row["id"]})

            ssids = [ h["ssid"] for h in hotspots ]
            if ssids:
                desc = ("%d: " % len(ssids)) + (", ".join(ssids))
            else:
                desc = "(no hotspots)"

            feat = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [ row["lon"], row["lat"] ]
                },
                "properties": {
                    "text": desc,
                }
            }
            geojson["features"].append(feat)
            numRows+=1

        print "numRows: %d" % numRows

        import json
        web.header("Content-Type", "application/json")
        return json.dumps( geojson )


class Upload:
    def GET(self):
        return render.upload("")

    def POST(self):
        #values = web.input(f={})
        values = web.input()

        if len(values.keys()) != 1:
            # there must be exactly one form field in the request
            raise web.webapi.BadRequest()

        for key in values:
            contents = values[key]

        if not(contents):
            message = "ignoring empty file."
        else:
            try:
                self.handleFileContents(contents)
            except Exception, e:
                message = "error handling uploaded file (%s)" % e
            else:
                message = "file was uploaded (%d bytes)!" % len(contents)

        print "message: '%s'" % message
        #raise web.seeother("/finished")

        return render.upload(message)

    def handleFileContents(self, s):
        # for debugging:
        fd = open("/tmp/uploaded.bin", "wb")
        fd.write(s)
        fd.close()

        # assume that uploaded files are in CSV format
        # TODO: detect file type

        def check(condition):
            "helper function for easily performing validation checks on the file contents"
            if not(condition):
               raise Exception("file is invalid")

        import csv
        import StringIO
        reader = csv.reader(StringIO.StringIO(s))

        t = db.transaction()

        # data of "current" scan (used for cumulating multiple hotspots at same location into single scan entry):
        currentScan = {
            "ts": None,
            "lat": None,
            "lon": None,
            "alt": None,
            "accuracy": None
        }
        currentHotspots = []

        def addScan(fileId, scan, hotspots):
            scanId = db.insert("scans", fileid=fileId, scantime=scan["ts"], lat=scan["lat"], lon=scan["lon"], alt=scan["alt"], accuracy=scan["accuracy"])
            for h in hotspots:
                db.insert("hotspots", scanid=scanId, ssid=h[0], bssid=h[1], channel=h[2], level=h[3])

        fileId = None
        for row in reader:
            #print row
            check(len(row) == 16)
            check(row[1] == "1") # format version

            (timestamp, formatVersion, deviceModel, sessionId, lat, lon, alt, accuracy, speed, specialCode, timeSinceLastLocUpdate, ssid, bssid, signalLevel, channel, filterRE) = row

            if not(fileId):
                fileId = db.insert("files", sessionid=sessionId, upload_date=datetime.datetime.now(), format=FILE_FORMAT_WIFI_LL_CSV, formatversion=int(formatVersion), device=deviceModel)
                print "fileId: %s" % fileId

            dotPos = timestamp.rindex(".")
            timestampDt = datetime.datetime.strptime(timestamp[:dotPos], "%Y-%m-%d %H:%M:%S")

            newScan = {
                "ts": timestampDt,
                "lat": float(lat),
                "lon": float(lon),
                "alt": float(alt),
                "accuracy": float(accuracy),
            }

            if newScan != currentScan:
                # create new scan entry
                if currentScan["ts"] is not None:
                    # save old scan entry first
                    addScan(fileId, currentScan, currentHotspots)
                currentScan = newScan
                currentHotspots = []
            else:
                # add to previous scan entry
                if int(specialCode) == 0: # row actually contains a hotspot
                    currentHotspots.append( (ssid, bssid, int(channel), int(signalLevel)) )

        # save last scan entry
        if currentScan["ts"] is not None:
            addScan(fileId, currentScan, currentHotspots)

        t.commit()

if __name__ == "__main__":
    app.run()

