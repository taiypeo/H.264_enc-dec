import h264
import av
if __name__ == "__main__":
    container = av.open('in.mp4')
    frames = list(container.decode(video=0))
    new_frames = []

    for i in range(300, 325):
        frame = frames[i]
        data = h264.__data_from_av_frame(frame)
        new_frame = h264.__data_to_av_frame(data, 1920, 800)
        new_frames.append(new_frame)

    out_container = av.open('out.yuv', mode='w')
    stream = out_container.add_stream('rawvideo', rate=24)
    stream.width = 1920
    stream.height = 800
    stream.pix_fmt = 'yuv420p'

    for frame in new_frames:
        for packet in stream.encode(frame):
            out_container.mux(packet)

    for packet in stream.encode():
        out_container.mux(packet)

    out_container.close()
