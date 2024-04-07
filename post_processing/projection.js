function radians(degrees) {
    return degrees * Math.PI / 180;
}

function constrain(v, minv, maxv) {
    if (v < minv) {
        return minv;
    } else if (v > maxv) {
        return maxv;
    } else {
        return v;
    }
}

function radians(deg) {
    return deg * Math.PI / 180;
}

function degrees(rad) {
    return rad * 180 / Math.PI;
}

/*
  calculate a new LatLng given a bearing (in degrees) and distance in
  meters
  */
function gps_newpos(latlon, bearing, distance) {
    const radius_of_earth = 6371e3; // in meters
    var latlonstr = latlon.toString();
    let lat1 = constrain(radians(latlon.lat()), -Math.PI / 2 + 1.0e-15, Math.PI / 2 - 1.0e-15);
    let lon1 = radians(latlon.lng());
    let tc = radians(-bearing);
    let d = distance / radius_of_earth;

    let newLat = lat1 + d * Math.cos(tc);
    newLat = constrain(newLat, -Math.PI / 2 + 1.0e-15, Math.PI / 2 - 1.0e-15);
    
    let q;
    if (Math.abs(newLat - lat1) < 1.0e-15) {
        q = Math.cos(lat1);
    } else {
        let dphi = Math.log(Math.tan(newLat / 2 + Math.PI / 4) / Math.tan(lat1 / 2 + Math.PI / 4));
        q = (newLat - lat1) / dphi;
    }

    let dlon = -d * Math.sin(tc) / q;
    let newLon = (lon1 + dlon + Math.PI) % (2 * Math.PI) - Math.PI;
    
    return new google.maps.LatLng(degrees(newLat), degrees(newLon));
}

/*
  calculate a new LatLng given a distance east and distance north from a latlon
  */
function gps_offset(latlon, east, north) {
    let bearing = degrees(Math.atan2(east, north));
    let distance = Math.sqrt(east * east + north * north);
    return gps_newpos(latlon, bearing, distance);
}

/*
  return a Vector3 for the view given flight position and x,y in image

  x and y go from -1 to 1 a x,y of 0,0 is the center of the image
  */
function get_view_vector(fpos, x, y, FOV, aspect_ratio) {
    let v = new Vector3(1, 0, 0);
    let m = new Matrix3();
    let roll = radians(fpos.GRoll);
    let pitch = radians(fpos.GPitch);
    let yaw = radians(fpos.GYaw);
    yaw += radians(fpos.yaw);
    let FOV_half = radians(0.5 * FOV);
    yaw += FOV_half * x;
    pitch -= y * FOV_half / aspect_ratio;
    m.fromEuler(roll, pitch, yaw);
    v = m.multiply(v);
    return v;
}

/*
  get a LatLng given (x,y) position in image

  x and y go from -1 to 1 a x,y of 0,0 is the center of the image
  */
function get_latlon(fpos, x, y, FOV, aspect_ratio) {
    let v = get_view_vector(fpos, x, y, FOV, aspect_ratio);
    if (!v) {
        return null;
    }
    v.x *= fpos.SR;
    v.y *= fpos.SR;
    let latlon = new google.maps.LatLng(fpos.lat, fpos.lon);
    return gps_offset(latlon, v.y, v.x);
}

function get_viewport_corners(fpos, FOV, aspect_ratio) {
    return [get_latlon(fpos, -1, -1, FOV, aspect_ratio),
	    get_latlon(fpos, 1, -1,  FOV, aspect_ratio),
	    get_latlon(fpos, 1, 1,   FOV, aspect_ratio),
	    get_latlon(fpos, -1, 1,  FOV, aspect_ratio)]
}
