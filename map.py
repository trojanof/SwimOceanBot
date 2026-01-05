import streamlit as st
import folium
import geopy.distance
import math


def distance_between(start, end):
    return geopy.distance.distance(start, end).km


def calculate_initial_compass_bearing(start: tuple,
                                      end: tuple) -> float:
    '''
    Calculates compass bearing (angle) fro start to end point
    '''
    if not isinstance(start, tuple) or not isinstance(end, tuple):
        raise TypeError("Only tuples are supported as arguments")
    lat1 = math.radians(start[0])
    lat2 = math.radians(end[0])
    diffLong = math.radians(end[1] - start[1])
    x = math.sin(diffLong) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (
            math.sin(lat1) * math.cos(lat2) * math.cos(diffLong))
    initial_bearing = math.atan2(x, y)
    # Now we have the initial bearing but math.atan2 return values
    # from -180° to + 180° which is not what we want for a compass bearing
    # The solution is to normalize the initial bearing as shown below
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360
    return compass_bearing


def location_at_dist(start: tuple,
                     end: tuple,
                     distance_travelled,
                     bearing: float | None = None) -> tuple[float, float]:
    '''
    Claculates point location between start and end point along straight
    line on a given distance
    '''
    if not bearing:
        bearing = calculate_initial_compass_bearing(start, end)
    point = geopy.distance.distance(
        kilometers=distance_travelled).destination(
        start,
        bearing=bearing
    )
    current_location = (point.latitude, point.longitude)
    return current_location


def draw_marker(coord, caption=''):
    '''
    Creates a marker with caption. To be added to the map
    '''
    marker = folium.CircleMarker(
        location=coord,
        radius=7,
        fill=True,
        popup=folium.Popup(caption),
        color='red'
        )
    return marker


def get_points_list_along_path(start_point, finish_point, bearing=None):
    '''
    Creates a list of points with coordinates between
    start and finish points. To be used for polyline drawing
    '''
    route_array = []
    route_array.append(tuple(start_point))
    full_dist = distance_between(start_point, finish_point)
    for i in range(1, 100, 1):
        dist = full_dist * i / 100
        pt = location_at_dist(
            tuple(start_point),
            tuple(finish_point),
            dist,
            bearing
            )
        route_array.append(pt)
    route_array.append(tuple(finish_point))
    return route_array


def prepare_map(start_coord,
                finish_coord,
                start_caption,
                finish_caption,
                dist,
                distance_travelled):
    '''
    Creates a map with start/finish points markers, tarjectory line
    and a highlighted line of travelled distance
    '''
    if 'map' not in st.session_state or st.session_state.map is None:
        half_dist = distance_between(start_coord, finish_coord) / 2
        center_point = location_at_dist(tuple(start_coord),
                                        tuple(finish_coord),
                                        half_dist)

        world_map = folium.Map(
            location=center_point,
            zoom_start=10,
            tiles="OpenStreetMap",
            attributionControl=0
            )

        draw_marker(start_coord, start_caption).add_to(world_map)
        draw_marker(finish_coord, finish_caption).add_to(world_map)

        dist_on_map = distance_between(start_coord, finish_coord) * 1000
        portion_travelled = distance_travelled / dist
        graphical_distance = round(portion_travelled * dist_on_map)
        current_point = location_at_dist(
            tuple(start_coord),
            tuple(finish_coord),
            graphical_distance / 1000
            )
        current_point = tuple(round(i, 3) for i in current_point)
        bearing = calculate_initial_compass_bearing(start=tuple(start_coord),
                                                    end=tuple(finish_coord))
        if 0 <= bearing <= 180:
            icon_image = 'swimmer_right.png'
        else:
            icon_image = 'swimmer_left.png'

        icon = folium.CustomIcon(
            icon_image,
            icon_size=(50, 50)
            )
        remaining_dist = dist - distance_travelled
        folium.Marker(location=current_point,
                      icon=icon,
                      popup=folium.Popup(
                          f'Мы тут! До конца пролива {remaining_dist} м',
                          parse_html=True,
                          max_width=100)).add_to(world_map)

        curr_coords = get_points_list_along_path(start_coord, current_point)
        folium.PolyLine(
            locations=curr_coords,
            color="#FF0000",
            weight=5,
            tooltip=f"Проплыто {distance_travelled} м"
            ).add_to(world_map)

        route_array = get_points_list_along_path(start_coord, finish_coord)
        folium.PolyLine(
            locations=route_array,
            color="#008000",
            weight=2,
            tooltip=f"Траектория заплыва, длина {dist} м",
            dash_array='5',
            opacity=0.3
            ).add_to(world_map)

        st.session_state.map = world_map
    return st.session_state.map
