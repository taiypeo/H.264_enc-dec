import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

from h264 import *

if __name__ == '__main__':
    Gst.init(None)

    frames = []
    for i in range(58):
        file = open('test/frame' + str(i) + '.yuv', 'rb')
        data = file.read()
        file.close()
        frames.append(VideoFrame(640, 480, data))
    encoder = H264_Encoder()
    payloads = encoder.encode(frames)
    print(len(payloads))

    GObject.MainLoop().run()
