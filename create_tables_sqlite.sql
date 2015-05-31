
--
-- create necessary tables in sqlite DB
--

drop table if exists files;
drop table if exists scans;
drop table if exists hotspots;

-- rename "files" to "sessions"? or "uploads"?
create table files (
    id INTEGER PRIMARY KEY,
    sessionid char,
    hash char,
    upload_date datetime,
    format INTEGER,
    formatversion INTEGER,
    device char, -- model name of device used to create this file
    creator char -- name of application used to create this file
);


create table scans (
    id INTEGER PRIMARY KEY,
    fileid INTEGER not null,
    scantime datetime,
    lat double,
    lon double,
    alt double, -- altitude in meters (TODO: above what?)
    accuracy double -- accuracy in meters
);


create table hotspots (
    scanid INTEGER not null,
    ssid char,
    bssid char,
    channel INTEGER, -- wifi channel (TODO: how to represent eg. 5035 MHz, which is channel 7 in 5GHz band?)
    level INTEGER -- signal level, in dBm
);
