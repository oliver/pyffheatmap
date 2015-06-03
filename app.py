#!/usr/bin/python

#
# Python Freifunk Heat Map
#


import os
import time
import datetime
import StringIO
import json
import csv
import tempfile
import re
import web

#web.config.debug = False


# file format constants
FILE_FORMAT_WIFI_LL_CSV = 1


db = web.database(dbn="sqlite", db="scanresults.db")
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

        scans = db.query("select *, (select count(*) from hotspots where scans.id = hotspots.scanid) as hscount, (select max(level) from hotspots where scans.id = hotspots.scanid) as maxlevel, (select group_concat(distinct ssid) from hotspots where scans.id = hotspots.scanid) as ssidnames, (select group_concat(bssid, ', ') from hotspots where scans.id = hotspots.scanid) as bssidnames from scans where scans.lon >= $west and scans.lon <= $east and scans.lat >= $south and scans.lat <= $north and hscount > 0",
            vars={"west": float(west), "east": float(east), "north": float(north), "south": float(south)})

        jsonData = []
        for row in scans:
            maxLevel = row["maxlevel"]
            desc = "%s: %s" % (row["ssidnames"], row["bssidnames"])

            point = {
                "lat": row["lat"],
                "lon": row["lon"],
                "quality": maxLevel+100,
                "text": desc,
            }
            jsonData.append(point)
        print "num points: %d" % len(jsonData)

        web.header("Content-Type", "application/json")
        return json.dumps(jsonData)


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
            (tempFd, tempPath) = tempfile.mkstemp(prefix="uploaded-%s-" % time.strftime("%Y%m%d-%H%M%S"), suffix=".bin", dir="/tmp/")
            print "writing uploaded data (%d bytes) to %s" % (len(contents), tempPath)
            fp = os.fdopen(tempFd, "wb")
            fp.write(contents)
            fp.close()

            try:
                # assume that uploaded files are in CSV format
                # TODO: detect file type
                (numLines, numBadLines) = self.parseWifiLLCSVFile(contents)
            except Exception, e:
                message = "error handling uploaded file (%s)" % e
            else:
                message = "file was uploaded (%d bytes); %d lines" % (len(contents), numLines)
                if numBadLines > 0:
                    message += "; %d lines were discarded due to errors" % numBadLines

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
        numLines = 0
        numBadLines = 0
        reader = csv.reader(StringIO.StringIO(s))
        for row in reader:
            numLines+=1
            #print row
            if len(row) != 16 or row[1] != "1":
                print "invalid data in line %d (num columns: %d; format version: '%s')" % (reader.line_num, len(row), row[1])
                numBadLines+=1
                continue

            try:
                (timestampDt, formatVersion, deviceModel, sessionId, lat, lon, alt, accuracy, speed, specialCode, timeSinceLastLocUpdate, ssid, bssid, signalLevel, channel, filterRE) = self.parseRowData(row)
            except Exception, e:
                print "invalid data in line %d (%s)" % (reader.line_num, e)
                numBadLines+=1
                continue

            if not(fileId):
                fileId = db.insert("files", sessionid=sessionId, upload_date=datetime.datetime.now(), format=FILE_FORMAT_WIFI_LL_CSV, formatversion=int(formatVersion), device=deviceModel)

            newScan = {
                "ts": timestampDt,
                "lat": lat,
                "lon": lon,
                "alt": alt,
                "accuracy": accuracy,
            }

            if newScan != currentScan:
                # create new scan entry
                if currentScan["ts"] is not None:
                    # save old scan entry first
                    addScan(fileId, currentScan, currentHotspots)
                currentScan = newScan
                currentHotspots = []

            if specialCode == 0 and ssid.find("freifunk") != -1: # row actually contains a hotspot, and it's a FF node
                currentHotspots.append( (ssid, bssid, channel, signalLevel) )

        # save last scan entry
        if currentScan["ts"] is not None:
            addScan(fileId, currentScan, currentHotspots)

        transaction.commit()

        return (numLines, numBadLines)

    def parseRowData (self, row):
        (timestamp, formatVersion, deviceModel, sessionId, lat, lon, alt, accuracy, speed, specialCode, timeSinceLastLocUpdate, ssid, bssid, signalLevel, channel, filterRE) = row

        dotPos = timestamp.rindex(".")
        timestampDt = datetime.datetime.strptime(timestamp[:dotPos], "%Y-%m-%d %H:%M:%S")

        if formatVersion != "1": raise Exception("bad formatVersion")
        formatVersion = int(formatVersion)

        deviceModel = deviceModel[:50].decode("utf-8", "replace")

        sessionId = sessionId[:50].decode("utf-8", "replace")

        lat = float(lat)
        lon = float(lon)
        alt = float(alt)
        accuracy = float(accuracy)
        speed = float(speed)

        if specialCode != "0" and specialCode != "1": raise Exception("bad specialCode")
        specialCode = int(specialCode)

        timeSinceLastLocUpdate = int(timeSinceLastLocUpdate)

        if specialCode == 1: # no AP found; following values should be empty anyway:
            ssid = ""
            bssid = ""
            signalLevel = 0
            channel = 0
        else:
            ssid = ssid[:50].decode("utf-8", "replace")

            bssid = bssid[:17]
            if not(re.match(r"^[0-9a-fA-F:]*$", bssid)): raise Exception("bad bssid '%s'" % bssid)

            signalLevel = int(signalLevel)

            channel = int(channel)

        filterRE = filterRE[:50].decode("utf-8", "replace")

        return (timestampDt, formatVersion, deviceModel, sessionId, lat, lon, alt, accuracy, speed, specialCode, timeSinceLastLocUpdate, ssid, bssid, signalLevel, channel, filterRE)

if __name__ == "__main__":
    app.run()
