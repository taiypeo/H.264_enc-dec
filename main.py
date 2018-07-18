import h264

if __name__ == "__main__":
    frame_size = h264.get_video_frame_size('in.mp4')

    # Encoding/decoding
    h264.decode('in.mp4', 'decoded.yuv')
    h264.encode('decoded.yuv', 'encoded.mp4', frame_size=frame_size)

    # Saving frames from the raw YUV420 video
    h264.get_yuv420_frame('decoded.yuv', 'yuv_frame.yuv', 300, frame_size)
    h264.get_jpeg_frame('decoded.yuv', 'yuv_frame.jpg', 300, frame_size)

    # Saving frames from the H.264 encoded video
    h264.get_yuv420_frame('encoded.mp4', 'mp4_frame.yuv', 300)
    h264.get_jpeg_frame('encoded.mp4', 'mp4_frame.jpg', 300)
