
#This script is for fixing video files:
# 1) Converts a video that a browser like Firefox says "No video with supported format and MIME type found." or simila into a format it can play.
# 2) Converts a mts video recorded by GCS so that VLC can play it better.


if [ "$#" -lt 2 ] ; then
    echo "Usage: INPUT OUTPUT [FIX_TYPE]"
    echo "Output should always be a .mp4 file."
    echo "FIX_TYPE is optional and can be either 's' to fix for streaming, or 'm' to fix mts recordings for playing on VLC. Default is 's'."
    exit 1
elif [ ! -z "$3" ] && [ "$3" = "m" ] ; then
    echo "Doing fix for mts recordings (just codec copy)."
    echo "1 $1 2 $2"
    # ffmpeg -i "$1" -c:v copy "$2"
else
    echo "Doing fix for playing on Chrome & Firefox (faststart and yuv420p)."
    echo "1 $1 2 $2"
    # ffmpeg -i "$1" -movflags faststart -pix_fmt yuv420p "$2"
fi

