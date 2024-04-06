var flight_json = null
var vehicle_marker = null

function get_flight_start() {
    return new Date(flight_json[0].timestamp*1000);
}

function get_flight_end() {
    return new Date(flight_json[flight_json.length-1].timestamp*1000);
}

function get_data_for_timestamp(timestamp) {
    if (!flight_json) {
	return null;
    }
    var idx_low = 0;
    var idx_high = flight_json.length - 1;
    while (idx_low < idx_high) {
	var mid = Math.floor((idx_low + idx_high) / 2);
	var tsdate = new Date(flight_json[mid].timestamp*1000);
	if (tsdate < timestamp) {
	    idx_low = mid+1;
	} else {
	    idx_high = mid;
	}
    }
    return flight_json[idx_low];
}

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

// load flight.json
fetch('flight.json').then(obj => obj.json()).then(json => set_flight_json(json));

// call check_video_playback at 1Hz
window.setInterval(function(){ check_video_playback() }, 1000);
