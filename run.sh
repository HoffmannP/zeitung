#!/bin/sh

docker run \
	--name OTZcouch \
	-v /home/couchdb/data:/opt/Zeitung/data \
	-e COUCHDB_USER=admin \
	-e COUCHDB_PASSWORD=otz \
	couchdb
