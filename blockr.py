import sys, os
from optparse import OptionParser
import math, pickle
import csv, json, geojson

from rtree import Rtree

from shapely.geometry import Point, Polygon, MultiPolygon, asShape
from shapely.geometry.polygon import LinearRing
from shapely.ops import cascaded_union, polygonize
from shapely.prepared import prep

from outliers import load_points, discard_outliers

SAMPLE_SIZE = 40  # was default 20
SCALE_FACTOR = 111111.0 # meters per degree latitude
#ACTION_THRESHOLD = 2.0/math.sqrt(1000.0) # 1 point closer than 1km
ACTION_THRESHOLD = 20.0/math.sqrt(1000.0) # 1 point closer than 1km
AREA_BOUND = 0.001
TARGET_ASSIGN_LEVEL = 0.75

optparser = OptionParser(usage="""%prog [options]

BETASHAPES!

Describe polygon shapes for WOE ids based by Flickr photo votes.
Requires a list of places and a geojson of geography building blocks.
Automatically query Flickr for registered voters in those places (requires API key).""")

optparser.add_option('-n', '--name_file', dest='name_file',
                      help='List of WOE place IDs and their names.')

optparser.add_option('-m', '--name_file_mask', dest='name_file_mask',
                      help='Use only the WOEs you actually find useful, listed here.')

optparser.add_option('-i', '--name_file_do_not_call_list', '--ignore', dest='name_file_do_not_call_list',
                      help='Ignore these WOEs when you find they are irrelevant.')

optparser.add_option('-l', '--line_file', '--geometry_file', '--block_file', '--polygon_file', dest='line_file',
                      help='Geometries that form building blocks for the voting districts (enumeration units). If lines are provided instead of polygons (which are prefered), will create polygon shapes.')

optparser.add_option('-p', '--point_file', '--photo_file', dest='point_file',
                      help='If provided, will create polygon shapes that form the building blocks for vote enumeration units.')
                      
optparser.add_option('-o', '--out_file', dest='output_file',
                      help='Name of the resulting GeoJSON output file of the betashapes.')

optparser.add_option('-v', '--verbose',dest='verbose', help='Chatty? 1 or 0.')


