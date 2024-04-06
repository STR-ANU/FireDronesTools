# This script converts a video that a browser like Firefox says "No video with supported format and MIME type found." into a format it can play.


[ $# -eq 2 ] || {
    echo "Usage: INPUT OUTPUT"
    exit 1
}

RGB="$1"
OUTPUT="$2"

ffmpeg -i "$RGB" -movflags faststart -pix_fmt yuv420p "$2"
