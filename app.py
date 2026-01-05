import os
import random
import subprocess
import zipfile
import uuid
import tempfile
import shutil

from flask import Flask, render_template, request, send_file, after_this_request

app = Flask(__name__)


def get_video_duration(video_path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return float(result.stdout.strip())


def split_video(video_path, min_minutes, max_minutes, clip_dir):
    duration = get_video_duration(video_path)
    start = 0
    part = 1
    clips = []

    while start < duration:
        clip_length = random.randint(min_minutes, max_minutes) * 60

        if start + clip_length > duration:
            clip_length = duration - start

        output_path = os.path.join(clip_dir, f"clip_{part}.mp4")

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(clip_length),
            "-c", "copy",
            output_path
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        clips.append(output_path)
        start += clip_length
        part += 1

    return clips


def zip_clips(clip_files, zip_path):
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for clip in clip_files:
            zipf.write(clip, os.path.basename(clip))


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        video = request.files["video"]
        min_duration = int(request.form["min_duration"])
        max_duration = int(request.form["max_duration"])

        # -------- CREATE ISOLATED TEMP JOB FOLDER --------
        job_id = str(uuid.uuid4())
        base_temp = tempfile.gettempdir()
        job_dir = os.path.join(base_temp, job_id)

        upload_dir = os.path.join(job_dir, "upload")
        clip_dir = os.path.join(job_dir, "clips")

        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(clip_dir, exist_ok=True)

        video_path = os.path.join(upload_dir, video.filename)
        video.save(video_path)

        clips = split_video(video_path, min_duration, max_duration, clip_dir)

        zip_path = os.path.join(job_dir, "clips.zip")
        zip_clips(clips, zip_path)

        # -------- AUTO CLEANUP AFTER DOWNLOAD --------
        @after_this_request
        def cleanup(response):
            try:
                shutil.rmtree(job_dir)
            except Exception as e:
                print("Cleanup error:", e)
            return response

        return send_file(zip_path, as_attachment=True)

    return render_template("index.html")


if __name__ == "__main__":
    app.run()
