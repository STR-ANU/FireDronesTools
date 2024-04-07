/*
  handling of time synch for various UI elements
  */

var flight_json = null;
var vehicle_marker = null;
var current_timestamp = null;

// treat a map click as a warp request if below this threshold
var map_click_dist_threshold = 25.0;

/*
  get time flight started, based on flight.json
  */
function get_flight_start() {
    return new Date(flight_json[0].timestamp*1000);
}

/*
  get time flight ended, based on flight.json
  */
function get_flight_end() {
    return new Date(flight_json[flight_json.length-1].timestamp*1000);
}

/*
  get flight json record for a given timestamp, takes a Date object
*/
function get_data_for_timestamp(js_timestamp) {
    if (!flight_json) {
	return null;
    }
    var idx_low = 0;
    var idx_high = flight_json.length - 1;
    while (idx_low < idx_high) {
	var mid = Math.floor((idx_low + idx_high) / 2);
	var tsdate = new Date(flight_json[mid].timestamp*1000);
	if (tsdate < js_timestamp) {
	    idx_low = mid+1;
	} else {
	    idx_high = mid;
	}
    }
    return flight_json[idx_low];
}

/*
  find the timestamp closest to the given latlon, returns a js Date object
*/
function get_timestamp_for_latlon(latlon) {
    if (!flight_json) {
	return null;
    }
    var smallest_distance = null;
    var smallest_timestamp = null;
    for (let i=0; i<flight_json.length; i++) {
	var dist = google.maps.geometry.spherical.computeDistanceBetween(latlon, new google.maps.LatLng(flight_json[i].lat, flight_json[i].lon));
	if (dist < map_click_dist_threshold && smallest_distance == null || dist < smallest_distance) {
	    smallest_distance = dist;
	    smallest_timestamp = flight_json[i].timestamp;
	}
    }
    if (smallest_timestamp == null) {
	return null;
    }
    return new Date(smallest_timestamp*1000);
}

/*
  warp map marker to a timestamp
  */
function warp_map_to_timestamp(js_timestamp) {
    var p = get_data_for_timestamp(js_timestamp);
    if (!p) {
	return;
    }
    if (!vehicle_marker) {
	vehicle_marker = new google.maps.Marker({
	    map: global_map,
	    position: { lat: p.lat, lng: p.lon },
	});
    }
    vehicle_marker.setPosition(new google.maps.LatLng(p.lat, p.lon));
}

/*
  warp playback time of videos to a js_timestamp
  */
function warp_videos_to_timestamp(js_timestamp) {
    for (let i = 0; i < video_list.length; i++) {
	var video = document.getElementById(video_list[i].video_id);
	var seek_seconds = (js_timestamp - video_list[i].start_time)*0.001;
	video.currentTime = seek_seconds;
    }
}

/*
  create and display the timeline object
  */
function create_timeline() {
    var container = document.getElementById('timeline');

    // Data for the Timeline
    var items = new vis.DataSet([
	{id: 1, content: 'FlightStart', start: get_flight_start()},
	{id: 2, content: 'FlightEnd', start: get_flight_end()},
    ]);

    // Configuration for the Timeline
    var options = {};

    // Create a Timeline
    var timeline = new vis.Timeline(container, items, options);

    // Callback function for when an item is selected
    timeline.on('select', function (properties) {
	var selectedId = properties.items[0];
	var selectedItem = items.get(selectedId);
    });

    timeline.on('click', function (properties) {
	var timestamp = properties.time;
	handle_timeline_click(timestamp);
    });
}

/*
  return true if a video is currently playing
  */
function video_is_playing(video) {
    return video.currentTime > 0 && !video.paused && !video.ended;
}

/*
  check if we are playing a video, and if so then update map marker
  */
function check_video_playback() {
    for (let i = 0; i < video_list.length; i++) {
	var video = document.getElementById(video_list[i].video_id);
	if (!video_is_playing(video)) {
	    continue;
	}

	// copy the date first, then update
	var js_timestamp = new Date(video_list[i].start_time);
	js_timestamp.setSeconds(js_timestamp.getSeconds() + video.currentTime);
	warp_map_to_timestamp(js_timestamp);
	current_timestamp = new Date(js_timestamp);
	break;
    }
}

/*
  update status text with current state
*/
function update_status() {
    var js_timestamp = current_timestamp;
    var p = get_data_for_timestamp(js_timestamp);
    var status = `
THeight: ${p.theight.toFixed(1)} m<br>
Yaw: ${p.yaw.toFixed(1)} degrees<br>
VehicleLat: ${p.lat.toFixed(9)}<br>
VehicleLon: ${p.lon.toFixed(9)}<br>
`;
    set_status_text(status);
}

/*
  handle 1Hz timer update
*/
function handle_timer_update() {
    check_video_playback();
    update_status();
}

/*
  handle a click on the timeline bar
  */
function handle_timeline_click(js_timestamp) {
    current_timestamp = new Date(js_timestamp);
    warp_map_to_timestamp(js_timestamp);
    warp_videos_to_timestamp(js_timestamp);
}

/*
  handle a click on the map. If we click within
  map_click_dist_threshold of a path point we warp to the closest path
  point
  */
function handle_map_click(mapsMouseEvent) {
    var latlon = mapsMouseEvent.latLng;
    var js_timestamp = get_timestamp_for_latlon(latlon);
    current_timestamp = new Date(js_timestamp);
    warp_videos_to_timestamp(js_timestamp);
    warp_map_to_timestamp(js_timestamp);
}

function set_status_text(text) {
    var status_el = document.getElementById("status_text");
    status_el.innerHTML = text;
}


/*
  callback to set flight_json variable from flight.json
  */
function set_flight_json(json) {
    flight_json = json;
    create_timeline();
}

// load flight.json
fetch('flight.json').then(obj => obj.json()).then(json => set_flight_json(json));

// call check_video_playback at 1Hz
window.setInterval(function(){ handle_timer_update() }, 1000);
