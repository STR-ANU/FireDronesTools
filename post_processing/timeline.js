var flight_json = null
var vehicle_marker = null

// treat a map click as a warp request if below this threshold
var map_click_dist_threshold = 25.0;

function get_flight_start() {
    return new Date(flight_json[0].timestamp*1000);
}

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

  */
function warp_map_to_timestamp(timestamp) {
    var p = get_data_for_timestamp(timestamp);
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

function warp_videos_to_timestamp(timestamp) {
    for (let i = 0; i < video_list.length; i++) {
	var video = document.getElementById(video_list[i].video_id);
	var seek_seconds = (timestamp - video_list[i].start_time)*0.001;
	video.currentTime = seek_seconds;
    }
}

function warp_to_timestamp(timestamp) {
    warp_map_to_timestamp(timestamp);
    warp_videos_to_timestamp(timestamp);
}

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
	warp_to_timestamp(timestamp);
    });
}

function video_is_playing(video) {
    return video.currentTime > 0 && !video.paused && !video.ended;
}

function check_video_playback() {
    for (let i = 0; i < video_list.length; i++) {
	var video = document.getElementById(video_list[i].video_id);
	if (!video_is_playing(video)) {
	    continue;
	}

	// copy the date first, then update
	var timestamp = new Date(video_list[i].start_time);
	timestamp.setSeconds(timestamp.getSeconds() + video.currentTime);
	warp_map_to_timestamp(timestamp);
	break;
    }

}

function set_flight_json(json) {
    flight_json = json;
    create_timeline();
}

function handle_map_click(mapsMouseEvent) {
    var latlon = mapsMouseEvent.latLng;
    var timestamp = get_timestamp_for_latlon(latlon);
    warp_videos_to_timestamp(timestamp);
    warp_map_to_timestamp(timestamp);
}

// load flight.json
fetch('flight.json').then(obj => obj.json()).then(json => set_flight_json(json));

// call check_video_playback at 1Hz
window.setInterval(function(){ check_video_playback() }, 1000);
