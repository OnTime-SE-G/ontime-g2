def build_transit_route(geojson):

    route_feature = None
    stops = []
    path = []

    for feature in geojson["features"]:
        props = feature["properties"]
        geom = feature["geometry"]

        if props["feature_type"] == "route":
            route_feature = feature
            path = geom["coordinates"]

        elif props["feature_type"] == "stop":
            stops.append({
                "name": props["name"],
                "coordinates": geom["coordinates"]
            })

    if route_feature is None:
        raise ValueError("No route found in GeoJSON")

    return {
        "id": str(route_feature["properties"]["route_id"]),
        "number": str(route_feature["properties"]["route_id"]),  # temp
        "name": route_feature["properties"]["name"],
        "color": "#FF5733",  # temp placeholder
        "path": path,
        "stops": stops
    }