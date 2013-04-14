#Betashapes

	created by Melissa Santos and Schuyler Erle
	(c) 2011 SimpleGeo, Inc.

What is this?
-------------

It's the code used by SimpleGeo to generate its international neighborhood
dataset.

See the blog post for an explanation:

* [its-a-beautiful-day-in-the-neighborhood](http://blog.simplegeo.com/2011/08/05/its-a-beautiful-day-in-the-neighborhood/)

Why's it here?
--------------

We had fun writing it. We like giving stuff away. Maybe you'll find it useful.
Maybe you'll improve it and send us a pull request! We provide no warranty, and
no support. If it breaks, you get to keep the pieces.

How's it work?
--------------

Well, it helps if you download Yahoo's GeoPlanet dump, and load both it and all
or some subset of Planet.osm into PostGIS.

You'll need to create a data/ directory, and dump a mapping of WoE ID -> Name
into a file called `data/names.txt`, and another mapping of Parent ID, Name,
Type -> WoE ID into another file called `data/suburbs.txt`. This is stupid and
could be done a lot more cleanly.

Here is a sample of the names.txt we're using:

    29372661	San Francisco Javier
    772864	San Francisco de Paula
    108040	Villa de San Francisco
    142610	San Francisco Culhuacán
    349422	San Francisco de Limache
    12521721	San Francisco International Airport

Here's a sample of the suburbs.txt:

    44418	Streatham Common	Suburb	20089509
    44418	Upper Walthamstow	Suburb	20089365
    44418	Castelnau	Suburb	20089570
    44418	Harold Hill	Suburb	22483
    44418	Blackfriars Road	Suburb	20094299
    44418	Lampton	Suburb	44314
    44418	Lower Place	Suburb	20089447
    44418	Furzedown	Suburb	20089510
    44418	Crofton	Suburb	20089334
    44418	Collier's Wood	Suburb	20089517

Running build_neighborhood.sh takes over from there.

What's in it?
-------------

build_neighborhood.sh <city> <woeid>

    This shell script makes the magic happen. Depends on PostgreSQL and GRASS,
    in addition to all the other stuff in here.

blockr.py <names.txt> <blocks.json> <points.txt>

    The main neighborhood generation script. Takes a name file
    (tab-separated, mapping WoE ID to name), a GeoJSON FeatureCollection
    containing the block polygons to be assigned, and a points file (as
    generated by geocrawlr.py).

    Requires Shapely.

outliers.py <points.txt>

    A module for reading points.txt files and discarding outlying points based
    on median absolute distance. If run as a script, prints the bounding box of
    the points after outliers are discarded.

geocrawlr.py <woe_id> [<woe_id> ...]

    A script that crawls the Flickr API looking for geotagged photo records
    associated with the given woe_ids. Writes line-by-line, tab-separated
    values to stdout consisting of: Photo ID, WoE ID, Longitude, Latitude.
    Uses Flickr.API. You must have your FLICKR_KEY and FLICKR_SECRET set in the
    environment.

geoplanet.py

    A utility script to query Y! GeoPlanet. Takes names, one per line, on stdin,
    queries GeoPlanet, and outputs the first WoE ID and name returned on stdout.
    Set YAHOO_APPID in your environment.

mapnik_render.py

    A Mapnik script to visualize the neighborhood.json and blocks.json data
    together.

leaves_from_woeid.py

    Walks a table of GeoPlanet data in PostgreSQL and fetches all the leaves
    descending from a given WoE ID.


Usage:
-------

###San Francisco

Let's download a sampling of geocoded Flickr photos:

	grep ^2362930 data_berkeley/suburbs.txt | cut -f4 | xargs python geocrawlr.py > data_berkeley/photos_2362930.txt

Now let's vote by geography (assumes you have census geography file for city in GeoJSON format):

	python blockr.py data_berkeley/suburbs.txt data_berkeley/blocks_2362930.json data_berkeley/photos_2362930.txt > data_berkeley/berkeley2.json


What's a "betashape"?
---------------------

* [the shape of alpha](http://code.flickr.com/blog/2008/10/30/the-shape-of-alpha/)
* [living in the donut hole](http://code.flickr.com/blog/2009/01/12/living-in-the-donut-hole/)
* [flickr shapefiles public dataset 2.0](http://code.flickr.com/blog/2011/01/08/flickr-shapefiles-public-dataset-2-0/)

_Propers to Aaron Straup Cope for his ideas and encouragement._

License
-------

Copyright (c) 2011, SimpleGeo, Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of the SimpleGeo, Inc. nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL SIMPLEGEO, INC. BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
