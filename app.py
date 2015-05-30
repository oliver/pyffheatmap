#!/usr/bin/python

#
# Python Freifunk Heat Map
#


import datetime
import StringIO
import json
import csv
import web

#web.config.debug = False


# file format constants
FILE_FORMAT_WIFI_LL_CSV = 1


db = web.database(dbn="sqlite", db="test1.db")
render = web.template.render("templates/")

urls = (
    "/", "Index",
    "/map", "Map",
    "/mapdata/(.+)/(.+)/(.+)/(.+)", "MapData",
    "/upload", "Upload",
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

        scans = db.query("select * from scans where scans.lon >= $west and scans.lon <= $east and scans.lat >= $south and scans.lat <= $north",
            vars={"west": float(west), "east": float(east), "north": float(north), "south": float(south)})

        geojson = {
            "type": "FeatureCollection",
            "features": []
        }

        numRows = 0
        for row in scans:
            hotspots = db.query("select * from hotspots where scanid = $scanid",
                vars={"scanid": row["id"]})

            hotspots = list(hotspots)
            maxLevel = max( [-1000] + [ h["level"] for h in hotspots] )

            ssids = [ h["ssid"] for h in hotspots ]
            if ssids:
                desc = ("%d: " % len(ssids)) + (", ".join(ssids))
            else:
                desc = "(no hotspots)"
                continue

            feat = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [ row["lon"], row["lat"] ]
                },
                "properties": {
                    "quality": maxLevel+100,
                    "text": desc,
                }
            }
            geojson["features"].append(feat)
            numRows+=1

        print "numRows: %d" % numRows

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
            # save raw file contents for debugging:
            fd = open("/tmp/uploaded.bin", "wb")
            fd.write(contents)
            fd.close()

            try:
                # assume that uploaded files are in CSV format
                # TODO: detect file type
                self.parseWifiLLCSVFile(contents)
            except Exception, e:
                message = "error handling uploaded file (%s)" % e
            else:
                message = "file was uploaded (%d bytes)!" % len(contents)

        #raise web.seeother("/finished")
        return render.upload(message)

    def parseWifiLLCSVFile(self, s):
        "read WifiLocationLogger CSV file (version 1) and add contents to database"

        transaction = db.transaction()

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
        reader = csv.reader(StringIO.StringIO(s))
        for row in reader:
            #print row
            if len(row) != 16 or row[1] != "1":
                print "invalid data in line %d (num columns: %d; format version: '%s')" % (reader.line_num, len(row), row[1])
                continue

            (timestamp, formatVersion, deviceModel, sessionId, lat, lon, alt, accuracy, speed, specialCode, timeSinceLastLocUpdate, ssid, bssid, signalLevel, channel, filterRE) = row

            if not(fileId):
                fileId = db.insert("files", sessionid=sessionId, upload_date=datetime.datetime.now(), format=FILE_FORMAT_WIFI_LL_CSV, formatversion=int(formatVersion), device=deviceModel)

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

            if int(specialCode) == 0 and ssid.find("freifunk") != -1: # row actually contains a hotspot, and it's a FF node
                currentHotspots.append( (ssid.decode("utf-8", "replace"), bssid, int(channel), int(signalLevel)) )

        # save last scan entry
        if currentScan["ts"] is not None:
            addScan(fileId, currentScan, currentHotspots)

        transaction.commit()


if __name__ == "__main__":
    app.run()