if __name__ == "__main__":

    (options, args) = optparser.parse_args()
    
    #print 'len(args): ', len(args)
    
    if len(args) is 3:
        name_file, line_file, point_file = sys.argv[1:4]
    else:
        name_file = options.name_file
        name_file_mask = options.name_file_mask
        name_file_do_not_call_list = options.name_file_do_not_call_list
        line_file = options.line_file
        point_file = options.point_file
        output_file = options.output_file
        verbose = options.verbose
        
        if verbose is None: 
            verbose = 0
   
    if not name_file or not line_file or not point_file:
        print 'Requires input and output files. Exiting...'
        sys.exit(1)

    votes = {}
    names = {}
    blocks = {}
    
    if os.path.exists(point_file + '.cache'):
        if verbose: print >>sys.stderr, "Reading from %s cache..." % point_file
        names, blocks, votes = pickle.load(file(point_file + ".cache"))
        blocks = map(asShape, blocks)
    else:
        all_names = {}
        count = 0
        pt_count = 0
        for line in file(name_file):
            #place_id, name = line.strip().split(None, 1)
            woe_parent, name, woe_type, place_id = line.strip().split('\t', 4)
            print >>sys.stderr,"%s, %s, %s, %s" % (woe_parent, name, woe_type, place_id )
            if name == "name" or name == "woe_name" or name == "Name" or name == "NAME":
                pass
            else :
                all_names[int(place_id)] = name
                count += 1
                if count % 1000 == 0:
                    print >>sys.stderr, "\rRead %d names from %s." % (count, name_file),
        print >>sys.stderr, "\rRead %d names from %s." % (count, name_file)
    
        votes = load_points(point_file, name_filter)

        if verbose: 
            print >>sys.stderr, "votes: %s" % len(votes)
            print >>sys.stderr, "place_id: %s, pts: %s" % (place_id, place_id)
            for place_id, pts in votes:
                names[place_id] = all_names.get(place_id, "")
                for pt in pts:
                    pt_count += 1
            print >>sys.stderr, "pt_count: %s" % (pt_count)

        votes = discard_outliers(votes)
        
        lines = []
        do_polygonize = False
        print >>sys.stderr, "Reading lines from %s..." % line_file,
        for feature in geojson.loads(file(line_file).read())["features"]:
            if verbose: print >>sys.stderr, "\nfeature: %s" % feature,
            if feature["geometry"]["type"] in ('LineString', 'MultiLineString'):
                do_polygonize = True
            lines.append(asShape(feature["geometry"]))
        if verbose: print >>sys.stderr, "%d lines read." % len(lines)
        if do_polygonize:
            if verbose: print >>sys.stderr, "Polygonizing %d lines..." % (len(lines)),
            blocks = [poly.__geo_interface__ for poly in  polygonize(lines)]
            if verbose: print >>sys.stderr, "%d blocks formed." % len(blocks)
        else:
            blocks = [poly.__geo_interface__ for poly in lines]
    
    if not os.path.exists(point_file + '.cache'):
        print >>sys.stderr, "Caching points, blocks, and names ..."
        pickle.dump((names, blocks, votes), file(point_file + ".cache", "w"), -1)
        blocks = map(asShape, blocks)
    
    points = []
    place_list = set()
    count = 0
    pt_count = 0
    for place_id, pts in votes.items():
        count += 1
        print >>sys.stderr, "\rPreparing %d of %d polling places..." % (count, len(votes)),
        for pt in pts:
            pt_count += 1
            place_list.add((len(points), pt+pt, None))
            points.append((place_id, Point(pt)))
    #print >> sys.stderr, "len(place_list): %d - pt_count: %d" % (len(place_list), pt_count)
    print >>sys.stderr, "Indexing...",
    index = Rtree(place_list)
    print >>sys.stderr, "Done."
    
    def score_block(polygon):
        centroid = polygon.centroid
        #prepared = prep(polygon)
        score = {}
        outside_samples = 0
        for item in index.nearest((centroid.x, centroid.y), num_results=SAMPLE_SIZE):
            place_id, point = points[item]
            score.setdefault(place_id, 0.0)
            #if prepared.contains(point):
            #    score[place_id] += 1.0
            #else:
            score[place_id] += 1.0 / math.sqrt(max(polygon.distance(point)*SCALE_FACTOR, 1.0))
            outside_samples += 1
            #print >>sys.stderr, "%s %s" % (place_id, score[place_id])
        score_list = list(reversed(sorted((sc, place_id) for place_id, sc in score.items())))
        #print >>sys.stderr, "%s" % (score_list[0])
        return score_list
    
    def count_photos_in_block(block, woe_ids):
        # Count up the features
        block_photos = 0
        woe_id_photos = {}
        for place in woe_ids:
            #print >> sys.stderr, "\n%s" % place
            woe_id_photos.setdefault( place, {})
            woe_id_photos[place].setdefault("photos", 0)
            #print >> sys.stderr, "\n%s" % woe_id_photos[place]["photos"]
            
        for item in points:
            #print >> sys.stderr, "\n%s %s" % (item[0], item[1])
            place_id, point = item
            #print >> sys.stderr, "\n%s %s" % (place_id, point)
            for place in woe_ids:
                if place_id == place:
                    if block.contains( point ):
                        woe_id_photos[place]["photos"] += 1
                        block_photos += 1
        
        if verbose: print >> sys.stderr, "len(points): %s" % len(points)
        if verbose: print >> sys.stderr, "\nblock_photos: %s" % block_photos
        
        if verbose: 
            if block_photos > 0:    
                for place in woe_id_photos:
                    print >> sys.stderr, "\n%s: %s" % (place, woe_id_photos[place]["photos"])
                
        return {"block_photos": block_photos, "woe_id_photos": woe_id_photos}
    
    count = 0
    assigned_blocks = {}
    assigned_blocks_persistent = {}
    assigned_ct = 0
    unassigned = {} #keyed on the polygon's index in blocks
    for count in range(len(blocks)):
        polygon = blocks[count]
        print >>sys.stderr, "\rScoring %d of %d blocks..." % ((count+1), len(blocks)),
        if not polygon.is_valid:
            try:
                polygon = polygon.buffer(0)
                blocks[count] = polygon
            except:
                pass
        if not polygon.is_valid:
            continue
        if polygon.is_empty: continue
        if polygon.area > AREA_BOUND: continue
    
        scores = score_block(polygon)
        
        #print >>sys.stderr, "\tThere are %s matches" % len(scores)
        #print >>sys.stderr, "\tTop winner are %s with score %s" % (scores[0][1], scores[0][0])
        
        best, winner = scores[0]
        
        photos = {}
    
        if len(scores) > 1:
            best_score2, place_winner2 = scores[1]
        else:
            best_score2 = -1
            place_winner2 = -1
        if len(scores) > 2:
            best_score3, place_winner3 = scores[2]
        else:
            best_score3 = -1
            place_winner3 = -1
        if len(scores) > 3:
            best_score4, place_winner4 = scores[3]
        else:
            best_score4 = -1
            place_winner4 = -1
        if len(scores) > 4:
            best_score5, place_winner5 = scores[4]
        else:
            best_score5 = -1
            place_winner5 = -1
       
        #print >>sys.stderr, "%s, %s, %s, %s, %s" % (winner, place_winner2, place_winner3, place_winner4, place_winner5)
        
        if best > ACTION_THRESHOLD:
            assigned_ct += 1
            assigned_blocks.setdefault(winner, [])
            assigned_blocks[winner].append(polygon)
    
            assigned_blocks_persistent.setdefault( winner, {})
            assigned_blocks_persistent[winner].setdefault("place1", winner)
            assigned_blocks_persistent[winner].setdefault("score1", best)
            assigned_blocks_persistent[winner].setdefault("place2", place_winner2)
            assigned_blocks_persistent[winner].setdefault("score2", best_score2)
            assigned_blocks_persistent[winner].setdefault("place3", place_winner3)
            assigned_blocks_persistent[winner].setdefault("score3", best_score3)
            assigned_blocks_persistent[winner].setdefault("place4", place_winner4)
            assigned_blocks_persistent[winner].setdefault("score4", best_score4)
            assigned_blocks_persistent[winner].setdefault("place5", place_winner5)
            assigned_blocks_persistent[winner].setdefault("score5", best_score5)
        else:
            # if the block wasn't assigned hang onto the info about the winning nbhd
            unassigned[count] = (best, winner)
    print >>sys.stderr, "\rDone, assigned %d of %d blocks" % (assigned_ct, len(blocks))
    
    new_threshold = ACTION_THRESHOLD
    while float(assigned_ct)/len(blocks) < TARGET_ASSIGN_LEVEL and len(unassigned) > 0:
        new_threshold -= 0.1
        print >>sys.stderr, "\rDropping threshold to %f1.3... " % new_threshold
        for blockindex in unassigned.keys():
            best, winner = unassigned[blockindex]
            #if blocks[blockindex].is_empty: del(unassigned[blockindex])
            if best > new_threshold:
                assigned_ct += 1
                assigned_blocks.setdefault(winner, [])
                assigned_blocks[winner].append(blocks[blockindex])
                del unassigned[blockindex]
        print >>sys.stderr, "\rDone, assigned %d of %d blocks" % (assigned_ct, len(blocks))
        
    
    polygons = {}
    count = 0
    for place_id in votes.keys():
        count += 1
        print >>sys.stderr, "\rMerging %d of %d boundaries..." % (count, len(votes)),
        if place_id not in assigned_blocks: continue
        polygons[place_id] = cascaded_union(assigned_blocks[place_id])
    print >>sys.stderr, "\rDone (no merging required)."
    
    count = 0
    orphans = []
    for place_id, multipolygon in polygons.items():
        count += 1
        print >>sys.stderr, "\rRemoving %d orphans from %d of %d polygons..." % (len(orphans), count, len(polygons)),
        if type(multipolygon) is not MultiPolygon: continue
        polygon_count = [0] * len(multipolygon)
        for i, polygon in enumerate(multipolygon.geoms):
            prepared = prep(polygon)
            for item in index.intersection(polygon.bounds):
                item_id, point = points[item]
                if item_id == place_id and prepared.intersects(point):
                    polygon_count[i] += 1
        winner = max((c, i) for (i, c) in enumerate(polygon_count))[1]
        polygons[place_id] = multipolygon.geoms[winner]
        orphans.extend((place_id, p) for i, p in enumerate(multipolygon.geoms) if i != winner)
    print >>sys.stderr, "\rDone (no orphans)."
    
    count = 0
    total = len(orphans)
    retries = 0
    unassigned = None
    while orphans:
        unassigned = []
        for origin_id, orphan in orphans:
            count += 1
            changed = False
            print >>sys.stderr, "\rReassigning %d of %d orphans..." % (count-retries, total),
            for score, place_id in score_block(orphan):
                if place_id not in polygons:
                    # Turns out we just wind up assigning tiny, inappropriate votes
                    #polygons[place_id] = orphan
                    #changed = True
                    continue
                elif place_id != origin_id and orphan.intersects(polygons[place_id]):
                    polygons[place_id] = polygons[place_id].union(orphan)
                    changed = True
                if changed:
                    break
            if not changed:
                unassigned.append((origin_id, orphan))
                retries += 1
        if len(unassigned) == len(orphans):
            # give up
            break
        orphans = unassigned
    try:
        print >>sys.stderr, "%d retried, %d unassigned." % (retries, len(unassigned))
    except:
        pass
    
    
    print >>sys.stderr, "Returning remaining orphans to original votes."
    for origin_id, orphan in orphans:
        if orphan.intersects(polygons[origin_id]):
            polygons[origin_id] = polygons[origin_id].union(orphan)
    
    print >>sys.stderr, "Try to assign the holes to neighboring neighborhoods."
    #merge the nbhds
    #city = cascaded_union(polygons.values())
    
    #pull out any holes in the resulting Polygon/Multipolygon
    #if type(city) is Polygon:
    #    over = [city]
    #elif type(city) is MultiPolygon:
    #    over = city.geoms
    #else:
    #    print >>sys.stderr, "\rcity is of type %s, wtf." % (type(city))
    
    #holes = []
    #for poly in over:
    #    holes.extend((Polygon(LinearRing(interior.coords)) for interior in poly.interiors))
    
    #count = 0
    #total = len(holes)
    #retries = 0
    #unassigned = None
    #while holes:
    #    unassigned = []
    #    for hole in holes:
    #        count += 1
    #        changed = False
    #        print >>sys.stderr, "\rReassigning %d of %d holes..." % (count-retries, total),
    #        for score, place_id in score_block(hole):
    #            if place_id not in polygons:
    #                # Turns out we just wind up assigning tiny, inappropriate votes
    #                #nbhds[place_id] = hole
    #                #changed = True
    #                continue
    #            elif hole.intersects(polygons[place_id]):
    #                polygons[place_id] = polygons[place_id].union(hole)
    #                changed = True
    #            if changed:
    #                break
    #        if not changed:
    #            unassigned.append(hole)
    #            retries += 1
    #    if len(unassigned) == len(holes):
    #        # give up
    #        break
    #    holes = unassigned
    #print >>sys.stderr, "%d retried, %d unassigned." % (retries, len(unassigned))
    
    print >>sys.stderr, "Buffering polygons."
    for place_id, polygon in polygons.items():
        if type(polygon) is Polygon:
            polygon = Polygon(polygon.exterior.coords)
        else:
            bits = []
            for p in polygon.geoms:
                if type(p) is Polygon:
                    bits.append(Polygon(p.exterior.coords))
            polygon = MultiPolygon(bits)
        polygons[place_id] = polygon.buffer(0) 
    
    print >>sys.stderr, "Writing output."
    features = []
    suburb_names_dict = {}
    
    #suburb_file = csv.reader(open('data/suburbs.txt', 'rb'), delimiter='\t')
    #headerNames = ["woe_city", "name", "woe_type", "woe_id"]
    suburb_names = csv.DictReader( open(name_file, 'rb'), delimiter='\t')
    for row in suburb_names:
        #print >>sys.stderr, "%s, %s" % (row.get('woe_id'), row.get('name'))
        suburb_names_dict.setdefault( row.get('woe_id'), row.get('woe_name'))
        #suburb_names_dict[row.get('woe_id')].setdefault( "name", row.get('name'))
    
    #print >>sys.stderr, "suburb name: %s" % (suburb_names[place_id])
    
    for place_id, poly in polygons.items():
    
        place1 = -1
        place2 = -1
        place3 = -1
        place4 = -1
        place5 = -1
    
        score1 = -1
        score2 = -1
        score3 = -1
        score4 = -1
        score5 = -1
        
        try :
            place1 = assigned_blocks_persistent[place_id]["place1"]
            place2 = assigned_blocks_persistent[place_id]["place2"]
            place3 = assigned_blocks_persistent[place_id]["place3"]
            place4 = assigned_blocks_persistent[place_id]["place4"]
            place5 = assigned_blocks_persistent[place_id]["place5"]
        
            score1 = assigned_blocks_persistent[place_id]["score1"]
            score2 = assigned_blocks_persistent[place_id]["score2"]
            score3 = assigned_blocks_persistent[place_id]["score3"]
            score4 = assigned_blocks_persistent[place_id]["score4"]
            score5 = assigned_blocks_persistent[place_id]["score5"]
        except :
            pass
    
        winners = []
        winners.append(place1)
            
        if place2 > 0:
            winners.append(place2)
        if place3 > 0:
            winners.append(place3)
        if place4 > 0:
            winners.append(place4)
        if place5 > 0:
            winners.append(place5)
    
        photos = count_photos_in_block(poly, winners)
           
        photos_sum = photos["block_photos"]
        
        if photos_sum > 0 :
            photos1 = photos["woe_id_photos"][place1]["photos"]
        
            if place2 > 0:
                photos2 = photos["woe_id_photos"][place2]["photos"]
            else :
                photos2 = -1
            if place3 > 0:
                photos3 = photos["woe_id_photos"][place3]["photos"]
            else :
                photos3 = -1
            if place4 > 0:
                photos4 = photos["woe_id_photos"][place4]["photos"]
            else :
                photos4 = -1
            if place5 > 0:
                photos5 = photos["woe_id_photos"][place5]["photos"]
            else :
                photos5 = -1
        
            name_composite = ""
            name_closer = -1
            count = 0;
            
            if photos1 > -1:
                try:
                    name1 = suburb_names_dict[str(place1)]
                except: 
                    name1 = None
                if name1 is not None :
                    name_composite = name1
                count += 1
            else:
                name1 = ""
            if photos2 > -1:
                try:
                    name2 = suburb_names_dict[str(place2)]
                except: 
                    name2 = None
                if name2 is not None :
                    name_composite += "\n(" + name2
                name_closer = 1
                count += 1
            else:
                name2 = ""
            if photos3 > -1:
                try:
                    name3 = suburb_names_dict[str(place3)]
                except: 
                    name3 = None
                if name3 is not None :
                    name_composite += ",\n" + name3
                count += 1
            else:
                name3 = ""
            if photos4 > -1:
                try:
                    name4 = suburb_names_dict[str(place4)]
                except: 
                    name4 = None
                if name4 is not None :
                    name_composite += ",\n" + name4
                count += 1
            else:
                name4 = ""
            if photos5 > -1:
                try:
                    name5 = suburb_names_dict[str(place5)]
                except: 
                    name5 = None
                if name5 is not None :
                    name_composite += ",\n" + name5
                count += 1
            else:
                name5 = ""
                
            if name_closer > -1:
                name_composite += ")"
        
            
            #print >>sys.stderr, "%s, %s, %s, %s, %s" % (winner, place_winner2, place_winner3, place_winner4, place_winner5)
            #print >>sys.stderr, "%s" % (suburb_names_dict[str(place_id)])
                
            features.append({
                "type": "Feature",
                "id": place_id,
                "geometry": poly.__geo_interface__,
                "properties": {"woe_id": place_id, "name": names.get(place_id, ""), "name1": name1, "place1": place1, "score1": score1, "name2": name2, "place2": place2, "score2": score2, "name3": name3, "place3": place3, "score3": score3, "name4": name4, "place4": place4, "score4": score4, "name5": name5, "place5": place5, "score5": score5, "name_all": name_composite, "count": count, "photo_sum": photos_sum, "photos1": photos1, "photos2": photos2, "photos3": photos3, "photos4": photos4, "photos5": photos5 }
            })
    
    collection = {
        "type": "FeatureCollection",
        "features": features
    }
    
    if output_file:
            # Capture the absolute path to the output directory
            out_dir = os.path.dirname( os.path.abspath(output_file) )

            # If the output directory doesn't exist...
            # Make it so we don't error later on file open()
            if not os.path.exists( out_dir ):
                print 'making dir...'
                os.makedirs( out_dir )
        
            # Prepare output files
            betashape_geojson = open( output_file, "w" )
        
            # Write out the headers to the text files
            betashape_geojson.writelines( json.dumps(collection) )
        
            # Close the MSS and MML files
            betashape_geojson.close()
    else:
        print json.dumps(collection)